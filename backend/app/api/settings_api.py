"""System settings API: LLM config, paths, system info — all editable via Web UI."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, get_admin_user
from app.models.user import UserOut
from app.config import get_settings, get_user_config
from app.services.llm_service import check_available
from app.api.version import get_local_version

router = APIRouter()
logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    api_url: str = ""
    api_key: str = ""
    model: str = ""
    embedding_model: str = ""
    embedding_dim: int = 1024


class LLMConfigUpdate(BaseModel):
    api_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    embedding_dim: int | None = None


class PathsConfig(BaseModel):
    obsidian_vault_path: str = ""
    data_dir: str = ""


class PathsConfigUpdate(BaseModel):
    obsidian_vault_path: str | None = None
    data_dir: str | None = None


def _mask_key(key: str) -> str:
    """Mask API key for display: show first 8 and last 4 chars."""
    if not key or len(key) < 16:
        return "***" if key else ""
    return key[:8] + "****" + key[-4:]


@router.get("/llm")
async def get_llm_config(_: Annotated[UserOut, Depends(get_current_user)]):
    """Get current LLM configuration."""
    settings = get_settings()
    user_cfg = get_user_config()
    llm_cfg = user_cfg.get("llm", {})

    api_url = llm_cfg.get("api_url") or settings.llm_api_url
    api_key = llm_cfg.get("api_key", "")
    model = llm_cfg.get("model") or settings.llm_model
    embedding_model = llm_cfg.get("embedding_model") or settings.embedding_model
    embedding_dim = llm_cfg.get("embedding_dim") or settings.embedding_dim

    try:
        llm_ok = await asyncio.wait_for(check_available(), timeout=5.0)
    except Exception:
        llm_ok = False

    return {
        "api_url": api_url,
        "api_key_masked": _mask_key(api_key),
        "has_api_key": bool(api_key),
        "model": model,
        "embedding_model": embedding_model,
        "embedding_dim": embedding_dim,
        "status": "connected" if llm_ok else "disconnected",
    }


@router.put("/llm")
async def update_llm_config(
    update: LLMConfigUpdate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    """Update LLM configuration. Saves to user_config.yaml."""
    user_cfg = get_user_config()
    llm_cfg = user_cfg.get("llm", {})

    if update.api_url is not None:
        llm_cfg["api_url"] = update.api_url
    if update.api_key is not None:
        llm_cfg["api_key"] = update.api_key
    if update.model is not None:
        llm_cfg["model"] = update.model
    if update.embedding_model is not None:
        llm_cfg["embedding_model"] = update.embedding_model
    if update.embedding_dim is not None:
        llm_cfg["embedding_dim"] = update.embedding_dim

    user_cfg.set("llm", llm_cfg)
    user_cfg.save()

    # Clear cached settings so new values take effect
    _reload_settings(llm_cfg)

    logger.info("LLM config updated via API")
    return {"message": "LLM 配置已更新", "config": {**llm_cfg, "api_key": _mask_key(llm_cfg.get("api_key", ""))}}


@router.get("/paths")
async def get_paths_config(_: Annotated[UserOut, Depends(get_current_user)]):
    """Get current paths configuration."""
    settings = get_settings()
    return {
        "obsidian_vault_path": settings.obsidian_vault_path,
        "data_dir": settings.data_dir,
        "resolved_vault_path": str(settings.resolved_vault_path),
        "resolved_data_dir": str(settings.resolved_data_dir),
    }


@router.put("/paths")
async def update_paths_config(
    update: PathsConfigUpdate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    """Update paths configuration."""
    user_cfg = get_user_config()
    paths_cfg = user_cfg.get("paths", {})

    if update.obsidian_vault_path is not None:
        paths_cfg["obsidian_vault_path"] = update.obsidian_vault_path
    if update.data_dir is not None:
        paths_cfg["data_dir"] = update.data_dir

    user_cfg.set("paths", paths_cfg)
    user_cfg.save()
    return {"message": "路径配置已更新"}


@router.get("/system-info")
async def get_system_info(_: Annotated[UserOut, Depends(get_current_user)]):
    """Get comprehensive system information."""
    settings = get_settings()

    # Fetch external service stats with timeouts to avoid blocking
    async def _safe_milvus():
        try:
            from app.storage.milvus_client import get_collection_stats
            return await asyncio.wait_for(get_collection_stats(), timeout=5.0)
        except Exception as e:
            logger.warning("Milvus stats unavailable: %s", e)
            return {"status": "unavailable"}

    async def _safe_neo4j():
        try:
            from app.storage.neo4j_client import get_graph_stats
            return await asyncio.wait_for(get_graph_stats(), timeout=5.0)
        except Exception as e:
            logger.warning("Neo4j stats unavailable: %s", e)
            return {"available": False, "node_count": 0}

    async def _safe_llm():
        try:
            return await asyncio.wait_for(check_available(), timeout=5.0)
        except Exception:
            return False

    milvus_stats, neo4j_stats, llm_ok = await asyncio.gather(
        _safe_milvus(), _safe_neo4j(), _safe_llm()
    )

    from app.storage.sqlite_client import get_db
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM entities")
    entity_count = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM review_queue WHERE status = 'pending'")
    pending_count = (await cursor.fetchone())["cnt"]
    try:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM conversations")
        conv_count = (await cursor.fetchone())["cnt"]
    except Exception:
        conv_count = 0

    return {
        "version": get_local_version(),
        "phase": "Phase 3 完成 / Phase 4 进行中",
        "auth_mode": settings.auth_mode,
        "vector_db_mode": settings.vector_db_mode,
        "services": {
            "llm": {"status": "online" if llm_ok else "offline", "url": settings.llm_api_url},
            "milvus": milvus_stats,
            "neo4j": neo4j_stats,
        },
        "data": {
            "entities": entity_count,
            "pending_reviews": pending_count,
            "conversations": conv_count,
            "milvus_vectors": milvus_stats.get("stats", {}).get("row_count", 0),
            "neo4j_nodes": neo4j_stats.get("node_count", 0),
        },
    }


def _reload_settings(llm_cfg: dict):
    """Apply LLM config changes to the running settings."""
    settings = get_settings()
    if "api_url" in llm_cfg:
        settings.llm_api_url = llm_cfg["api_url"]
    if "model" in llm_cfg:
        settings.llm_model = llm_cfg["model"]
    if "embedding_model" in llm_cfg:
        settings.embedding_model = llm_cfg["embedding_model"]
    if "embedding_dim" in llm_cfg:
        settings.embedding_dim = llm_cfg["embedding_dim"]

    # Reset LLM client to pick up new URL/key
    import asyncio
    from app.services.llm_service import close_client
    try:
        asyncio.get_event_loop().create_task(close_client())
    except Exception:
        pass
