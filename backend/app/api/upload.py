"""File upload API: accepts multimodal files → extract text → ingest pipeline → review queue."""

from __future__ import annotations

import uuid
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.models.user import UserOut

router = APIRouter()

ALLOWED_EXTENSIONS = {
    "text": {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".xml", ".html"},
    "document": {".docx", ".doc", ".xlsx", ".xls", ".pptx"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"},
    "audio": {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma"},
    "video": {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    "pdf": {".pdf"},
}


@router.post("")
async def upload_file(
    user: Annotated[UserOut, Depends(get_current_user)],
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
):
    """Upload any file → text extraction → LLM tag suggestion → review queue."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = Path(file.filename).suffix.lower()
    all_exts = set()
    for exts in ALLOWED_EXTENSIONS.values():
        all_exts |= exts
    if ext not in all_exts:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")

    settings = get_settings()
    upload_dir = settings.resolved_data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    saved_name = f"{file_id}{ext}"
    saved_path = upload_dir / saved_name

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    entity_title = title or Path(file.filename).stem

    from app.sync.ingest_pipeline import ingest_uploaded_file
    result = await ingest_uploaded_file(
        file_path=str(saved_path),
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        created_by=user.id,
    )

    return {
        "message": "文件已上传并进入处理流程",
        "entity_id": result.get("id"),
        "status": result.get("status"),
        "title": entity_title,
        "file": saved_name,
    }
