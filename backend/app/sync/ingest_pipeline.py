"""Data ingestion pipeline: Apple data / file uploads -> Entity + Obsidian note + LLM tag suggestion -> Review queue.

This is the central orchestrator that connects all Phase 2 components.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from app.storage.sqlite_client import get_db
from app.sync.obsidian_writer import (
    write_note_to_vault,
    note_from_apple_note,
    note_from_apple_reminder,
    note_from_apple_event,
)
from app.services.tag_engine import suggest_tags
from app.services.review_service import create_review_item

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


async def ingest_entity(
    *,
    title: str,
    content: str,
    source: str,
    source_id: str | None = None,
    content_type: str = "text",
    file_path: str | None = None,
    folder: str = "",
    metadata: dict | None = None,
    created_by: str = "system",
    skip_llm: bool = False,
) -> dict:
    """Full ingestion pipeline for a single piece of content.

    Steps:
    1. Write Obsidian note
    2. Create entity in SQLite
    3. Create initial version
    4. LLM tag suggestion (if not skipped)
    5. Create review queue item

    Returns the created entity dict.
    """
    db = await get_db()
    entity_id = str(uuid.uuid4())
    c_hash = _content_hash(content)

    # Check for duplicate by source_id
    if source_id:
        cursor = await db.execute(
            "SELECT id, content_hash FROM entities WHERE source = ? AND source_id = ?",
            (source, source_id),
        )
        existing = await cursor.fetchone()
        if existing:
            if existing["content_hash"] == c_hash:
                logger.debug("Skipping unchanged entity: %s/%s", source, source_id)
                return {"id": existing["id"], "status": "skipped", "reason": "unchanged"}
            entity_id = existing["id"]
            return await _update_existing_entity(entity_id, title, content, c_hash, metadata)

    # Step 1: Write Obsidian note
    obsidian_path = None
    try:
        rel_path = await write_note_to_vault(
            title=title, content=content, source=source,
            source_id=source_id, folder=folder,
        )
        obsidian_path = str(rel_path)
    except Exception as e:
        logger.warning("Failed to write Obsidian note for '%s': %s", title, e)

    # Step 2: Create entity
    await db.execute(
        """INSERT INTO entities
           (id, source, source_id, title, content, content_type,
            obsidian_path, file_path, metadata, current_version,
            review_status, content_hash, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'pending', ?, ?, datetime('now'), datetime('now'))""",
        (
            entity_id, source, source_id, title, content, content_type,
            obsidian_path, file_path,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            c_hash, created_by,
        ),
    )

    # Step 3: Create initial version
    version_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO entity_versions
           (id, entity_id, version_number, title, content, metadata,
            change_source, change_summary, created_at)
           VALUES (?, ?, 1, ?, ?, ?, ?, '初始版本', datetime('now'))""",
        (
            version_id, entity_id, title, content,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            source,
        ),
    )
    await db.commit()

    # Step 4 & 5: LLM tag suggestion + review queue
    suggestion = {
        "folder_tags": [], "content_tags": [], "status": {},
        "confidence": {}, "summary": title or "",
    }
    if not skip_llm:
        from app.services.llm_service import check_available
        llm_ok = await check_available()
        if llm_ok:
            try:
                suggestion = await suggest_tags(title, content, source, metadata)
            except Exception as e:
                logger.warning("LLM tag suggestion failed for '%s': %s", title, e)
        else:
            logger.info("LLM unavailable, using empty suggestion for '%s'", title)

    # Always create a review item so user can manually tag
    try:
        await create_review_item(entity_id, suggestion)
    except Exception as e:
        logger.warning("Failed to create review item for '%s': %s", title, e)

    return {
        "id": entity_id,
        "status": "created",
        "title": title,
        "source": source,
        "obsidian_path": obsidian_path,
    }


async def _update_existing_entity(
    entity_id: str, title: str, content: str, c_hash: str, metadata: dict | None,
) -> dict:
    """Update an existing entity with new content (new version)."""
    db = await get_db()

    cursor = await db.execute("SELECT current_version FROM entities WHERE id = ?", (entity_id,))
    row = await cursor.fetchone()
    new_version = (row["current_version"] if row else 0) + 1

    await db.execute(
        """UPDATE entities SET title = ?, content = ?, content_hash = ?,
           current_version = ?, updated_at = datetime('now'),
           metadata = COALESCE(?, metadata)
           WHERE id = ?""",
        (title, content, c_hash, new_version,
         json.dumps(metadata, ensure_ascii=False) if metadata else None,
         entity_id),
    )

    version_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO entity_versions
           (id, entity_id, version_number, title, content, metadata,
            change_source, change_summary, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'sync', '同步更新', datetime('now'))""",
        (version_id, entity_id, new_version, title, content,
         json.dumps(metadata, ensure_ascii=False) if metadata else None),
    )
    await db.commit()

    logger.info("Updated entity %s to version %d", entity_id, new_version)
    return {"id": entity_id, "status": "updated", "version": new_version}


async def ingest_apple_notes(
    limit: int = 50,
    order: str = "newest",
    folder_whitelist: list[str] | None = None,
) -> list[dict]:
    """Run the full Apple Notes ingestion pipeline. Optional folder_whitelist = only sync these folders."""
    from app.sync.apple_notes import fetch_all_notes
    notes = await fetch_all_notes(limit=limit, order=order, folder_whitelist=folder_whitelist)
    results = []
    for note in notes:
        kwargs = note_from_apple_note(note)
        meta = kwargs.pop("extra_meta", None)
        result = await ingest_entity(
            **kwargs,
            content_type="text",
            metadata=meta,
            created_by="apple_notes_sync",
        )
        results.append(result)
    return results


async def ingest_apple_reminders(
    limit: int = 50,
    order: str = "newest",
    list_names: list[str] | None = None,
    due_after: str | None = None,
    due_before: str | None = None,
) -> list[dict]:
    """Run the full Apple Reminders ingestion pipeline. Optional list_names and due range."""
    from app.sync.apple_reminders import fetch_all_reminders
    reminders = await fetch_all_reminders(
        limit=limit, order=order,
        list_names=list_names, due_after=due_after, due_before=due_before,
    )
    results = []
    for reminder in reminders:
        kwargs = note_from_apple_reminder(reminder)
        meta = kwargs.pop("extra_meta", None)
        result = await ingest_entity(
            **kwargs,
            content_type="text",
            metadata=meta,
            created_by="apple_reminders_sync",
        )
        results.append(result)
    return results


async def ingest_apple_calendar(
    limit: int = 50,
    order: str = "newest",
    days_back: int = 30,
    days_forward: int = 90,
) -> list[dict]:
    """Run the full Apple Calendar ingestion pipeline. Time range = now - days_back to now + days_forward."""
    from app.sync.apple_calendar import fetch_all_events
    events = await fetch_all_events(
        limit=limit, order=order,
        days_back=days_back, days_forward=days_forward,
    )
    results = []
    for event in events:
        kwargs = note_from_apple_event(event)
        meta = kwargs.pop("extra_meta", None)
        result = await ingest_entity(
            **kwargs,
            content_type="text",
            metadata=meta,
            created_by="apple_calendar_sync",
        )
        results.append(result)
    return results


async def ingest_uploaded_file(
    file_path: str,
    original_filename: str,
    content_type: str,
    created_by: str = "upload",
) -> dict:
    """Process an uploaded file through the ingestion pipeline."""
    from app.services.file_processor import extract_text, detect_content_type

    text = await extract_text(file_path, content_type)
    ct = detect_content_type(original_filename)
    title = original_filename.rsplit(".", 1)[0] if "." in original_filename else original_filename

    return await ingest_entity(
        title=title,
        content=text,
        source="upload",
        content_type=ct,
        file_path=file_path,
        folder="Resources/Uploads",
        created_by=created_by,
    )
