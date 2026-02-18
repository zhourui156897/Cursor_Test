"""Neo4j knowledge graph client.

Manages entity nodes and relationship edges for the knowledge graph.
Falls back gracefully if Neo4j is not available.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_driver = None
_available: bool | None = None


async def get_driver():
    global _driver, _available
    if _driver is not None:
        return _driver

    try:
        import neo4j as neo4j_lib
        settings = get_settings()
        _driver = neo4j_lib.GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_lifetime=300,
        )
        _driver.verify_connectivity()
        _available = True
        logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
        await _ensure_constraints()
        return _driver
    except Exception as e:
        _available = False
        _driver = None
        logger.warning("Neo4j unavailable: %s", e)
        return None


async def _ensure_constraints():
    """Create indexes and constraints if they don't exist."""
    if _driver is None:
        return
    with _driver.session() as session:
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE")
        session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.title)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.source)")
    logger.info("Neo4j constraints and indexes ensured")


async def is_available() -> bool:
    global _available
    if _available is None:
        await get_driver()
    return bool(_available)


async def create_entity_node(
    entity_id: str,
    title: str,
    source: str,
    content_type: str = "text",
    tags: list[str] | None = None,
    extra_props: dict[str, Any] | None = None,
) -> str | None:
    """Create or merge an Entity node. Returns the neo4j element ID or None."""
    driver = await get_driver()
    if driver is None:
        return None

    props = {
        "entity_id": entity_id,
        "title": title,
        "source": source,
        "content_type": content_type,
    }
    if tags:
        props["tags"] = tags
    if extra_props:
        props.update(extra_props)

    try:
        with driver.session() as session:
            result = session.run(
                """MERGE (e:Entity {entity_id: $entity_id})
                   SET e += $props
                   RETURN elementId(e) as node_id""",
                entity_id=entity_id,
                props=props,
            )
            record = result.single()
            node_id = record["node_id"] if record else None
            logger.debug("Upserted Neo4j node for entity %s -> %s", entity_id, node_id)
            return node_id
    except Exception as e:
        logger.error("Failed to create Neo4j entity node: %s", e)
        return None


async def create_relationship(
    from_entity_id: str,
    to_entity_id: str,
    rel_type: str,
    properties: dict[str, Any] | None = None,
) -> bool:
    """Create a typed relationship between two entity nodes."""
    driver = await get_driver()
    if driver is None:
        return False

    try:
        props_clause = ""
        params: dict[str, Any] = {
            "from_id": from_entity_id,
            "to_id": to_entity_id,
        }
        if properties:
            props_clause = " SET r += $props"
            params["props"] = properties

        safe_rel = rel_type.upper().replace(" ", "_").replace("-", "_")

        with driver.session() as session:
            session.run(
                f"""MATCH (a:Entity {{entity_id: $from_id}})
                    MATCH (b:Entity {{entity_id: $to_id}})
                    MERGE (a)-[r:{safe_rel}]->(b)
                    {props_clause}""",
                **params,
            )
        logger.debug("Created relationship %s -> %s [%s]", from_entity_id, to_entity_id, safe_rel)
        return True
    except Exception as e:
        logger.error("Failed to create relationship: %s", e)
        return False


async def get_entity_relations(
    entity_id: str,
    depth: int = 1,
) -> dict:
    """Get an entity and its relationships up to N hops."""
    driver = await get_driver()
    if driver is None:
        return {"nodes": [], "edges": []}

    try:
        with driver.session() as session:
            result = session.run(
                """MATCH path = (e:Entity {entity_id: $entity_id})-[*1..%d]-(related)
                   RETURN e, relationships(path) as rels, nodes(path) as path_nodes
                   LIMIT 100""" % min(depth, 3),
                entity_id=entity_id,
            )

            nodes_map: dict[str, dict] = {}
            edges: list[dict] = []

            for record in result:
                for node in record["path_nodes"]:
                    nid = node.get("entity_id", str(node.element_id))
                    if nid not in nodes_map:
                        nodes_map[nid] = {
                            "id": nid,
                            "title": node.get("title", ""),
                            "source": node.get("source", ""),
                            "labels": list(node.labels),
                        }
                for rel in record["rels"]:
                    edges.append({
                        "from": rel.start_node.get("entity_id", ""),
                        "to": rel.end_node.get("entity_id", ""),
                        "type": rel.type,
                    })

            return {"nodes": list(nodes_map.values()), "edges": edges}
    except Exception as e:
        logger.error("Failed to get entity relations: %s", e)
        return {"nodes": [], "edges": []}


async def delete_entity_node(entity_id: str) -> bool:
    """Delete an entity node and all its relationships."""
    driver = await get_driver()
    if driver is None:
        return False

    try:
        with driver.session() as session:
            session.run(
                "MATCH (e:Entity {entity_id: $entity_id}) DETACH DELETE e",
                entity_id=entity_id,
            )
        logger.debug("Deleted Neo4j node for entity %s", entity_id)
        return True
    except Exception as e:
        logger.error("Failed to delete Neo4j node: %s", e)
        return False


async def run_cypher(query: str, params: dict | None = None) -> list[dict]:
    """Run an arbitrary Cypher query and return results as list of dicts."""
    driver = await get_driver()
    if driver is None:
        return []

    try:
        with driver.session() as session:
            result = session.run(query, **(params or {}))
            return [dict(record) for record in result]
    except Exception as e:
        logger.error("Cypher query failed: %s", e)
        return []


async def get_graph_stats() -> dict:
    """Get basic graph statistics."""
    driver = await get_driver()
    if driver is None:
        return {"available": False}

    try:
        with driver.session() as session:
            node_count = session.run("MATCH (n:Entity) RETURN count(n) as cnt").single()["cnt"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as cnt").single()["cnt"]
            return {
                "available": True,
                "node_count": node_count,
                "relationship_count": rel_count,
            }
    except Exception as e:
        return {"available": False, "error": str(e)}


async def close_neo4j():
    global _driver, _available
    if _driver is not None:
        _driver.close()
        _driver = None
        _available = None
        logger.info("Neo4j driver closed")
