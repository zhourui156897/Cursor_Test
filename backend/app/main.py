"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.storage.sqlite_client import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _ensure_admin_user()

    # Pre-connect Milvus (non-blocking: lite mode is instant, standalone may not be ready)
    try:
        from app.storage.milvus_client import get_milvus
        await get_milvus()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Milvus not available at startup: %s", e)

    # 定时同步：若开启则按间隔执行（使用已持久化的 sync_scope）
    _scheduler: object | None = None
    try:
        from app.config import get_user_config
        from app.sync.scheduler import run_scheduled_sync
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        cfg = get_user_config().get("apple_sync", {})
        if cfg.get("auto_sync") and cfg.get("interval_minutes", 0) > 0:
            interval = max(1, int(cfg["interval_minutes"]))
            _scheduler = AsyncIOScheduler(event_loop=asyncio.get_running_loop())
            _scheduler.add_job(run_scheduled_sync, "interval", minutes=interval, id="apple_sync")
            _scheduler.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Scheduled sync not started: %s", e)

    yield

    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
    from app.services.llm_service import close_client
    from app.storage.milvus_client import close_milvus
    from app.storage.neo4j_client import close_neo4j
    await close_client()
    await close_milvus()
    await close_neo4j()
    await close_db()


from app.api.version import get_local_version

app = FastAPI(
    title="第二大脑 - dierdanao",
    description="人生价值系统 API",
    version=get_local_version(),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    from app.storage.milvus_client import get_collection_stats
    from app.storage.neo4j_client import get_graph_stats
    return {
        "status": "ok",
        "version": get_local_version(),
        "milvus": await get_collection_stats(),
        "neo4j": await get_graph_stats(),
    }


async def _ensure_admin_user():
    from app.storage.sqlite_client import get_db
    from app.config import get_settings

    settings = get_settings()
    db = await get_db()

    row = await db.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    admin = await row.fetchone()

    if admin is None:
        from passlib.hash import bcrypt
        import uuid

        password_hash = bcrypt.hash(settings.admin_password)
        await db.execute(
            "INSERT INTO users (id, username, password_hash, display_name, role) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), settings.admin_username, password_hash, "管理员", "admin"),
        )
        await db.commit()


# --- Register API routers ---

from app.api import auth as auth_router
from app.api import tags as tags_router
from app.api import entities as entities_router
from app.api import upload as upload_router
from app.api import review as review_router
from app.api import sync as sync_router
from app.api import search as search_router
from app.api import graph as graph_router
from app.api import chat as chat_router
from app.api import history as history_router
from app.api import settings_api as settings_router
from app.api import version as version_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["认证"])
app.include_router(tags_router.router, prefix="/api/tags", tags=["标签"])
app.include_router(entities_router.router, prefix="/api/entities", tags=["实体"])
app.include_router(upload_router.router, prefix="/api/upload", tags=["上传"])
app.include_router(review_router.router, prefix="/api/review", tags=["审核"])
app.include_router(sync_router.router, prefix="/api/sync", tags=["同步"])
app.include_router(search_router.router, prefix="/api/search", tags=["搜索"])
app.include_router(graph_router.router, prefix="/api/graph", tags=["图谱"])
app.include_router(chat_router.router, prefix="/api/chat", tags=["对话"])
app.include_router(history_router.router, prefix="/api/history", tags=["历史"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["设置"])
app.include_router(version_router.router, prefix="/api/version", tags=["版本"])
