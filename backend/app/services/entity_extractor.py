"""Entity and relationship extraction service.

Uses LLM to extract structured entities (people, places, projects, concepts)
and relationships from content, then writes them to Neo4j.
"""

from __future__ import annotations

import json
import logging

from app.services.llm_service import chat_completion, check_available
from app.storage.neo4j_client import (
    create_entity_node,
    create_relationship,
    is_available as neo4j_available,
)
from app.storage.sqlite_client import get_db

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是一个知识图谱实体关系抽取助手。请从给定内容中抽取实体和关系。

## 实体类型（仅选以下类型）
- PERSON: 人物
- PLACE: 地点
- PROJECT: 项目/计划
- CONCEPT: 概念/主题
- ORGANIZATION: 组织/公司
- EVENT: 事件
- TIME: 时间点/时间段

## 关系类型（仅选以下类型）
- BELONGS_TO: 属于
- PARTICIPATES_IN: 参与
- RELATED_TO: 关联
- LOCATED_AT: 位于
- CREATED_BY: 创建者
- HAPPENED_AT: 发生于
- PART_OF: 属于（部分）
- DEPENDS_ON: 依赖

## 输出格式
严格输出JSON，不要输出其他内容：
{
  "entities": [
    {"name": "实体名", "type": "PERSON/PLACE/...", "description": "简短描述"}
  ],
  "relationships": [
    {"from": "实体名1", "to": "实体名2", "type": "RELATED_TO", "description": "关系描述"}
  ]
}

规则：
1. 只抽取明确存在于内容中的实体，不要臆造
2. 实体名使用内容中的原始称呼
3. 每条关系必须连接两个已抽取的实体
4. 如果内容过短或无有意义的实体，返回空数组
5. 最多抽取10个实体和15条关系"""


async def extract_and_store(entity_id: str) -> dict:
    """Extract entities/relationships from an entity's content and store in Neo4j.

    Returns extraction result summary.
    """
    llm_ok = await check_available()
    if not llm_ok:
        return {"status": "skipped", "reason": "LLM unavailable"}

    neo4j_ok = await neo4j_available()
    if not neo4j_ok:
        return {"status": "skipped", "reason": "Neo4j unavailable"}

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, title, content, source, content_type FROM entities WHERE id = ?",
        (entity_id,),
    )
    entity = await cursor.fetchone()
    if entity is None:
        return {"status": "error", "reason": "Entity not found"}

    entity = dict(entity)
    title = entity["title"] or ""
    content = entity["content"] or ""

    if len(content.strip()) < 20:
        return {"status": "skipped", "reason": "Content too short"}

    source_node_id = await create_entity_node(
        entity_id=entity_id,
        title=title,
        source=entity["source"],
        content_type=entity["content_type"] or "text",
    )

    if source_node_id:
        await db.execute(
            "UPDATE entities SET neo4j_node_id = ? WHERE id = ?",
            (source_node_id, entity_id),
        )
        await db.commit()

    try:
        extraction = await _llm_extract(title, content)
    except Exception as e:
        logger.error("LLM extraction failed for entity %s: %s", entity_id, e)
        return {"status": "partial", "source_node": source_node_id, "extraction_error": str(e)}

    entities_created = 0
    rels_created = 0

    entity_name_to_id: dict[str, str] = {title: entity_id}

    for ext_entity in extraction.get("entities", []):
        name = ext_entity.get("name", "")
        if not name or name == title:
            continue

        sub_id = f"{entity_id}::{name}"
        node_id = await create_entity_node(
            entity_id=sub_id,
            title=name,
            source="extraction",
            content_type=ext_entity.get("type", "CONCEPT").lower(),
            extra_props={
                "entity_type": ext_entity.get("type", "CONCEPT"),
                "description": ext_entity.get("description", ""),
                "parent_entity": entity_id,
            },
        )
        if node_id:
            entity_name_to_id[name] = sub_id
            entities_created += 1

    for rel in extraction.get("relationships", []):
        from_name = rel.get("from", "")
        to_name = rel.get("to", "")
        rel_type = rel.get("type", "RELATED_TO")

        from_id = entity_name_to_id.get(from_name)
        to_id = entity_name_to_id.get(to_name)

        if from_id and to_id:
            ok = await create_relationship(
                from_id, to_id, rel_type,
                properties={"description": rel.get("description", "")},
            )
            if ok:
                rels_created += 1

    logger.info(
        "Extracted for entity %s: %d entities, %d relationships",
        entity_id, entities_created, rels_created,
    )

    return {
        "status": "success",
        "source_node": source_node_id,
        "entities_created": entities_created,
        "relationships_created": rels_created,
    }


async def _llm_extract(title: str, content: str) -> dict:
    """Call LLM to extract entities and relationships."""
    truncated = content[:3000]
    user_msg = f"标题: {title}\n\n内容:\n{truncated}"

    try:
        result_text = await chat_completion(
            [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for extraction")
        return {"entities": [], "relationships": []}
    except Exception as e:
        logger.error("LLM extraction call failed: %s", e)
        raise


async def extract_batch(entity_ids: list[str]) -> dict:
    """Extract entities/relationships for multiple entities."""
    result = {"success": 0, "skipped": 0, "failed": 0}
    for eid in entity_ids:
        try:
            res = await extract_and_store(eid)
            if res.get("status") == "success":
                result["success"] += 1
            elif res.get("status") == "skipped":
                result["skipped"] += 1
            else:
                result["failed"] += 1
        except Exception as e:
            logger.error("Extract failed for %s: %s", eid, e)
            result["failed"] += 1
    return result
