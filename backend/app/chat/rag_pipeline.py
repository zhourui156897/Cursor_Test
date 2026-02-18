"""RAG pipeline: query rewrite -> hybrid retrieval -> context building -> LLM generation.

Implements the core retrieval-augmented generation flow for the Q&A system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.llm_service import chat_completion, check_available
from app.services.embedding_service import semantic_search
from app.storage.neo4j_client import is_available as neo4j_available, run_cypher
from app.storage.sqlite_client import get_db

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    entity_id: str
    title: str
    content: str
    source: str
    score: float = 0.0
    match_type: str = "vector"


@dataclass
class RAGContext:
    query: str
    rewritten_query: str
    results: list[RetrievalResult] = field(default_factory=list)
    graph_context: str = ""
    answer: str = ""
    sources: list[dict] = field(default_factory=list)


async def run_rag(
    query: str,
    history: list[dict] | None = None,
    top_k: int = 5,
) -> RAGContext:
    """Execute the full RAG pipeline."""
    ctx = RAGContext(query=query, rewritten_query=query)

    if not await check_available():
        ctx.answer = "LLM 服务不可用，无法生成回答。请检查 LLM API 配置。"
        return ctx

    if history:
        ctx.rewritten_query = await _rewrite_query(query, history)

    ctx.results = await _hybrid_retrieve(ctx.rewritten_query, top_k)

    graph_ctx = await _graph_retrieve(ctx.rewritten_query)
    ctx.graph_context = graph_ctx

    answer, sources = await _generate_answer(ctx)
    ctx.answer = answer
    ctx.sources = sources

    return ctx


async def _rewrite_query(query: str, history: list[dict]) -> str:
    """Rewrite query using conversation history for coreference resolution."""
    recent = history[-6:]
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
        for m in recent
    )

    try:
        result = await chat_completion(
            [
                {"role": "system", "content": (
                    "你是查询改写助手。根据对话历史，改写用户的最新问题使其成为独立的、完整的查询。"
                    "如果问题已经完整，原样返回。只输出改写后的查询，不要其他内容。"
                )},
                {"role": "user", "content": f"对话历史:\n{history_text}\n\n最新问题: {query}\n\n改写后的查询:"},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        rewritten = result.strip()
        if rewritten:
            logger.debug("Query rewritten: '%s' -> '%s'", query, rewritten)
            return rewritten
    except Exception as e:
        logger.warning("Query rewrite failed: %s", e)

    return query


async def _hybrid_retrieve(query: str, top_k: int) -> list[RetrievalResult]:
    """Hybrid retrieval: vector search + metadata search, merged with RRF."""
    results: list[RetrievalResult] = []

    try:
        vector_hits = await semantic_search(query, top_k=top_k * 2)
        for i, hit in enumerate(vector_hits):
            results.append(RetrievalResult(
                entity_id=hit["entity_id"],
                title=hit.get("title", ""),
                content=hit.get("content", ""),
                source=hit.get("source", ""),
                score=1.0 / (60 + i + 1),
                match_type="vector",
            ))
    except Exception as e:
        logger.warning("Vector search failed: %s", e)

    try:
        meta_hits = await _metadata_search(query, top_k=top_k)
        seen = {r.entity_id for r in results}
        for i, hit in enumerate(meta_hits):
            eid = hit["id"]
            if eid in seen:
                for r in results:
                    if r.entity_id == eid:
                        r.score += 1.0 / (60 + i + 1)
                        break
            else:
                results.append(RetrievalResult(
                    entity_id=eid,
                    title=hit.get("title", ""),
                    content=hit.get("content", ""),
                    source=hit.get("source", ""),
                    score=1.0 / (60 + i + 1),
                    match_type="metadata",
                ))
    except Exception as e:
        logger.warning("Metadata search failed: %s", e)

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_k]


async def _metadata_search(query: str, top_k: int = 10) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, title, substr(content, 1, 500) as content, source
           FROM entities
           WHERE title LIKE ? OR content LIKE ?
           ORDER BY updated_at DESC LIMIT ?""",
        (f"%{query}%", f"%{query}%", top_k),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def _graph_retrieve(query: str) -> str:
    """Query the knowledge graph for related entities."""
    if not await neo4j_available():
        return ""

    try:
        results = await run_cypher(
            """MATCH (e:Entity)
               WHERE e.title CONTAINS $query
               OPTIONAL MATCH (e)-[r]-(related:Entity)
               RETURN e.title as entity, type(r) as relation, related.title as related_entity
               LIMIT 20""",
            {"query": query[:50]},
        )

        if not results:
            return ""

        lines = []
        for r in results:
            entity = r.get("entity", "")
            rel = r.get("relation", "")
            related = r.get("related_entity", "")
            if rel and related:
                lines.append(f"- {entity} --[{rel}]--> {related}")
            elif entity:
                lines.append(f"- {entity}")

        return "知识图谱关联:\n" + "\n".join(lines) if lines else ""
    except Exception as e:
        logger.warning("Graph retrieval failed: %s", e)
        return ""


async def _generate_answer(ctx: RAGContext) -> tuple[str, list[dict]]:
    """Build context and generate LLM answer with source citations."""
    context_parts = []
    sources = []

    for i, r in enumerate(ctx.results):
        context_parts.append(f"[来源{i+1}] {r.title}\n{r.content[:600]}")
        sources.append({
            "index": i + 1,
            "entity_id": r.entity_id,
            "title": r.title,
            "source": r.source,
        })

    if ctx.graph_context:
        context_parts.append(ctx.graph_context)

    context_text = "\n\n".join(context_parts) if context_parts else "（未找到相关内容）"

    system_prompt = """你是"第二大脑"智能助手，帮助用户在个人知识库中查找和理解信息。

规则：
1. 基于提供的参考资料回答问题，不要编造信息
2. 引用来源时使用 [来源N] 格式
3. 如果参考资料不足以回答问题，坦诚告知
4. 用中文回答，简洁清晰
5. 如果用户的问题和知识库无关，友好地提示"""

    user_prompt = f"""参考资料：
{context_text}

用户问题：{ctx.query}"""

    try:
        answer = await chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        return answer, sources
    except Exception as e:
        logger.error("Answer generation failed: %s", e)
        return f"生成回答时出错: {e}", sources
