"""FastAPI application entry point."""

from __future__ import annotations

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

    yield

    from app.services.llm_service import close_client
    from app.storage.milvus_client import close_milvus
    from app.storage.neo4j_client import close_neo4j
    await close_client()
    await close_milvus()
    await close_neo4j()
    await close_db()


app = FastAPI(
    title="第二大脑 - dierdanao",
    description="人生价值系统 API",
    version="0.2.0",
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
        "version": "0.2.0",
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

app.include_router(auth_router.router, prefix="/api/auth", tags=["认证"])
app.include_router(tags_router.router, prefix="/api/tags", tags=["标签"])
app.include_router(entities_router.router, prefix="/api/entities", tags=["实体"])
app.include_router(upload_router.router, prefix="/api/upload", tags=["上传"])
app.include_router(review_router.router, prefix="/api/review", tags=["审核"])
app.include_router(sync_router.router, prefix="/api/sync", tags=["同步"])
