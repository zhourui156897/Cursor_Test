"""SQLite database connection and initialization."""

from __future__ import annotations

import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager

from app.config import get_settings

_db_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db_connection
    if _db_connection is not None:
        try:
            await _db_connection.execute("SELECT 1")
        except Exception:
            _db_connection = None

    if _db_connection is None:
        settings = get_settings()
        settings.resolved_data_dir.mkdir(parents=True, exist_ok=True)
        _db_connection = await aiosqlite.connect(str(settings.db_path))
        _db_connection.row_factory = aiosqlite.Row
        await _db_connection.execute("PRAGMA journal_mode=WAL")
        await _db_connection.execute("PRAGMA foreign_keys=ON")
    return _db_connection


async def close_db():
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None


@asynccontextmanager
async def db_transaction():
    db = await get_db()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise


SCHEMA_SQL = """
-- ============================================
-- 用户与权限
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'member',
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role TEXT NOT NULL,
    permission TEXT NOT NULL,
    scope_config TEXT,
    PRIMARY KEY (role, permission)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================
-- 树形文件夹标签
-- ============================================

CREATE TABLE IF NOT EXISTS tag_tree (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT REFERENCES tag_tree(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    icon TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tag_tree_parent ON tag_tree(parent_id);
CREATE INDEX IF NOT EXISTS idx_tag_tree_path ON tag_tree(path);

-- ============================================
-- 扁平内容标签
-- ============================================

CREATE TABLE IF NOT EXISTS content_tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================
-- 状态标签维度
-- ============================================

CREATE TABLE IF NOT EXISTS status_dimensions (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    display_name TEXT,
    options TEXT NOT NULL,
    default_value TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================
-- 核心实体
-- ============================================

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    content TEXT,
    content_type TEXT DEFAULT 'text',
    obsidian_path TEXT,
    file_path TEXT,
    metadata TEXT,
    current_version INTEGER DEFAULT 1,
    milvus_id TEXT,
    neo4j_node_id TEXT,
    review_status TEXT DEFAULT 'pending',
    content_hash TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source);
CREATE INDEX IF NOT EXISTS idx_entities_review ON entities(review_status);
CREATE INDEX IF NOT EXISTS idx_entities_created_by ON entities(created_by);

-- ============================================
-- 实体标签绑定
-- ============================================

CREATE TABLE IF NOT EXISTS entity_tags (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    tag_tree_id TEXT REFERENCES tag_tree(id) ON DELETE SET NULL,
    content_tag_ids TEXT,
    status_values TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (entity_id, tag_tree_id)
);

-- ============================================
-- 审核队列
-- ============================================

CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    suggested_folder_tags TEXT,
    suggested_content_tags TEXT,
    suggested_status TEXT,
    confidence_scores TEXT,
    status TEXT DEFAULT 'pending',
    reviewer_action TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);

-- ============================================
-- 版本历史
-- ============================================

CREATE TABLE IF NOT EXISTS entity_versions (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title TEXT,
    content TEXT,
    metadata TEXT,
    tags_snapshot TEXT,
    change_source TEXT,
    change_summary TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entity_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_entity_versions_entity ON entity_versions(entity_id);

-- ============================================
-- 状态时间线
-- ============================================

CREATE TABLE IF NOT EXISTS status_timeline (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT,
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_status_timeline_entity ON status_timeline(entity_id);

-- ============================================
-- 同步状态追踪
-- ============================================

CREATE TABLE IF NOT EXISTS sync_state (
    entity_id TEXT NOT NULL,
    layer TEXT NOT NULL,
    content_hash TEXT,
    last_synced_at TEXT,
    sync_status TEXT DEFAULT 'synced',
    PRIMARY KEY (entity_id, layer)
);

-- ============================================
-- 配置变更日志
-- ============================================

CREATE TABLE IF NOT EXISTS config_changelog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_type TEXT NOT NULL,
    target TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by TEXT,
    changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================
-- 对话
-- ============================================

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    summary TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    tool_results TEXT,
    sources TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
"""


async def init_db():
    db = await get_db()
    await db.executescript(SCHEMA_SQL)
    await db.commit()
