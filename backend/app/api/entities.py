"""Entity CRUD API with version history and status timeline."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.models.entity import (
    EntityCreate, EntityUpdate, EntityOut, EntityTagsOut,
    EntityVersionOut, StatusTimelineEntry,
)
from app.models.user import UserOut
from app.storage.sqlite_client import get_db

router = APIRouter()


def _content_hash(content: str | None) -> str:
    return hashlib.sha256((content or "").encode()).hexdigest()[:16]


def _parse_json(val: str | None) -> dict | list | None:
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


async def _get_entity_tags(db, entity_id: str) -> EntityTagsOut | None:
    cursor = await db.execute(
        "SELECT et.content_tag_ids, et.status_values, tt.path "
        "FROM entity_tags et LEFT JOIN tag_tree tt ON et.tag_tree_id = tt.id "
        "WHERE et.entity_id = ? LIMIT 1",
        (entity_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return EntityTagsOut(
        folder_tag_path=row["path"],
        content_tags=_parse_json(row["content_tag_ids"]) or [],
        status_values=_parse_json(row["status_values"]) or {},
    )


async def _to_entity_out(db, row) -> EntityOut:
    d = dict(row)
    d["metadata"] = _parse_json(d.get("metadata"))
    tags = await _get_entity_tags(db, d["id"])
    return EntityOut(**d, tags=tags)


# --- List & Get ---

@router.get("", response_model=list[EntityOut])
async def list_entities(
    user: Annotated[UserOut, Depends(get_current_user)],
    source: str | None = None,
    review_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    db = await get_db()
    conditions = []
    params = []

    if source:
        conditions.append("source = ?")
        params.append(source)
    if review_status:
        conditions.append("review_status = ?")
        params.append(review_status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size
    params.extend([page_size, offset])

    cursor = await db.execute(
        f"SELECT * FROM entities {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        params,
    )
    rows = await cursor.fetchall()
    return [await _to_entity_out(db, r) for r in rows]


@router.get("/{entity_id}", response_model=EntityOut)
async def get_entity(
    entity_id: str,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="实体不存在")
    return await _to_entity_out(db, row)


# --- Create ---

@router.post("", response_model=EntityOut, status_code=201)
async def create_entity(
    req: EntityCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    entity_id = str(uuid.uuid4())
    meta_json = json.dumps(req.metadata, ensure_ascii=False) if req.metadata else None
    chash = _content_hash(req.content)

    await db.execute(
        """INSERT INTO entities
           (id, source, source_id, title, content, content_type, metadata, content_hash, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entity_id, req.source, req.source_id, req.title, req.content,
         req.content_type, meta_json, chash, user.id),
    )

    # Save initial version
    await db.execute(
        """INSERT INTO entity_versions
           (id, entity_id, version_number, title, content, metadata, change_source, change_summary)
           VALUES (?, ?, 1, ?, ?, ?, 'create', '初始创建')""",
        (str(uuid.uuid4()), entity_id, req.title, req.content, meta_json),
    )

    # Bind tags if provided
    if req.folder_tag_id or req.content_tag_names or req.status_values:
        ct_json = json.dumps(req.content_tag_names, ensure_ascii=False) if req.content_tag_names else None
        sv_json = json.dumps(req.status_values, ensure_ascii=False) if req.status_values else None
        await db.execute(
            "INSERT INTO entity_tags (entity_id, tag_tree_id, content_tag_ids, status_values) VALUES (?, ?, ?, ?)",
            (entity_id, req.folder_tag_id, ct_json, sv_json),
        )

    await db.commit()

    cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
    return await _to_entity_out(db, await cursor.fetchone())


# --- Update (creates new version) ---

@router.put("/{entity_id}", response_model=EntityOut)
async def update_entity(
    entity_id: str,
    req: EntityUpdate,
    user: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
    existing = await cursor.fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="实体不存在")

    new_title = req.title if req.title is not None else existing["title"]
    new_content = req.content if req.content is not None else existing["content"]
    new_meta = json.dumps(req.metadata, ensure_ascii=False) if req.metadata is not None else existing["metadata"]
    new_version = existing["current_version"] + 1
    new_hash = _content_hash(new_content)

    # Save old version snapshot
    tags = await _get_entity_tags(db, entity_id)
    tags_snapshot = json.dumps(tags.model_dump() if tags else {}, ensure_ascii=False)

    await db.execute(
        """INSERT INTO entity_versions
           (id, entity_id, version_number, title, content, metadata, tags_snapshot, change_source, change_summary)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), entity_id, new_version, new_title, new_content,
         new_meta, tags_snapshot, "web_edit", f"v{new_version} 更新"),
    )

    await db.execute(
        """UPDATE entities SET title = ?, content = ?, metadata = ?,
           current_version = ?, content_hash = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (new_title, new_content, new_meta, new_version, new_hash, entity_id),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
    return await _to_entity_out(db, await cursor.fetchone())


# --- Delete ---

@router.delete("/{entity_id}")
async def delete_entity(
    entity_id: str,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    await db.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
    await db.commit()
    return {"message": "实体已删除"}


# --- Version History ---

@router.get("/{entity_id}/versions", response_model=list[EntityVersionOut])
async def list_versions(
    entity_id: str,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM entity_versions WHERE entity_id = ? ORDER BY version_number DESC",
        (entity_id,),
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["metadata"] = _parse_json(d.get("metadata"))
        d["tags_snapshot"] = _parse_json(d.get("tags_snapshot"))
        result.append(EntityVersionOut(**d))
    return result


@router.get("/{entity_id}/versions/{version_number}", response_model=EntityVersionOut)
async def get_version(
    entity_id: str,
    version_number: int,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM entity_versions WHERE entity_id = ? AND version_number = ?",
        (entity_id, version_number),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    d = dict(row)
    d["metadata"] = _parse_json(d.get("metadata"))
    d["tags_snapshot"] = _parse_json(d.get("tags_snapshot"))
    return EntityVersionOut(**d)


# --- Status Timeline ---

@router.get("/{entity_id}/timeline", response_model=list[StatusTimelineEntry])
async def get_status_timeline(
    entity_id: str,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM status_timeline WHERE entity_id = ? ORDER BY changed_at DESC",
        (entity_id,),
    )
    return [StatusTimelineEntry(**dict(r)) for r in await cursor.fetchall()]
