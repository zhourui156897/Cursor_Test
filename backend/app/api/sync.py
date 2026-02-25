"""Sync & ingestion trigger API: manual sync, auto-sync config, upload, Apple data creation."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, get_admin_user
from app.models.user import UserOut
from app.config import get_settings, get_user_config
from app.sync.messages import APPLE_JXA_USER_MESSAGE

router = APIRouter()
logger = logging.getLogger(__name__)

_sync_status: dict = {
    "apple_notes": {"running": False, "last_run": None, "last_result": None},
    "apple_reminders": {"running": False, "last_run": None, "last_result": None},
    "apple_calendar": {"running": False, "last_run": None, "last_result": None},
}


@router.get("/status")
async def get_sync_status(_: Annotated[UserOut, Depends(get_current_user)]):
    config = get_user_config()
    apple_cfg = config.get("apple_sync", {})
    return {
        "config": {
            "enabled": apple_cfg.get("enabled", False),
            "auto_sync": apple_cfg.get("auto_sync", False),
            "interval_minutes": apple_cfg.get("interval_minutes", 30),
            "sources": apple_cfg.get("sources", {}),
            "sync_scope": apple_cfg.get("sync_scope", {}),
        },
        "status": _sync_status,
    }


@router.get("/apple/note-folders")
async def list_apple_note_folders(_: Annotated[UserOut, Depends(get_current_user)]):
    """List Apple Notes folder names for user to choose which to sync (first-time or selective sync)."""
    from app.sync.apple_notes import list_note_folders
    folders = await list_note_folders()
    return {"folders": folders}


@router.get("/apple/reminder-lists")
async def list_apple_reminder_lists(_: Annotated[UserOut, Depends(get_current_user)]):
    """List Apple Reminders list names for user to choose which to sync."""
    from app.sync.apple_reminders import list_reminder_lists
    lists = await list_reminder_lists()
    return {"lists": lists}


@router.post("/trigger/{source}")
async def trigger_sync(
    source: str,
    user: Annotated[UserOut, Depends(get_current_user)],
    limit: int = Query(default=20, ge=1, le=500, description="最多同步条数"),
    order: str = Query(default="newest", pattern="^(newest|oldest)$", description="排序: newest/oldest"),
    # 备忘录：要同步的文件夹（空=全部）
    folder_whitelist: str = Query(default="", description="备忘录文件夹名，逗号分隔，空为全部"),
    # 日历：时间范围（天）
    days_back: int = Query(default=30, ge=0, le=365, description="日历：从今天往前多少天"),
    days_forward: int = Query(default=90, ge=0, le=365, description="日历：从今天往后多少天"),
    # 待办：要同步的列表 + 截止范围
    list_names: str = Query(default="", description="待办列表名，逗号分隔，空为全部"),
    due_after: str = Query(default="", description="待办截止范围起 ISO 日期"),
    due_before: str = Query(default="", description="待办截止范围止 ISO 日期"),
):
    """Manually trigger sync. Optional: note folders, calendar range, reminder lists + due range."""
    from app.sync.ingest_pipeline import (
        ingest_apple_notes, ingest_apple_reminders, ingest_apple_calendar,
    )

    valid_sources = {
        "apple_notes": ingest_apple_notes,
        "apple_reminders": ingest_apple_reminders,
        "apple_calendar": ingest_apple_calendar,
    }

    if source not in valid_sources:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    if _sync_status[source]["running"]:
        raise HTTPException(status_code=409, detail=f"{source} sync already running")

    _sync_status[source]["running"] = True
    try:
        if source == "apple_notes":
            folders = [s.strip() for s in folder_whitelist.split(",") if s.strip()] or None
            results = await ingest_apple_notes(limit=limit, order=order, folder_whitelist=folders)
        elif source == "apple_reminders":
            lists = [s.strip() for s in list_names.split(",") if s.strip()] or None
            results = await ingest_apple_reminders(
                limit=limit, order=order,
                list_names=lists,
                due_after=due_after.strip() or None,
                due_before=due_before.strip() or None,
            )
        elif source == "apple_calendar":
            results = await ingest_apple_calendar(
                limit=limit, order=order,
                days_back=days_back, days_forward=days_forward,
            )
        else:
            results = []
        from datetime import datetime
        _sync_status[source]["last_run"] = datetime.now().isoformat()
        _sync_status[source]["last_result"] = {
            "total": len(results),
            "created": sum(1 for r in results if r.get("status") == "created"),
            "updated": sum(1 for r in results if r.get("status") == "updated"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        }
        # 持久化本次同步范围，供下次手动同步预填与定时同步使用
        user_config = get_user_config()
        apple_cfg = user_config.get("apple_sync", {})
        scope = apple_cfg.get("sync_scope", {})
        scope[source] = {
            "limit": limit,
            "order": order,
            "folder_whitelist": folder_whitelist if source == "apple_notes" else "",
            "days_back": days_back if source == "apple_calendar" else 30,
            "days_forward": days_forward if source == "apple_calendar" else 90,
            "list_names": list_names if source == "apple_reminders" else "",
            "due_after": due_after.strip() if source == "apple_reminders" else "",
            "due_before": due_before.strip() if source == "apple_reminders" else "",
        }
        apple_cfg["sync_scope"] = scope
        user_config.set("apple_sync", apple_cfg)
        user_config.save()
        return {
            "message": f"{source} sync completed",
            "results": _sync_status[source]["last_result"],
        }
    except Exception as e:
        logger.error("Sync %s failed: %s", source, e)
        detail = APPLE_JXA_USER_MESSAGE if _is_apple_jxa_error(e) else str(e)
        raise HTTPException(status_code=503, detail=detail)
    finally:
        _sync_status[source]["running"] = False


@router.post("/trigger-all")
async def trigger_all_sync(
    user: Annotated[UserOut, Depends(get_current_user)],
    limit: int = Query(default=20, ge=1, le=500),
    order: str = Query(default="newest", pattern="^(newest|oldest)$"),
):
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
                ingest_apple_notes, ingest_apple_reminders, ingest_apple_calendar,
            )
            fn_map = {
                "apple_notes": ingest_apple_notes,
                "apple_reminders": ingest_apple_reminders,
                "apple_calendar": ingest_apple_calendar,
            }
            if source_name in fn_map:
                res = await fn_map[source_name](limit=limit, order=order)
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


# --- Apple Data Creation (bidirectional) ---

class CreateNoteRequest(BaseModel):
    title: str
    body: str = ""
    folder: str = ""

class CreateReminderRequest(BaseModel):
    title: str
    body: str = ""
    list_name: str = ""
    due_date: str = ""
    priority: int = 0

class CreateEventRequest(BaseModel):
    title: str
    start_date: str
    end_date: str
    description: str = ""
    location: str = ""
    calendar: str = ""
    all_day: bool = False


def _is_apple_jxa_error(e: Exception) -> bool:
    s = str(e).lower()
    return "jxa" in s or "osascript" in s or "apple notes" in s or "apple reminders" in s or "apple calendar" in s


@router.post("/create/note")
async def create_apple_note(
    req: CreateNoteRequest,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    """Create a new note in Apple Notes app."""
    from app.sync.apple_notes import create_note
    try:
        result = await create_note(title=req.title, body=req.body, folder=req.folder)
        return {"message": "备忘录已创建", "result": result}
    except Exception as e:
        logger.exception("Create Apple note failed")
        detail = APPLE_JXA_USER_MESSAGE if _is_apple_jxa_error(e) else str(e)
        raise HTTPException(status_code=503, detail=detail)


@router.post("/create/reminder")
async def create_apple_reminder(
    req: CreateReminderRequest,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    """Create a new reminder in Apple Reminders app."""
    from app.sync.apple_reminders import create_reminder
    try:
        result = await create_reminder(
            title=req.title, body=req.body, list_name=req.list_name,
            due_date=req.due_date, priority=req.priority,
        )
        return {"message": "提醒事项已创建", "result": result}
    except Exception as e:
        logger.exception("Create Apple reminder failed")
        detail = APPLE_JXA_USER_MESSAGE if _is_apple_jxa_error(e) else str(e)
        raise HTTPException(status_code=503, detail=detail)


@router.post("/create/event")
async def create_apple_event(
    req: CreateEventRequest,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    """Create a new event in Apple Calendar app."""
    from app.sync.apple_calendar import create_event
    try:
        result = await create_event(
            title=req.title, start_date=req.start_date, end_date=req.end_date,
            description=req.description, location=req.location,
            calendar=req.calendar, all_day=req.all_day,
        )
        return {"message": "日历事件已创建", "result": result}
    except Exception as e:
        logger.exception("Create Apple event failed")
        detail = APPLE_JXA_USER_MESSAGE if _is_apple_jxa_error(e) else str(e)
        raise HTTPException(status_code=503, detail=detail)


@router.put("/config")
async def update_sync_config(
    config_update: dict,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    user_config = get_user_config()
    current = user_config.get("apple_sync", {})
    current.update(config_update)
    user_config.set("apple_sync", current)
    user_config.save()
    return {"message": "配置已更新", "config": current}
