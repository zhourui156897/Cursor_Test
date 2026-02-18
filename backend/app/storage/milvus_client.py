"""Milvus vector database client.

Supports two modes via VECTOR_DB_MODE env var:
- "milvus-lite": Embedded local file-based Milvus (no Docker needed)
- "milvus": Standalone Milvus server via Docker
"""

from __future__ import annotations

import logging
from typing import Any

from pymilvus import MilvusClient, DataType

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: MilvusClient | None = None

COLLECTION_NAME = "dierdanao_entities"
VECTOR_FIELD = "embedding"
ID_FIELD = "entity_id"
TEXT_FIELD = "text_preview"
SOURCE_FIELD = "source"


async def get_milvus() -> MilvusClient:
    global _client
    if _client is not None:
        return _client

    settings = get_settings()

    if settings.vector_db_mode == "milvus-lite":
        db_path = str(settings.resolved_data_dir / "milvus_lite.db")
        settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        _client = MilvusClient(uri=db_path)
        logger.info("Connected to Milvus Lite: %s", db_path)
    else:
        uri = f"http://localhost:{settings.milvus_port}"
        _client = MilvusClient(uri=uri)
        logger.info("Connected to Milvus Standalone: %s", uri)

    await _ensure_collection(_client, settings.embedding_dim)
    return _client


async def _ensure_collection(client: MilvusClient, dim: int):
    """Create the entity collection if it doesn't exist."""
    if client.has_collection(COLLECTION_NAME):
        logger.debug("Collection '%s' already exists", COLLECTION_NAME)
        return

    schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field(ID_FIELD, DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field(VECTOR_FIELD, DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field(TEXT_FIELD, DataType.VARCHAR, max_length=512)
    schema.add_field(SOURCE_FIELD, DataType.VARCHAR, max_length=64)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name=VECTOR_FIELD,
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128},
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params,
    )
    logger.info("Created Milvus collection '%s' with dim=%d", COLLECTION_NAME, dim)


async def upsert_vector(
    entity_id: str,
    embedding: list[float],
    text_preview: str = "",
    source: str = "",
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Insert or update a single entity vector."""
    client = await get_milvus()
    data = {
        ID_FIELD: entity_id,
        VECTOR_FIELD: embedding,
        TEXT_FIELD: text_preview[:500],
        SOURCE_FIELD: source,
    }
    if extra_fields:
        data.update(extra_fields)

    client.upsert(collection_name=COLLECTION_NAME, data=[data])
    logger.debug("Upserted vector for entity %s", entity_id)


async def search_vectors(
    query_embedding: list[float],
    top_k: int = 10,
    filters: str | None = None,
    output_fields: list[str] | None = None,
) -> list[dict]:
    """Search for similar vectors. Returns list of {entity_id, distance, ...}."""
    client = await get_milvus()

    if output_fields is None:
        output_fields = [ID_FIELD, TEXT_FIELD, SOURCE_FIELD]

    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_embedding],
        limit=top_k,
        filter=filters or "",
        output_fields=output_fields,
        search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
    )

    hits = []
    for result_list in results:
        for hit in result_list:
            hits.append({
                "entity_id": hit["entity"][ID_FIELD],
                "distance": hit["distance"],
                "text_preview": hit["entity"].get(TEXT_FIELD, ""),
                "source": hit["entity"].get(SOURCE_FIELD, ""),
            })
    return hits


async def delete_vector(entity_id: str) -> None:
    """Delete a vector by entity ID."""
    client = await get_milvus()
    client.delete(collection_name=COLLECTION_NAME, ids=[entity_id])
    logger.debug("Deleted vector for entity %s", entity_id)


async def get_collection_stats() -> dict:
    """Get collection statistics. Returns quickly if client is not initialized."""
    if _client is None:
        return {"status": "unavailable", "collection": COLLECTION_NAME}
    try:
        stats = _client.get_collection_stats(COLLECTION_NAME)
        return {"status": "ok", "collection": COLLECTION_NAME, "stats": stats}
    except Exception as e:
        return {"status": "error", "collection": COLLECTION_NAME, "error": str(e)}


async def close_milvus():
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("Milvus client closed")
