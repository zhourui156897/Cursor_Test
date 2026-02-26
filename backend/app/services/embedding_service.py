"""Embedding service: vectorize entity content and write to Milvus.

Orchestrates LLM embedding calls and Milvus storage.
向量化时同时写入 folder_tags / content_tags 元数据，支持按标签过滤检索。
"""

from __future__ import annotations

import json
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


async def _fetch_entity_tags(db, entity_id: str) -> tuple[list[str], list[str]]:
    """从 entity_tags + tag_tree + content_tags 联查实体的标签名列表。"""
    folder_tags: list[str] = []
    content_tags: list[str] = []

    cursor = await db.execute(
        """SELECT t.path, et.content_tag_ids
           FROM entity_tags et
           LEFT JOIN tag_tree t ON et.tag_tree_id = t.id
           WHERE et.entity_id = ?""",
        (entity_id,),
    )
    rows = await cursor.fetchall()
    for row in rows:
        row = dict(row)
        if row.get("path"):
            folder_tags.append(row["path"])
        ct_raw = row.get("content_tag_ids")
        if ct_raw:
            try:
                ct_ids = json.loads(ct_raw) if isinstance(ct_raw, str) else ct_raw
                if ct_ids:
                    placeholders = ",".join("?" for _ in ct_ids)
                    c2 = await db.execute(
                        f"SELECT name FROM content_tags WHERE id IN ({placeholders})",
                        ct_ids,
                    )
                    content_tags.extend(r["name"] for r in await c2.fetchall())
            except (json.JSONDecodeError, TypeError):
                pass

    return folder_tags, content_tags


async def embed_entity(entity_id: str) -> bool:
    """向量化单个实体并存入 Milvus（含 folder_tags / content_tags 元数据）。"""
    llm_ok = await check_available()
    if not llm_ok:
        logger.warning("LLM 不可用，无法向量化 entity %s", entity_id)
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

        folder_tags, content_tags = await _fetch_entity_tags(db, entity_id)

        await upsert_vector(
            entity_id=entity_id,
            embedding=embedding,
            text_preview=text[:500],
            source=entity["source"],
            extra_fields={
                "content_type": entity["content_type"] or "text",
                "folder_tags": json.dumps(folder_tags, ensure_ascii=False),
                "content_tags": json.dumps(content_tags, ensure_ascii=False),
            },
        )

        await db.execute(
            "UPDATE entities SET milvus_id = ?, synced_at = datetime('now') WHERE id = ?",
            (entity_id, entity_id),
        )
        await db.commit()
        logger.info("Embedded entity %s (%d dims, folders=%s, tags=%s)",
                     entity_id, len(embedding), folder_tags, content_tags)
        return True

    except Exception as e:
        logger.error("Failed to embed entity %s: %s", entity_id, e, exc_info=True)
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


async def re_embed_all_pending() -> dict:
    """补录所有已审核但未向量化的实体。返回 {total, success, failed}。"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id FROM entities WHERE review_status = 'reviewed' AND milvus_id IS NULL"
    )
    rows = await cursor.fetchall()
    ids = [r["id"] for r in rows]

    if not ids:
        return {"total": 0, "success": 0, "failed": 0, "message": "没有需要补录的实体"}

    logger.info("开始补录向量化: %d 个实体", len(ids))
    result = {"total": len(ids), "success": 0, "failed": 0}
    for i, eid in enumerate(ids, 1):
        ok = await embed_entity(eid)
        if ok:
            result["success"] += 1
        else:
            result["failed"] += 1
        if i % 10 == 0:
            logger.info("补录进度: %d/%d (成功 %d, 失败 %d)",
                        i, len(ids), result["success"], result["failed"])

    logger.info("补录完成: %s", result)
    return result


def _build_filter_expr(
    source_filter: str | None = None,
    folder_filter: str | None = None,
    tag_filter: str | None = None,
) -> str | None:
    """构造 Milvus filter 表达式（多条件用 and 连接）。"""
    parts: list[str] = []
    if source_filter:
        parts.append(f'source == "{source_filter}"')
    if folder_filter:
        parts.append(f'folder_tags like "%{folder_filter}%"')
    if tag_filter:
        parts.append(f'content_tags like "%{tag_filter}%"')
    return " and ".join(parts) if parts else None


async def semantic_search(
    query: str,
    top_k: int = 10,
    source_filter: str | None = None,
    folder_filter: str | None = None,
    tag_filter: str | None = None,
) -> list[dict]:
    """语义搜索，支持按 source / folder / content_tag 过滤。"""
    llm_ok = await check_available()
    if not llm_ok:
        logger.warning("LLM unavailable for semantic search")
        return []

    try:
        query_embedding = await get_embedding(query)
    except Exception as e:
        logger.error("Failed to get query embedding: %s", e)
        return []

    filters = _build_filter_expr(source_filter, folder_filter, tag_filter)

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
