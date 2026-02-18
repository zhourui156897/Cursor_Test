"""File upload API: accepts multimodal files and creates entities."""

from __future__ import annotations

import uuid
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.models.entity import EntityOut
from app.models.user import UserOut
from app.storage.sqlite_client import get_db

router = APIRouter()

ALLOWED_EXTENSIONS = {
    "text": {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"},
    "audio": {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"},
    "video": {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    "pdf": {".pdf"},
}


def _detect_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    for ct, exts in ALLOWED_EXTENSIONS.items():
        if suffix in exts:
            return ct
    return "text"


@router.post("", response_model=EntityOut, status_code=201)
async def upload_file(
    user: Annotated[UserOut, Depends(get_current_user)],
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    settings = get_settings()
    upload_dir = settings.resolved_data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    content_type = _detect_content_type(file.filename)
    ext = Path(file.filename).suffix
    file_id = str(uuid.uuid4())
    saved_name = f"{file_id}{ext}"
    saved_path = upload_dir / saved_name

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    entity_title = title or Path(file.filename).stem
    entity_id = str(uuid.uuid4())

    # For text files, read content; for others, content is empty (will be processed later)
    content = None
    if content_type == "text" and saved_path.stat().st_size < 1_000_000:
        content = saved_path.read_text(encoding="utf-8", errors="replace")

    db = await get_db()
    await db.execute(
        """INSERT INTO entities
           (id, source, title, content, content_type, file_path, review_status, created_by)
           VALUES (?, 'upload', ?, ?, ?, ?, 'pending', ?)""",
        (entity_id, entity_title, content, content_type, str(saved_path), user.id),
    )

    await db.execute(
        """INSERT INTO entity_versions
           (id, entity_id, version_number, title, content, change_source, change_summary)
           VALUES (?, ?, 1, ?, ?, 'upload', '文件上传')""",
        (str(uuid.uuid4()), entity_id, entity_title, content),
    )

    await db.commit()

    cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
    row = await cursor.fetchone()

    from app.api.entities import _to_entity_out
    return await _to_entity_out(db, row)
