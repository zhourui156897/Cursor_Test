"""Tag system CRUD API: tree tags, content tags, status dimensions."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user, get_admin_user
from app.models.tag import (
    TagTreeCreate, TagTreeUpdate, TagTreeOut,
    ContentTagCreate, ContentTagUpdate, ContentTagOut,
    StatusDimensionCreate, StatusDimensionUpdate, StatusDimensionOut,
)
from app.models.user import UserOut
from app.storage.sqlite_client import get_db

router = APIRouter()


# ===========================
# Tree Tags (Folder Structure)
# ===========================

async def _build_path(db, name: str, parent_id: str | None) -> str:
    if parent_id is None:
        return name
    cursor = await db.execute("SELECT path FROM tag_tree WHERE id = ?", (parent_id,))
    parent = await cursor.fetchone()
    if parent is None:
        raise HTTPException(status_code=400, detail="父标签不存在")
    return f"{parent['path']}/{name}"


async def _build_tree(rows: list[dict]) -> list[TagTreeOut]:
    """Build a nested tree from flat rows."""
    by_id: dict[str, TagTreeOut] = {}
    roots: list[TagTreeOut] = []

    for r in rows:
        node = TagTreeOut(**r, children=[])
        by_id[node.id] = node

    for node in by_id.values():
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots


@router.get("/tree", response_model=list[TagTreeOut])
async def list_tree_tags(_: Annotated[UserOut, Depends(get_current_user)]):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, name, parent_id, path, icon, sort_order, created_at, updated_at "
        "FROM tag_tree ORDER BY sort_order, name"
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    return await _build_tree(rows)


@router.post("/tree", response_model=TagTreeOut, status_code=201)
async def create_tree_tag(
    req: TagTreeCreate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    tag_id = str(uuid.uuid4())
    path = await _build_path(db, req.name, req.parent_id)

    await db.execute(
        "INSERT INTO tag_tree (id, name, parent_id, path, icon, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
        (tag_id, req.name, req.parent_id, path, req.icon, req.sort_order),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM tag_tree WHERE id = ?", (tag_id,))
    row = dict(await cursor.fetchone())
    return TagTreeOut(**row, children=[])


@router.put("/tree/{tag_id}", response_model=TagTreeOut)
async def update_tree_tag(
    tag_id: str,
    req: TagTreeUpdate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM tag_tree WHERE id = ?", (tag_id,))
    existing = await cursor.fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="标签不存在")

    name = req.name or existing["name"]
    parent_id = req.parent_id if req.parent_id is not None else existing["parent_id"]
    path = await _build_path(db, name, parent_id)

    updates = {"name": name, "parent_id": parent_id, "path": path, "updated_at": "datetime('now')"}
    if req.icon is not None:
        updates["icon"] = req.icon
    if req.sort_order is not None:
        updates["sort_order"] = req.sort_order

    set_parts = []
    values = []
    for k, v in updates.items():
        if v == "datetime('now')":
            set_parts.append(f"{k} = datetime('now')")
        else:
            set_parts.append(f"{k} = ?")
            values.append(v)

    values.append(tag_id)
    await db.execute(f"UPDATE tag_tree SET {', '.join(set_parts)} WHERE id = ?", values)
    await db.commit()

    cursor = await db.execute("SELECT * FROM tag_tree WHERE id = ?", (tag_id,))
    row = dict(await cursor.fetchone())
    return TagTreeOut(**row, children=[])


@router.delete("/tree/{tag_id}")
async def delete_tree_tag(
    tag_id: str,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    await db.execute("DELETE FROM tag_tree WHERE id = ?", (tag_id,))
    await db.commit()
    return {"message": "标签已删除"}


# ===========================
# Content Tags (Flat)
# ===========================

@router.get("/content", response_model=list[ContentTagOut])
async def list_content_tags(_: Annotated[UserOut, Depends(get_current_user)]):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, name, color, usage_count, created_at FROM content_tags ORDER BY usage_count DESC, name"
    )
    return [ContentTagOut(**dict(r)) for r in await cursor.fetchall()]


@router.post("/content", response_model=ContentTagOut, status_code=201)
async def create_content_tag(
    req: ContentTagCreate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    tag_id = str(uuid.uuid4())

    try:
        await db.execute(
            "INSERT INTO content_tags (id, name, color) VALUES (?, ?, ?)",
            (tag_id, req.name, req.color),
        )
        await db.commit()
    except Exception:
        raise HTTPException(status_code=400, detail="标签名已存在")

    cursor = await db.execute("SELECT * FROM content_tags WHERE id = ?", (tag_id,))
    return ContentTagOut(**dict(await cursor.fetchone()))


@router.put("/content/{tag_id}", response_model=ContentTagOut)
async def update_content_tag(
    tag_id: str,
    req: ContentTagUpdate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.color is not None:
        updates["color"] = req.color

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [tag_id]
        await db.execute(f"UPDATE content_tags SET {set_clause} WHERE id = ?", values)
        await db.commit()

    cursor = await db.execute("SELECT * FROM content_tags WHERE id = ?", (tag_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    return ContentTagOut(**dict(row))


@router.delete("/content/{tag_id}")
async def delete_content_tag(
    tag_id: str,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    await db.execute("DELETE FROM content_tags WHERE id = ?", (tag_id,))
    await db.commit()
    return {"message": "标签已删除"}


# ===========================
# Status Dimensions
# ===========================

@router.get("/status", response_model=list[StatusDimensionOut])
async def list_status_dimensions(_: Annotated[UserOut, Depends(get_current_user)]):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM status_dimensions ORDER BY created_at")
    rows = []
    for r in await cursor.fetchall():
        d = dict(r)
        d["options"] = json.loads(d["options"]) if isinstance(d["options"], str) else d["options"]
        rows.append(StatusDimensionOut(**d))
    return rows


@router.post("/status", response_model=StatusDimensionOut, status_code=201)
async def create_status_dimension(
    req: StatusDimensionCreate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    dim_id = str(uuid.uuid4())

    try:
        await db.execute(
            "INSERT INTO status_dimensions (id, key, display_name, options, default_value) VALUES (?, ?, ?, ?, ?)",
            (dim_id, req.key, req.display_name, json.dumps(req.options, ensure_ascii=False), req.default_value),
        )
        await db.commit()
    except Exception:
        raise HTTPException(status_code=400, detail="维度key已存在")

    cursor = await db.execute("SELECT * FROM status_dimensions WHERE id = ?", (dim_id,))
    d = dict(await cursor.fetchone())
    d["options"] = json.loads(d["options"])
    return StatusDimensionOut(**d)


@router.put("/status/{dim_id}", response_model=StatusDimensionOut)
async def update_status_dimension(
    dim_id: str,
    req: StatusDimensionUpdate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    updates = {}
    if req.display_name is not None:
        updates["display_name"] = req.display_name
    if req.options is not None:
        updates["options"] = json.dumps(req.options, ensure_ascii=False)
    if req.default_value is not None:
        updates["default_value"] = req.default_value

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [dim_id]
        await db.execute(f"UPDATE status_dimensions SET {set_clause} WHERE id = ?", values)
        await db.commit()

    cursor = await db.execute("SELECT * FROM status_dimensions WHERE id = ?", (dim_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="维度不存在")
    d = dict(row)
    d["options"] = json.loads(d["options"])
    return StatusDimensionOut(**d)


@router.delete("/status/{dim_id}")
async def delete_status_dimension(
    dim_id: str,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    await db.execute("DELETE FROM status_dimensions WHERE id = ?", (dim_id,))
    await db.commit()
    return {"message": "维度已删除"}
