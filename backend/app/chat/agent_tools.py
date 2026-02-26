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
from app.sync.messages import APPLE_JXA_USER_MESSAGE

logger = logging.getLogger(__name__)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在知识库中搜索相关内容，支持语义向量搜索和关键词搜索。可按文件夹标签或内容标签过滤，缩小搜索范围。当用户问知识相关问题时，优先使用本工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询内容"},
                    "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
                    "folder_tag": {"type": "string", "description": "按文件夹标签过滤（如 '领域/技术'、'项目/创业'）"},
                    "content_tag": {"type": "string", "description": "按内容标签过滤（如 '学习'、'研究'、'想法'）"},
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
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "获取服务器当前日期时间（ISO 格式）。当用户说「今天」「明天」「下午3点」等相对时间时，必须先调用本工具得到当前时间，再计算 start_date/end_date/due_date，严禁猜测或使用 2023 等错误年份。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ─── Apple 三件套：实时读取（从系统 App 拉取，非数据库） ───
    {
        "type": "function",
        "function": {
            "name": "fetch_apple_data",
            "description": "从用户 Mac 上的 Apple 备忘录/待办/日历实时读取最新数据（不经过知识库），用于总结、查看最新内容。需指定来源。日历可指定时间范围，待办可指定截止范围。涉及「今天」「明天」等请先调用 get_current_datetime。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["apple_notes", "apple_reminders", "apple_calendar"],
                        "description": "数据来源: apple_notes 备忘录, apple_reminders 待办, apple_calendar 日历",
                    },
                    "limit": {"type": "integer", "description": "最多返回条数", "default": 20},
                    "order": {
                        "type": "string",
                        "enum": ["newest", "oldest"],
                        "description": "排序: newest 由新到旧, oldest 由旧到新",
                        "default": "newest",
                    },
                    "days_back": {"type": "integer", "description": "仅日历: 从今天往前多少天内的事件，如 0 表示只看今天及以后", "default": 0},
                    "days_forward": {"type": "integer", "description": "仅日历: 从今天往后多少天内的事件，如 1 表示包含明天", "default": 7},
                    "due_after": {"type": "string", "description": "仅待办: 只返回截止日期不早于此的，ISO 日期如 2026-02-20。查「明天待办」时设为明天日期。"},
                    "due_before": {"type": "string", "description": "仅待办: 只返回截止日期不晚于此的，ISO 日期如 2026-02-21。"},
                },
                "required": ["source"],
            },
        },
    },
    # ─── Apple 三件套：写入（真正在系统 App 中创建） ───
    {
        "type": "function",
        "function": {
            "name": "create_apple_note",
            "description": "在用户 Mac 的「备忘录」App 中创建一条新备忘录。仅当用户明确要求创建备忘录时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "备忘录标题"},
                    "body": {"type": "string", "description": "备忘录正文内容", "default": ""},
                    "folder": {"type": "string", "description": "文件夹名称（可选，为空则默认文件夹）", "default": ""},
                    "add_to_knowledge_base": {"type": "boolean", "description": "是否同时记入第二大脑知识库便于检索", "default": True},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_apple_reminder",
            "description": "在用户 Mac 的「提醒事项」App 中创建一条新待办。仅当用户明确要求创建待办/提醒时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "待办标题"},
                    "body": {"type": "string", "description": "备注内容", "default": ""},
                    "list_name": {"type": "string", "description": "列表名称（可选）", "default": ""},
                    "due_date": {"type": "string", "description": "截止时间 ISO 格式，如 2026-02-20T09:00:00", "default": ""},
                    "priority": {"type": "integer", "description": "优先级 0无 1高 5中 9低", "default": 0},
                    "add_to_knowledge_base": {"type": "boolean", "description": "是否同时记入第二大脑知识库", "default": True},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_apple_event",
            "description": "在用户 Mac 的「日历」App 中创建一条新日历事件。仅当用户明确要求创建日历/日程时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "事件标题"},
                    "start_date": {"type": "string", "description": "开始时间 ISO 格式，如 2026-02-20T09:00:00"},
                    "end_date": {"type": "string", "description": "结束时间 ISO 格式"},
                    "description": {"type": "string", "description": "事件描述", "default": ""},
                    "location": {"type": "string", "description": "地点", "default": ""},
                    "calendar": {"type": "string", "description": "日历名称（可选）", "default": ""},
                    "all_day": {"type": "boolean", "description": "是否全天", "default": False},
                    "add_to_knowledge_base": {"type": "boolean", "description": "是否同时记入第二大脑知识库", "default": True},
                },
                "required": ["title", "start_date", "end_date"],
            },
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
    folder_tag = args.get("folder_tag")
    content_tag = args.get("content_tag")

    results = []
    try:
        vector_hits = await semantic_search(
            query, top_k=top_k,
            folder_filter=folder_tag,
            tag_filter=content_tag,
        )
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


async def _get_current_datetime(_args: dict) -> Any:
    """返回当前日期时间，供 Agent 计算「今天」「明天」等。"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # 也返回本地时间常用格式，便于 LLM 理解
    try:
        import zoneinfo
        local = now.astimezone(zoneinfo.ZoneInfo("Asia/Shanghai"))
    except Exception:
        local = now
    return {
        "iso_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "iso_local": local.strftime("%Y-%m-%dT%H:%M:%S"),
        "date_only": local.strftime("%Y-%m-%d"),
        "weekday_cn": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][local.weekday()],
        "hint": "创建日历/待办时，start_date/end_date/due_date 请用与 iso_local 同格式的日期时间，例如今天下午3点即 date_only + 'T15:00:00'",
    }


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


# ─── Apple 三件套：实时读取 ───


async def _fetch_apple_data(args: dict) -> Any:
    """从 Mac 上的 Apple 备忘录/待办/日历实时拉取数据（JXA），返回给 Agent 用于总结或回答。"""
    source = args.get("source", "")
    limit = args.get("limit", 10)
    order = args.get("order", "newest")
    try:
        return await _fetch_apple_data_impl(args, source, limit, order)
    except Exception as e:
        logger.exception("fetch_apple_data failed: %s", e)
        return {"error": APPLE_JXA_USER_MESSAGE}


async def _fetch_apple_data_impl(args: dict, source: str, limit: int, order: str) -> Any:
    if source == "apple_notes":
        from app.sync.apple_notes import fetch_all_notes
        notes = await fetch_all_notes(limit=min(limit, 50), order=order)
        return {
            "source": "apple_notes",
            "count": len(notes),
            "items": [
                {
                    "id": n.id,
                    "title": n.name,
                    "content_preview": (n.body_text or "")[:500],
                    "folder": getattr(n, "folder", ""),
                    "created": getattr(n, "creation_date", ""),
                    "modified": getattr(n, "modification_date", ""),
                }
                for n in notes
            ],
        }
    if source == "apple_reminders":
        from app.sync.apple_reminders import fetch_all_reminders
        due_after = (args.get("due_after") or "").strip() or None
        due_before = (args.get("due_before") or "").strip() or None
        reminders = await fetch_all_reminders(
            limit=min(limit, 50), order=order,
            due_after=due_after, due_before=due_before,
        )
        return {
            "source": "apple_reminders",
            "count": len(reminders),
            "items": [
                {
                    "id": r.id,
                    "title": r.name,
                    "body": (r.body or "")[:200],
                    "list": r.list_name,
                    "completed": r.completed,
                    "due_date": r.due_date,
                    "priority": r.priority,
                    "modified": r.modification_date,
                }
                for r in reminders
            ],
        }
    if source == "apple_calendar":
        from app.sync.apple_calendar import fetch_all_events
        days_back = int(args.get("days_back", 0))
        days_forward = int(args.get("days_forward", 7))
        events = await fetch_all_events(
            limit=min(limit, 50), order=order,
            days_back=max(0, days_back), days_forward=max(0, days_forward),
        )
        return {
            "source": "apple_calendar",
            "count": len(events),
            "items": [
                {
                    "id": e.id,
                    "title": e.summary,
                    "start": e.start_date,
                    "end": e.end_date,
                    "location": e.location,
                    "calendar": e.calendar_name,
                    "all_day": e.all_day,
                }
                for e in events
            ],
        }
    return {"error": "source 必须是 apple_notes / apple_reminders / apple_calendar"}


# ─── Apple 三件套：写入（真正调用系统 App） ───


async def _create_apple_note(args: dict) -> Any:
    try:
        return await _create_apple_note_impl(args)
    except Exception as e:
        logger.exception("create_apple_note failed: %s", e)
        return {"success": False, "error": APPLE_JXA_USER_MESSAGE}


async def _create_apple_note_impl(args: dict) -> Any:
    from app.sync.apple_notes import create_note
    title = (args.get("title") or "").strip() or "新备忘录"
    body = (args.get("body") or "")
    folder = (args.get("folder") or "")
    result = await create_note(title=title, body=body, folder=folder)
    out = {"success": True, "message": "已在「备忘录」中创建", "result": result}
    if args.get("add_to_knowledge_base", True):
        try:
            from app.sync.ingest_pipeline import ingest_entity
            await ingest_entity(
                title=title, content=body or f"[由 Agent 在 Apple 备忘录创建]",
                source="agent_apple_notes", created_by="agent", skip_llm=True,
            )
            out["knowledge_base"] = "已记入第二大脑知识库"
        except Exception as e:
            logger.warning("Agent create_apple_note: ingest failed %s", e)
    return out


async def _create_apple_reminder(args: dict) -> Any:
    try:
        return await _create_apple_reminder_impl(args)
    except Exception as e:
        logger.exception("create_apple_reminder failed: %s", e)
        return {"success": False, "error": APPLE_JXA_USER_MESSAGE}


async def _create_apple_reminder_impl(args: dict) -> Any:
    from app.sync.apple_reminders import create_reminder
    title = (args.get("title") or "").strip() or "新提醒"
    body = (args.get("body") or "")
    due = (args.get("due_date") or "")
    result = await create_reminder(
        title=title, body=body,
        list_name=(args.get("list_name") or ""),
        due_date=due, priority=int(args.get("priority") or 0),
    )
    out = {"success": True, "message": "已在「提醒事项」中创建", "result": result}
    if args.get("add_to_knowledge_base", True):
        try:
            from app.sync.ingest_pipeline import ingest_entity
            content = body or f"截止: {due}" if due else "[由 Agent 在 Apple 提醒事项创建]"
            await ingest_entity(
                title=title, content=content, source="agent_apple_reminders",
                created_by="agent", skip_llm=True,
            )
            out["knowledge_base"] = "已记入第二大脑知识库"
        except Exception as e:
            logger.warning("Agent create_apple_reminder: ingest failed %s", e)
    return out


async def _create_apple_event(args: dict) -> Any:
    title = (args.get("title") or "").strip() or "新事件"
    start = (args.get("start_date") or "").strip()
    end = (args.get("end_date") or "").strip()
    if not start or not end:
        return {"success": False, "error": "start_date 和 end_date 必填，请使用 ISO 格式如 2026-02-20T09:00:00。用户说「今天」时请先调用 get_current_datetime。"}
    if start.startswith("2023") or (start.startswith("2024") and start < "2025-01-01"):
        return {"success": False, "error": "start_date 不能使用过往年份。请先调用 get_current_datetime 获取当前日期后再计算 start_date/end_date。"}
    try:
        return await _create_apple_event_impl(args, title, start, end)
    except Exception as e:
        logger.exception("create_apple_event failed: %s", e)
        return {"success": False, "error": APPLE_JXA_USER_MESSAGE}


async def _create_apple_event_impl(args: dict, title: str, start: str, end: str) -> Any:
    from app.sync.apple_calendar import create_event
    desc = (args.get("description") or "")
    loc = (args.get("location") or "")
    result = await create_event(
        title=title, start_date=start, end_date=end,
        description=desc, location=loc, calendar=(args.get("calendar") or ""),
        all_day=bool(args.get("all_day")),
    )
    out = {"success": True, "message": "已在「日历」中创建", "result": result}
    if args.get("add_to_knowledge_base", True):
        try:
            from app.sync.ingest_pipeline import ingest_entity
            content = f"{start} ~ {end}"
            if desc:
                content += f"\n\n{desc}"
            if loc:
                content += f"\n地点: {loc}"
            await ingest_entity(
                title=title, content=content, source="agent_apple_calendar",
                created_by="agent", skip_llm=True,
            )
            out["knowledge_base"] = "已记入第二大脑知识库"
        except Exception as e:
            logger.warning("Agent create_apple_event: ingest failed %s", e)
    return out


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
    "get_current_datetime": _get_current_datetime,
    "fetch_apple_data": _fetch_apple_data,
    "create_apple_note": _create_apple_note,
    "create_apple_reminder": _create_apple_reminder,
    "create_apple_event": _create_apple_event,
}
