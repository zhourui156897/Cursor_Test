"""Agent tool definitions: callable tools for the LLM agent mode.

Each tool has a schema (for function-calling) and an execute function.
Tools enable the LLM to perform actions beyond simple RAG retrieval.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.storage.sqlite_client import get_db
from app.services.embedding_service import semantic_search
from app.storage.neo4j_client import is_available as neo4j_ok, run_cypher, get_entity_relations

logger = logging.getLogger(__name__)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在知识库中搜索相关内容，支持语义搜索和关键词搜索",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询内容"},
                    "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_detail",
            "description": "获取某个知识实体的完整详情（标题、内容、标签、状态）",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": "列出知识库中的实体，可按来源或关键词过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "来源过滤: apple_notes, apple_reminders, apple_calendar, upload, manual"},
                    "keyword": {"type": "string", "description": "标题关键词过滤"},
                    "limit": {"type": "integer", "description": "返回数量限制", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_graph",
            "description": "查询知识图谱中的实体关系网络",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_title": {"type": "string", "description": "要查询关系的实体标题"},
                    "relation_type": {"type": "string", "description": "关系类型过滤 (如 RELATED_TO, MENTIONS, PART_OF)"},
                },
                "required": ["entity_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tags",
            "description": "列出当前标签体系（文件夹标签/内容标签/状态维度）",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag_type": {
                        "type": "string",
                        "enum": ["folder", "content", "status", "all"],
                        "description": "标签类型",
                        "default": "all",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_entity",
            "description": "创建一个新的知识实体笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "实体标题"},
                    "content": {"type": "string", "description": "实体内容 (Markdown)"},
                    "source": {"type": "string", "description": "来源标记", "default": "agent"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_entity_tags",
            "description": "为实体添加或修改标签",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "folder_tags": {"type": "array", "items": {"type": "string"}, "description": "文件夹标签列表"},
                    "content_tags": {"type": "array", "items": {"type": "string"}, "description": "内容标签列表"},
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_content",
            "description": "对一段内容生成摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要摘要的内容"},
                    "style": {
                        "type": "string",
                        "enum": ["brief", "detailed", "bullet_points"],
                        "description": "摘要风格",
                        "default": "brief",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "获取知识库的统计信息（实体数量、标签使用、来源分布）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool by name and return the result as a string."""
    try:
        handler = _HANDLERS.get(name)
        if not handler:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        result = await handler(arguments)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Tool execution error: %s(%s) -> %s", name, arguments, e)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ─── Tool Implementations ───


async def _search_knowledge(args: dict) -> Any:
    query = args["query"]
    top_k = args.get("top_k", 5)

    results = []
    try:
        vector_hits = await semantic_search(query, top_k=top_k)
        results.extend(vector_hits)
    except Exception:
        pass

    db = await get_db()
    cursor = await db.execute(
        """SELECT id, title, substr(content, 1, 300) as content, source
           FROM entities WHERE title LIKE ? OR content LIKE ?
           ORDER BY updated_at DESC LIMIT ?""",
        (f"%{query}%", f"%{query}%", top_k),
    )
    meta_hits = [dict(r) for r in await cursor.fetchall()]
    seen = {r["entity_id"] for r in results}
    for h in meta_hits:
        if h["id"] not in seen:
            results.append({"entity_id": h["id"], "title": h["title"], "content": h["content"], "source": h["source"]})

    return {"query": query, "count": len(results), "results": results[:top_k]}


async def _get_entity_detail(args: dict) -> Any:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (args["entity_id"],))
    row = await cursor.fetchone()
    if not row:
        return {"error": "实体不存在"}
    entity = dict(row)

    cursor = await db.execute(
        "SELECT tag_id FROM entity_tags WHERE entity_id = ?", (args["entity_id"],)
    )
    tags = [r["tag_id"] for r in await cursor.fetchall()]
    entity["tags"] = tags
    return entity


async def _list_entities(args: dict) -> Any:
    db = await get_db()
    conditions = []
    params: list = []

    if args.get("source"):
        conditions.append("source = ?")
        params.append(args["source"])
    if args.get("keyword"):
        conditions.append("title LIKE ?")
        params.append(f"%{args['keyword']}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit = args.get("limit", 10)
    params.append(limit)

    cursor = await db.execute(
        f"SELECT id, title, source, review_status, created_at FROM entities {where} ORDER BY updated_at DESC LIMIT ?",
        params,
    )
    return {"entities": [dict(r) for r in await cursor.fetchall()]}


async def _query_graph(args: dict) -> Any:
    if not await neo4j_ok():
        return {"error": "知识图谱不可用"}

    title = args["entity_title"]
    rel_filter = args.get("relation_type", "")

    rel_clause = f"AND type(r) = '{rel_filter}'" if rel_filter else ""
    cypher = f"""
        MATCH (e:Entity)-[r]-(related:Entity)
        WHERE e.title CONTAINS $title {rel_clause}
        RETURN e.title as entity, type(r) as relation, related.title as related_entity
        LIMIT 20
    """
    results = await run_cypher(cypher, {"title": title})
    return {"entity": title, "relations": results or []}


async def _list_tags(args: dict) -> Any:
    db = await get_db()
    tag_type = args.get("tag_type", "all")
    result: dict[str, Any] = {}

    if tag_type in ("folder", "all"):
        cursor = await db.execute("SELECT id, name, parent_id, path FROM tag_tree ORDER BY sort_order")
        result["folder_tags"] = [dict(r) for r in await cursor.fetchall()]

    if tag_type in ("content", "all"):
        cursor = await db.execute("SELECT id, name, color, usage_count FROM content_tags ORDER BY usage_count DESC")
        result["content_tags"] = [dict(r) for r in await cursor.fetchall()]

    if tag_type in ("status", "all"):
        cursor = await db.execute("SELECT id, key, display_name, options, default_value FROM status_dimensions")
        rows = await cursor.fetchall()
        result["status_dimensions"] = []
        for r in rows:
            d = dict(r)
            try:
                d["options"] = json.loads(d["options"]) if isinstance(d["options"], str) else d["options"]
            except Exception:
                pass
            result["status_dimensions"].append(d)

    return result


async def _create_entity(args: dict) -> Any:
    import uuid
    from datetime import datetime

    db = await get_db()
    entity_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    await db.execute(
        """INSERT INTO entities (id, source, title, content, content_type, current_version,
           review_status, created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, 'text/markdown', 1, 'pending', ?, ?, 'agent')""",
        (entity_id, args.get("source", "agent"), args["title"], args["content"], now, now),
    )
    await db.execute(
        "INSERT INTO entity_versions (id, entity_id, version_number, title, content, change_source, created_at) VALUES (?, ?, 1, ?, ?, 'agent', ?)",
        (str(uuid.uuid4()), entity_id, args["title"], args["content"], now),
    )
    await db.commit()
    return {"entity_id": entity_id, "title": args["title"], "status": "created"}


async def _update_entity_tags(args: dict) -> Any:
    db = await get_db()
    entity_id = args["entity_id"]

    cursor = await db.execute("SELECT id FROM entities WHERE id = ?", (entity_id,))
    if not await cursor.fetchone():
        return {"error": "实体不存在"}

    added = []

    if args.get("folder_tags"):
        for tag_name in args["folder_tags"]:
            cursor = await db.execute("SELECT id FROM tag_tree WHERE name = ?", (tag_name,))
            row = await cursor.fetchone()
            if row:
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO entity_tags (entity_id, tag_id, tag_type) VALUES (?, ?, 'folder')",
                        (entity_id, row["id"]),
                    )
                    added.append(f"folder:{tag_name}")
                except Exception:
                    pass

    if args.get("content_tags"):
        for tag_name in args["content_tags"]:
            cursor = await db.execute("SELECT id FROM content_tags WHERE name = ?", (tag_name,))
            row = await cursor.fetchone()
            if row:
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO entity_tags (entity_id, tag_id, tag_type) VALUES (?, ?, 'content')",
                        (entity_id, row["id"]),
                    )
                    added.append(f"content:{tag_name}")
                except Exception:
                    pass

    await db.commit()
    return {"entity_id": entity_id, "tags_added": added}


async def _summarize_content(args: dict) -> Any:
    from app.services.llm_service import chat_completion

    style_map = {
        "brief": "用1-2句话简要概括以下内容：",
        "detailed": "详细总结以下内容的要点：",
        "bullet_points": "用要点列表（bullet points）概括以下内容：",
    }
    prompt = style_map.get(args.get("style", "brief"), style_map["brief"])

    result = await chat_completion(
        [{"role": "user", "content": f"{prompt}\n\n{args['content'][:3000]}"}],
        temperature=0.3,
        max_tokens=1024,
    )
    return {"summary": result}


async def _get_statistics(args: dict) -> Any:
    db = await get_db()

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM entities")
    total = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT source, COUNT(*) as cnt FROM entities GROUP BY source ORDER BY cnt DESC"
    )
    by_source = {r["source"]: r["cnt"] for r in await cursor.fetchall()}

    cursor = await db.execute(
        "SELECT review_status, COUNT(*) as cnt FROM entities GROUP BY review_status"
    )
    by_status = {r["review_status"]: r["cnt"] for r in await cursor.fetchall()}

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM content_tags")
    tag_count = (await cursor.fetchone())["cnt"]

    return {
        "total_entities": total,
        "by_source": by_source,
        "by_review_status": by_status,
        "content_tag_count": tag_count,
    }


_HANDLERS = {
    "search_knowledge": _search_knowledge,
    "get_entity_detail": _get_entity_detail,
    "list_entities": _list_entities,
    "query_graph": _query_graph,
    "list_tags": _list_tags,
    "create_entity": _create_entity,
    "update_entity_tags": _update_entity_tags,
    "summarize_content": _summarize_content,
    "get_statistics": _get_statistics,
}
