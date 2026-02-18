"""Sync & ingestion trigger API: manual sync, auto-sync config, upload with processing."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.auth.dependencies import get_current_user, get_admin_user
from app.models.user import UserOut
from app.config import get_settings, get_user_config

router = APIRouter()
logger = logging.getLogger(__name__)

# Track running sync jobs
_sync_status: dict = {
    "apple_notes": {"running": False, "last_run": None, "last_result": None},
    "apple_reminders": {"running": False, "last_run": None, "last_result": None},
    "apple_calendar": {"running": False, "last_run": None, "last_result": None},
}


@router.get("/status")
async def get_sync_status(_: Annotated[UserOut, Depends(get_current_user)]):
    """Get the status of all sync sources."""
    config = get_user_config()
    apple_cfg = config.get("apple_sync", {})
    return {
        "config": {
            "enabled": apple_cfg.get("enabled", False),
            "auto_sync": apple_cfg.get("auto_sync", False),
            "interval_minutes": apple_cfg.get("interval_minutes", 30),
            "sources": apple_cfg.get("sources", {}),
        },
        "status": _sync_status,
    }


@router.post("/trigger/{source}")
async def trigger_sync(
    source: str,
    user: Annotated[UserOut, Depends(get_current_user)],
):
    """Manually trigger sync for a specific source."""
    from app.sync.ingest_pipeline import (
        ingest_apple_notes,
        ingest_apple_reminders,
        ingest_apple_calendar,
    )

    valid_sources = {
        "apple_notes": ingest_apple_notes,
        "apple_reminders": ingest_apple_reminders,
        "apple_calendar": ingest_apple_calendar,
    }

    if source not in valid_sources:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}. Valid: {list(valid_sources.keys())}")

    if _sync_status[source]["running"]:
        raise HTTPException(status_code=409, detail=f"{source} sync is already running")

    _sync_status[source]["running"] = True
    try:
        results = await valid_sources[source]()
        from datetime import datetime
        _sync_status[source]["last_run"] = datetime.now().isoformat()
        _sync_status[source]["last_result"] = {
            "total": len(results),
            "created": sum(1 for r in results if r.get("status") == "created"),
            "updated": sum(1 for r in results if r.get("status") == "updated"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        }
        return {
            "message": f"{source} sync completed",
            "results": _sync_status[source]["last_result"],
        }
    except Exception as e:
        logger.error("Sync %s failed: %s", source, e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _sync_status[source]["running"] = False


@router.post("/trigger-all")
async def trigger_all_sync(user: Annotated[UserOut, Depends(get_current_user)]):
    """Trigger sync for all enabled Apple sources."""
    config = get_user_config()
    apple_cfg = config.get("apple_sync", {})
    sources = apple_cfg.get("sources", {})

    results = {}
    for source_key, enabled in sources.items():
        if not enabled:
            results[source_key] = {"status": "disabled"}
            continue
        source_name = f"apple_{source_key}"
        try:
            from app.sync.ingest_pipeline import (
                ingest_apple_notes,
                ingest_apple_reminders,
                ingest_apple_calendar,
            )
            fn_map = {
                "apple_notes": ingest_apple_notes,
                "apple_reminders": ingest_apple_reminders,
                "apple_calendar": ingest_apple_calendar,
            }
            if source_name in fn_map:
                res = await fn_map[source_name]()
                results[source_key] = {
                    "status": "ok",
                    "total": len(res),
                    "created": sum(1 for r in res if r.get("status") == "created"),
                }
        except Exception as e:
            results[source_key] = {"status": "error", "detail": str(e)}

    return {"results": results}


@router.post("/upload")
async def upload_and_ingest(
    file: UploadFile = File(...),
    user: Annotated[UserOut, Depends(get_current_user)] = None,
):
    """Upload a file and run it through the full ingestion pipeline."""
    from app.sync.ingest_pipeline import ingest_uploaded_file

    settings = get_settings()
    upload_dir = settings.resolved_data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(file.filename or "file")[1]
    saved_name = f"{uuid.uuid4()}{ext}"
    saved_path = upload_dir / saved_name

    content = await file.read()
    saved_path.write_bytes(content)

    try:
        result = await ingest_uploaded_file(
            file_path=str(saved_path),
            original_filename=file.filename or "file",
            content_type=file.content_type or "application/octet-stream",
            created_by=user.id if user else "upload",
        )
        return result
    except Exception as e:
        logger.error("Upload ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_sync_config(
    config_update: dict,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    """Update Apple sync configuration."""
    user_config = get_user_config()
    current = user_config.get("apple_sync", {})
    current.update(config_update)
    user_config.set("apple_sync", current)
    user_config.save()
    return {"message": "配置已更新", "config": current}
