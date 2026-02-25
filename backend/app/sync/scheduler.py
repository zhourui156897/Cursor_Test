"""Scheduled sync: run Apple sync at interval using persisted scope."""

from __future__ import annotations

import asyncio
import logging

from app.config import get_user_config
from app.sync.ingest_pipeline import (
    ingest_apple_notes,
    ingest_apple_reminders,
    ingest_apple_calendar,
)

logger = logging.getLogger(__name__)


async def run_scheduled_sync() -> None:
    """Run sync for all enabled Apple sources using persisted sync_scope. No auth."""
    config = get_user_config()
    apple = config.get("apple_sync", {})
    if not apple.get("auto_sync", False):
        return
    sources_cfg = apple.get("sources", {})
    scope = apple.get("sync_scope", {})

    for source_key, enabled in sources_cfg.items():
        if not enabled:
            continue
        source = f"apple_{source_key}"
        opts = scope.get(source, {}) or scope.get(source_key, {})
        limit = int(opts.get("limit", 20))
        order = str(opts.get("order", "newest"))

        try:
            if source_key == "notes":
                folders = opts.get("folder_whitelist")
                if isinstance(folders, str):
                    folders = [s.strip() for s in folders.split(",") if s.strip()] or None
                await ingest_apple_notes(limit=limit, order=order, folder_whitelist=folders)
            elif source_key == "reminders":
                lists = opts.get("list_names")
                if isinstance(lists, str):
                    lists = [s.strip() for s in lists.split(",") if s.strip()] or None
                await ingest_apple_reminders(
                    limit=limit, order=order,
                    list_names=lists,
                    due_after=opts.get("due_after") or None,
                    due_before=opts.get("due_before") or None,
                )
            elif source_key == "calendar":
                await ingest_apple_calendar(
                    limit=limit, order=order,
                    days_back=int(opts.get("days_back", 30)),
                    days_forward=int(opts.get("days_forward", 90)),
                )
        except Exception as e:
            logger.warning("Scheduled sync %s failed: %s", source, e)
