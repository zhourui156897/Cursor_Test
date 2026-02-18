"""Version history and status timeline API."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.storage.sqlite_client import get_db

router = APIRouter()


class VersionItem(BaseModel):
    id: str
    version_number: int
    title: str | None
    content: str | None
    change_source: str | None
    change_summary: str | None
    created_at: str


class StatusTimelineItem(BaseModel):
    id: str
    dimension: str
    old_value: str | None
    new_value: str | None
    changed_by: str | None
    changed_at: str
    note: str | None


class VersionDiff(BaseModel):
    entity_id: str
    version_a: VersionItem
    version_b: VersionItem


@router.get("/{entity_id}/versions")
async def list_versions(entity_id: str):
    """List all versions of an entity."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, version_number, title, substr(content, 1, 200) as content,
                  change_source, change_summary, created_at
           FROM entity_versions
           WHERE entity_id = ?
           ORDER BY version_number DESC""",
        (entity_id,),
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    if not rows:
        cursor2 = await db.execute("SELECT id FROM entities WHERE id = ?", (entity_id,))
        if not await cursor2.fetchone():
            raise HTTPException(404, "实体不存在")
    return rows


@router.get("/{entity_id}/versions/{version_number}")
async def get_version(entity_id: str, version_number: int):
    """Get a specific version's full content."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM entity_versions
           WHERE entity_id = ? AND version_number = ?""",
        (entity_id, version_number),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "版本不存在")

    result = dict(row)
    for key in ("metadata", "tags_snapshot"):
        if result.get(key) and isinstance(result[key], str):
            try:
                result[key] = json.loads(result[key])
            except json.JSONDecodeError:
                pass
    return result


@router.get("/{entity_id}/diff")
async def version_diff(
    entity_id: str,
    a: int = Query(..., description="版本A编号"),
    b: int = Query(..., description="版本B编号"),
):
    """Compare two versions of an entity."""
    db = await get_db()

    async def _get_version(vnum: int) -> dict:
        cursor = await db.execute(
            "SELECT * FROM entity_versions WHERE entity_id = ? AND version_number = ?",
            (entity_id, vnum),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, f"版本 {vnum} 不存在")
        return dict(row)

    va = await _get_version(a)
    vb = await _get_version(b)

    return {
        "entity_id": entity_id,
        "version_a": va,
        "version_b": vb,
        "title_changed": va.get("title") != vb.get("title"),
        "content_changed": va.get("content") != vb.get("content"),
    }


@router.get("/{entity_id}/timeline")
async def status_timeline(entity_id: str):
    """Get the status change timeline for an entity."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, dimension, old_value, new_value, changed_by, changed_at, note
           FROM status_timeline
           WHERE entity_id = ?
           ORDER BY changed_at DESC""",
        (entity_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]
