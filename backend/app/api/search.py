"""Semantic search API: hybrid retrieval across Milvus + Neo4j + SQLite."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.embedding_service import semantic_search
from app.storage.sqlite_client import get_db

router = APIRouter()


class SearchResult(BaseModel):
    entity_id: str
    title: str | None = None
    content: str | None = None
    source: str | None = None
    obsidian_path: str | None = None
    distance: float | None = None
    match_type: str = "vector"


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    message: str | None = None  # 当向量检索不可用等时给出说明


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="搜索查询"),
    top_k: int = Query(default=10, ge=1, le=50),
    source: str | None = Query(default=None, description="按来源过滤"),
    mode: str = Query(default="hybrid", description="搜索模式: vector/metadata/hybrid"),
):
    """Hybrid semantic search across all data stores."""
    results: list[SearchResult] = []
    message: str | None = None

    if mode in ("vector", "hybrid"):
        try:
            vector_hits = await semantic_search(q, top_k=top_k, source_filter=source)
        except Exception:
            vector_hits = []
            message = (
                "向量检索暂不可用（Milvus 或 Embedding 服务异常），仅展示关键词匹配结果。"
                "请检查：1) 设置中 LLM 是否已连接 2) Milvus 是否已启动 3) 是否有已审核并向量化的实体。"
            )
        else:
            vector_hits = vector_hits or []
        for hit in vector_hits:
            results.append(SearchResult(
                entity_id=hit["entity_id"],
                title=hit.get("title"),
                content=hit.get("content", "")[:300],
                source=hit.get("source"),
                obsidian_path=hit.get("obsidian_path"),
                distance=hit.get("distance"),
                match_type="vector",
            ))

    if mode in ("metadata", "hybrid"):
        meta_hits = await _metadata_search(q, top_k=top_k, source=source)
        seen_ids = {r.entity_id for r in results}
        for hit in meta_hits:
            if hit["id"] not in seen_ids:
                results.append(SearchResult(
                    entity_id=hit["id"],
                    title=hit.get("title"),
                    content=hit.get("content", "")[:300],
                    source=hit.get("source"),
                    obsidian_path=hit.get("obsidian_path"),
                    match_type="metadata",
                ))

    if mode == "hybrid":
        results = _rrf_merge(results, top_k)

    return SearchResponse(query=q, results=results[:top_k], total=len(results), message=message)


async def _metadata_search(query: str, top_k: int = 10, source: str | None = None) -> list[dict]:
    """SQLite full-text search on title and content."""
    db = await get_db()
    params: list = []
    where_clauses = ["(title LIKE ? OR content LIKE ?)"]
    params.extend([f"%{query}%", f"%{query}%"])

    if source:
        where_clauses.append("source = ?")
        params.append(source)

    sql = f"""SELECT id, title, substr(content, 1, 300) as content, source, obsidian_path
              FROM entities
              WHERE {' AND '.join(where_clauses)}
              ORDER BY updated_at DESC
              LIMIT ?"""
    params.append(top_k)

    cursor = await db.execute(sql, params)
    return [dict(r) for r in await cursor.fetchall()]


def _rrf_merge(results: list[SearchResult], top_k: int, k: int = 60) -> list[SearchResult]:
    """Reciprocal Rank Fusion to merge vector and metadata results."""
    scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for rank, r in enumerate(results):
        rrf_score = 1.0 / (k + rank + 1)
        scores[r.entity_id] = scores.get(r.entity_id, 0) + rrf_score
        if r.entity_id not in result_map:
            result_map[r.entity_id] = r

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [result_map[eid] for eid in sorted_ids[:top_k]]
