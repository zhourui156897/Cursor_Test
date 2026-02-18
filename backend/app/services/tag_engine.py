"""LLM-powered tag suggestion engine.

Analyzes entity content and suggests folder tags, content tags,
and status values based on the user's configured tag system.
"""

from __future__ import annotations

import json
import logging

from app.services.llm_service import chat_completion
from app.storage.sqlite_client import get_db

logger = logging.getLogger(__name__)


async def _load_tag_system() -> dict:
    """Load the current tag system from the database for prompt injection."""
    db = await get_db()

    cursor = await db.execute("SELECT id, name, path FROM tag_tree ORDER BY path")
    tree_tags = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute("SELECT id, name FROM content_tags ORDER BY name")
    content_tags = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute("SELECT key, display_name, options FROM status_dimensions")
    status_dims = []
    for r in await cursor.fetchall():
        d = dict(r)
        opts = d["options"]
        if isinstance(opts, str):
            opts = json.loads(opts)
        status_dims.append({"key": d["key"], "display_name": d["display_name"], "options": opts})

    return {
        "folder_tags": [t["path"] for t in tree_tags],
        "content_tags": [t["name"] for t in content_tags],
        "status_dimensions": status_dims,
    }


def _build_system_prompt(tag_system: dict) -> str:
    folders = "\n".join(f"  - {p}" for p in tag_system["folder_tags"]) or "  (暂无)"
    content = ", ".join(tag_system["content_tags"]) or "(暂无)"
    status_parts = []
    for dim in tag_system["status_dimensions"]:
        opts = ", ".join(dim["options"])
        status_parts.append(f"  - {dim['display_name']} ({dim['key']}): [{opts}]")
    status = "\n".join(status_parts) or "  (暂无)"

    return f"""你是一个智能标签分析助手。你的任务是分析用户的笔记/待办/日历内容，然后从用户已定义的标签体系中推荐最合适的标签。

## 用户的标签体系

### 树形文件夹标签（选择最匹配的1-2个路径）：
{folders}

### 内容标签（选择1-3个最相关的）：
{content}

### 状态维度（为每个维度选择一个值）：
{status}

## 输出要求

严格输出JSON格式，不要输出其他内容：
{{
  "folder_tags": ["路径1"],
  "content_tags": ["标签1", "标签2"],
  "status": {{"维度key": "值"}},
  "confidence": {{
    "folder_tags": {{"路径1": 0.85}},
    "content_tags": {{"标签1": 0.9, "标签2": 0.7}},
    "status": {{"维度key": 0.8}}
  }},
  "summary": "一句话摘要"
}}

规则：
1. 只能从上面列出的标签中选择，不要自创标签
2. 每个标签附带 0-1 的置信度分数
3. 如果没有合适的标签，对应数组留空
4. summary 用一句中文概括内容要点"""


async def suggest_tags(
    title: str,
    content: str,
    source: str = "",
    metadata: dict | None = None,
) -> dict:
    """Call LLM to suggest tags for an entity.

    Returns dict with keys: folder_tags, content_tags, status, confidence, summary.
    """
    tag_system = await _load_tag_system()

    if not tag_system["folder_tags"] and not tag_system["content_tags"]:
        return {
            "folder_tags": [],
            "content_tags": [],
            "status": {},
            "confidence": {},
            "summary": title or "",
        }

    system_prompt = _build_system_prompt(tag_system)

    user_content = f"标题: {title}\n来源: {source}\n\n内容:\n{content[:3000]}"
    if metadata:
        user_content += f"\n\n元数据: {json.dumps(metadata, ensure_ascii=False)[:500]}"

    try:
        result_text = await chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        suggestion = json.loads(result_text)
        _validate_suggestion(suggestion, tag_system)
        return suggestion

    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for tag suggestion, trying to extract...")
        return _fallback_parse(title)
    except Exception as e:
        logger.error("Tag suggestion failed: %s", e)
        return {
            "folder_tags": [],
            "content_tags": [],
            "status": {},
            "confidence": {},
            "summary": title or "",
            "error": str(e),
        }


def _validate_suggestion(suggestion: dict, tag_system: dict):
    """Remove any tags that don't exist in the user's system."""
    valid_folders = set(tag_system["folder_tags"])
    valid_content = set(tag_system["content_tags"])
    valid_status_keys = {d["key"] for d in tag_system["status_dimensions"]}
    valid_status_values = {d["key"]: set(d["options"]) for d in tag_system["status_dimensions"]}

    suggestion["folder_tags"] = [t for t in suggestion.get("folder_tags", []) if t in valid_folders]
    suggestion["content_tags"] = [t for t in suggestion.get("content_tags", []) if t in valid_content]

    clean_status = {}
    for k, v in suggestion.get("status", {}).items():
        if k in valid_status_keys and v in valid_status_values.get(k, set()):
            clean_status[k] = v
    suggestion["status"] = clean_status


def _fallback_parse(title: str) -> dict:
    return {
        "folder_tags": [],
        "content_tags": [],
        "status": {},
        "confidence": {},
        "summary": title or "",
    }
