"""Review queue service: manages LLM tag suggestions awaiting human approval."""

from __future__ import annotations

import json
import logging
import uuid

from app.storage.sqlite_client import get_db

logger = logging.getLogger(__name__)


async def create_review_item(
    entity_id: str,
    suggestion: dict,
) -> str:
    """Insert a new review item into the queue. Returns review item ID."""
    db = await get_db()
    review_id = str(uuid.uuid4())

    await db.execute(
        """INSERT INTO review_queue
           (id, entity_id, suggested_folder_tags, suggested_content_tags,
            suggested_status, confidence_scores, status)
           VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
        (
            review_id,
            entity_id,
            json.dumps(suggestion.get("folder_tags", []), ensure_ascii=False),
            json.dumps(suggestion.get("content_tags", []), ensure_ascii=False),
            json.dumps(suggestion.get("status", {}), ensure_ascii=False),
            json.dumps(suggestion.get("confidence", {}), ensure_ascii=False),
        ),
    )
    await db.commit()
    logger.info("Created review item %s for entity %s", review_id, entity_id)
    return review_id


async def list_reviews(status: str = "all", page: int = 1, page_size: int = 50) -> dict:
    """List review items with optional status filter. Returns {items, total, page}."""
    db = await get_db()
    offset = (page - 1) * page_size

    where = ""
    params: list = []
    if status != "all":
        where = "WHERE r.status = ?"
        params.append(status)

    count_cursor = await db.execute(
        f"SELECT COUNT(*) as cnt FROM review_queue r {where}", params
    )
    total = (await count_cursor.fetchone())["cnt"]

    cursor = await db.execute(
        f"""SELECT r.*, e.title as entity_title, e.source as entity_source,
                  substr(e.content, 1, 300) as entity_content
           FROM review_queue r
           JOIN entities e ON r.entity_id = e.id
           {where}
           ORDER BY r.created_at DESC
           LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    )
    rows = _parse_json_fields([dict(r) for r in await cursor.fetchall()])
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def list_pending(page: int = 1, page_size: int = 50) -> list[dict]:
    """List pending review items with entity info."""
    result = await list_reviews(status="pending", page=page, page_size=page_size)
    return result["items"]


async def get_pending_count() -> int:
    """Count pending review items."""
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM review_queue WHERE status = 'pending'")
    row = await cursor.fetchone()
    return row["cnt"]


async def get_stats() -> dict:
    """Get review counts by status."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT status, COUNT(*) as cnt FROM review_queue GROUP BY status"
    )
    stats = {r["status"]: r["cnt"] for r in await cursor.fetchall()}
    stats["total"] = sum(stats.values())
    return stats


def _parse_json_fields(rows: list[dict]) -> list[dict]:
    for row in rows:
        for key in ("suggested_folder_tags", "suggested_content_tags", "suggested_status", "confidence_scores", "reviewer_action"):
            if row.get(key) and isinstance(row[key], str):
                try:
                    row[key] = json.loads(row[key])
                except json.JSONDecodeError:
                    pass
    return rows


async def approve_item(review_id: str, modifications: dict | None = None) -> dict:
    """Approve a review item, optionally with modifications.

    If modifications is provided, the modified tags are used instead of the suggestions.
    """
    db = await get_db()

    cursor = await db.execute("SELECT * FROM review_queue WHERE id = ?", (review_id,))
    item = await cursor.fetchone()
    if item is None:
        raise ValueError("Review item not found")

    item = dict(item)
    status = "approved" if modifications is None else "modified"

    folder_tags = modifications.get("folder_tags") if modifications else None
    content_tags = modifications.get("content_tags") if modifications else None
    status_values = modifications.get("status") if modifications else None

    if folder_tags is None:
        val = item["suggested_folder_tags"]
        folder_tags = json.loads(val) if isinstance(val, str) else (val or [])
    if content_tags is None:
        val = item["suggested_content_tags"]
        content_tags = json.loads(val) if isinstance(val, str) else (val or [])
    if status_values is None:
        val = item["suggested_status"]
        status_values = json.loads(val) if isinstance(val, str) else (val or {})

    action = {
        "status": status,
        "final_folder_tags": folder_tags,
        "final_content_tags": content_tags,
        "final_status": status_values,
    }
    if modifications:
        action["modifications"] = modifications

    await db.execute(
        """UPDATE review_queue
           SET status = ?, reviewer_action = ?, reviewed_at = datetime('now')
           WHERE id = ?""",
        (status, json.dumps(action, ensure_ascii=False), review_id),
    )

    # Apply tags to entity
    entity_id = item["entity_id"]
    await _apply_tags_to_entity(entity_id, folder_tags, content_tags, status_values)

    await db.execute(
        "UPDATE entities SET review_status = 'reviewed', updated_at = datetime('now') WHERE id = ?",
        (entity_id,),
    )
    await db.commit()

    # Move note to folder tag directory, then update frontmatter
    cursor = await db.execute("SELECT obsidian_path FROM entities WHERE id = ?", (entity_id,))
    entity_row = await cursor.fetchone()
    if entity_row and entity_row["obsidian_path"]:
        current_path = entity_row["obsidian_path"]
        try:
            from app.sync.obsidian_writer import move_note_to_folder, update_note_frontmatter

            # Step 1: Move file to the first folder_tag directory
            if folder_tags:
                new_path = await move_note_to_folder(current_path, folder_tags[0])
                if new_path and new_path != current_path:
                    current_path = new_path
                    await db.execute(
                        "UPDATE entities SET obsidian_path = ? WHERE id = ?",
                        (current_path, entity_id),
                    )
                    await db.commit()

            # Step 2: Update frontmatter with tags
            fm_updates: dict = {"review_status": "reviewed"}
            if folder_tags:
                fm_updates["folder_tags"] = folder_tags
            if content_tags:
                fm_updates["tags"] = content_tags
            if status_values:
                fm_updates["status"] = status_values
            await update_note_frontmatter(current_path, fm_updates)
        except Exception as e:
            logger.warning("Failed to update Obsidian note for entity %s: %s", entity_id, e)

    # Trigger async vectorization + knowledge graph extraction
    try:
        from app.services.embedding_service import embed_entity
        from app.services.entity_extractor import extract_and_store
        embed_ok = await embed_entity(entity_id)
        extract_result = await extract_and_store(entity_id)
        logger.info(
            "Post-approval pipeline for %s: embed=%s, extract=%s",
            entity_id, embed_ok, extract_result.get("status"),
        )
    except Exception as e:
        logger.warning("Post-approval pipeline error for entity %s: %s", entity_id, e)

    logger.info("Approved review %s (status: %s) for entity %s", review_id, status, entity_id)
    return action


async def reject_item(review_id: str, reason: str = "") -> None:
    """Reject a review item."""
    db = await get_db()
    action = json.dumps({"status": "rejected", "reason": reason}, ensure_ascii=False)
    await db.execute(
        """UPDATE review_queue
           SET status = 'rejected', reviewer_action = ?, reviewed_at = datetime('now')
           WHERE id = ?""",
        (action, review_id),
    )
    await db.commit()
    logger.info("Rejected review %s", review_id)


async def batch_approve(review_ids: list[str]) -> int:
    """Approve multiple review items at once. Returns count of approved items."""
    count = 0
    for rid in review_ids:
        try:
            await approve_item(rid)
            count += 1
        except Exception as e:
            logger.warning("Failed to approve %s: %s", rid, e)
    return count


async def _apply_tags_to_entity(
    entity_id: str,
    folder_tags: list[str],
    content_tags: list[str],
    status_values: dict,
):
    """Write approved tags to entity_tags table."""
    db = await get_db()

    if folder_tags:
        for folder_path in folder_tags:
            cursor = await db.execute("SELECT id FROM tag_tree WHERE path = ?", (folder_path,))
            row = await cursor.fetchone()
            if row:
                tag_tree_id = row["id"]
                await db.execute(
                    """INSERT OR REPLACE INTO entity_tags
                       (entity_id, tag_tree_id, content_tag_ids, status_values, created_at)
                       VALUES (?, ?, ?, ?, datetime('now'))""",
                    (
                        entity_id,
                        tag_tree_id,
                        json.dumps(content_tags, ensure_ascii=False),
                        json.dumps(status_values, ensure_ascii=False),
                    ),
                )
    elif content_tags or status_values:
        await db.execute(
            """INSERT OR REPLACE INTO entity_tags
               (entity_id, tag_tree_id, content_tag_ids, status_values, created_at)
               VALUES (?, '__untagged__', ?, ?, datetime('now'))""",
            (
                entity_id,
                json.dumps(content_tags, ensure_ascii=False),
                json.dumps(status_values, ensure_ascii=False),
            ),
        )
