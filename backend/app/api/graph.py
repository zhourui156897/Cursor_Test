"""Knowledge graph query API: graph traversal and visualization data."""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.storage.neo4j_client import (
    get_entity_relations,
    get_graph_stats,
    run_cypher,
    is_available,
)

router = APIRouter()


class GraphNode(BaseModel):
    id: str
    title: str
    source: str = ""
    labels: list[str] = []


class GraphEdge(BaseModel):
    source: str  # from node id
    target: str  # to node id
    type: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStatsResponse(BaseModel):
    available: bool
    node_count: int = 0
    relationship_count: int = 0
    error: str | None = None


@router.get("/stats", response_model=GraphStatsResponse)
async def graph_stats():
    """Get knowledge graph statistics."""
    stats = await get_graph_stats()
    return GraphStatsResponse(**stats)


@router.get("/entity/{entity_id}", response_model=GraphData)
async def entity_graph(
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=3),
):
    """Get graph data for a specific entity and its neighbors."""
    if not await is_available():
        raise HTTPException(503, "Neo4j 不可用")

    raw = await get_entity_relations(entity_id, depth=depth)

    nodes = [GraphNode(
        id=n["id"],
        title=n.get("title", ""),
        source=n.get("source", ""),
        labels=n.get("labels", []),
    ) for n in raw.get("nodes", [])]

    edges = [GraphEdge(
        source=e["from"],
        target=e["to"],
        type=e.get("type", "RELATED_TO"),
    ) for e in raw.get("edges", [])]

    return GraphData(nodes=nodes, edges=edges)


@router.get("/overview", response_model=GraphData)
async def graph_overview(
    limit: int = Query(default=100, ge=10, le=500),
):
    """Get an overview of the entire knowledge graph (limited nodes)."""
    if not await is_available():
        raise HTTPException(503, "Neo4j 不可用")

    node_results = await run_cypher(
        """MATCH (e:Entity)
           RETURN e.entity_id as id, e.title as title, e.source as source, labels(e) as labels
           ORDER BY e.title
           LIMIT $limit""",
        {"limit": limit},
    )

    nodes = []
    node_ids = set()
    for r in node_results:
        nid = r.get("id", "")
        if nid:
            nodes.append(GraphNode(
                id=nid,
                title=r.get("title", ""),
                source=r.get("source", ""),
                labels=r.get("labels", []),
            ))
            node_ids.add(nid)

    edge_results = await run_cypher(
        """MATCH (a:Entity)-[r]->(b:Entity)
           WHERE a.entity_id IN $ids AND b.entity_id IN $ids
           RETURN a.entity_id as from_id, b.entity_id as to_id, type(r) as rel_type
           LIMIT 500""",
        {"ids": list(node_ids)},
    )

    edges = [GraphEdge(
        source=r.get("from_id", ""),
        target=r.get("to_id", ""),
        type=r.get("rel_type", "RELATED_TO"),
    ) for r in edge_results]

    return GraphData(nodes=nodes, edges=edges)
