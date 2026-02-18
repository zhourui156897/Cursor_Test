"""Embedding service: vectorize entity content and write to Milvus.

Orchestrates LLM embedding calls and Milvus storage.
"""

from __future__ import annotations

import logging

from app.services.llm_service import get_embedding, check_available
from app.storage.milvus_client import upsert_vector, delete_vector, search_vectors
from app.storage.sqlite_client import get_db

logger = logging.getLogger(__name__)

MAX_EMBED_LENGTH = 8000


def _prepare_text(title: str, content: str, max_len: int = MAX_EMBED_LENGTH) -> str:
    """Prepare text for embedding: title + content, truncated to max length."""
    text = f"{title}\n\n{content}" if title else content
    if len(text) > max_len:
        text = text[:max_len]
    return text.strip()


async def embed_entity(entity_id: str) -> bool:
    """Vectorize a single entity and store in Milvus.

    Reads entity from SQLite, generates embedding via LLM API,
    stores in Milvus, and updates entity.milvus_id in SQLite.

    Returns True if successful, False otherwise.
    """
    llm_ok = await check_available()
    if not llm_ok:
        logger.warning("LLM unavailable, cannot embed entity %s", entity_id)
        return False

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, title, content, source, content_type FROM entities WHERE id = ?",
        (entity_id,),
    )
    entity = await cursor.fetchone()
    if entity is None:
        logger.warning("Entity %s not found for embedding", entity_id)
        return False

    entity = dict(entity)
    text = _prepare_text(entity["title"] or "", entity["content"] or "")
    if not text:
        logger.warning("Entity %s has no content to embed", entity_id)
        return False

    try:
        embedding = await get_embedding(text)

        await upsert_vector(
            entity_id=entity_id,
            embedding=embedding,
            text_preview=text[:500],
            source=entity["source"],
            extra_fields={"content_type": entity["content_type"] or "text"},
        )

        await db.execute(
            "UPDATE entities SET milvus_id = ?, synced_at = datetime('now') WHERE id = ?",
            (entity_id, entity_id),
        )
        await db.commit()
        logger.info("Embedded entity %s (%d dims)", entity_id, len(embedding))
        return True

    except Exception as e:
        logger.error("Failed to embed entity %s: %s", entity_id, e)
        return False


async def embed_entities_batch(entity_ids: list[str]) -> dict:
    """Embed multiple entities. Returns {success: int, failed: int, skipped: int}."""
    result = {"success": 0, "failed": 0, "skipped": 0}
    for eid in entity_ids:
        ok = await embed_entity(eid)
        if ok:
            result["success"] += 1
        else:
            result["failed"] += 1
    return result


async def semantic_search(
    query: str,
    top_k: int = 10,
    source_filter: str | None = None,
) -> list[dict]:
    """Search entities by semantic similarity.

    Returns list of {entity_id, distance, text_preview, source, title, content}.
    """
    llm_ok = await check_available()
    if not llm_ok:
        logger.warning("LLM unavailable for semantic search")
        return []

    try:
        query_embedding = await get_embedding(query)
    except Exception as e:
        logger.error("Failed to get query embedding: %s", e)
        return []

    filters = None
    if source_filter:
        filters = f'source == "{source_filter}"'

    hits = await search_vectors(query_embedding, top_k=top_k, filters=filters)

    db = await get_db()
    enriched = []
    for hit in hits:
        cursor = await db.execute(
            "SELECT title, content, source, obsidian_path FROM entities WHERE id = ?",
            (hit["entity_id"],),
        )
        row = await cursor.fetchone()
        entry = {**hit}
        if row:
            row = dict(row)
            entry["title"] = row["title"]
            entry["content"] = row["content"][:500] if row["content"] else ""
            entry["obsidian_path"] = row["obsidian_path"]
        enriched.append(entry)

    return enriched


async def remove_entity_embedding(entity_id: str) -> None:
    """Remove an entity's vector from Milvus."""
    try:
        await delete_vector(entity_id)
        db = await get_db()
        await db.execute("UPDATE entities SET milvus_id = NULL WHERE id = ?", (entity_id,))
        await db.commit()
    except Exception as e:
        logger.error("Failed to remove embedding for %s: %s", entity_id, e)
