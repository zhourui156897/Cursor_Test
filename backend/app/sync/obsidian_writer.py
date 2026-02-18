"""Generate Obsidian-compatible Markdown notes with YAML frontmatter."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import yaml

from app.config import get_settings

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip(". ")
    return name[:100] or "Untitled"


def build_frontmatter(metadata: dict) -> str:
    """Serialize metadata dict into YAML frontmatter block."""
    clean = {k: v for k, v in metadata.items() if v is not None}
    dumped = yaml.dump(clean, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{dumped}---\n"


def build_note_markdown(
    *,
    title: str,
    content: str,
    source: str,
    source_id: str | None = None,
    tags: list[str] | None = None,
    extra_meta: dict | None = None,
) -> str:
    """Build a complete Obsidian note (frontmatter + body)."""
    meta: dict = {
        "title": title,
        "source": source,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "review_status": "pending",
    }
    if source_id:
        meta["source_id"] = source_id
    if tags:
        meta["tags"] = tags
    if extra_meta:
        meta.update(extra_meta)

    body = f"# {title}\n\n{content}"
    return build_frontmatter(meta) + "\n" + body


async def write_note_to_vault(
    *,
    title: str,
    content: str,
    source: str,
    source_id: str | None = None,
    folder: str = "",
    tags: list[str] | None = None,
    extra_meta: dict | None = None,
) -> Path:
    """Write a Markdown note into the Obsidian Vault and return the file path."""
    settings = get_settings()
    vault = settings.resolved_vault_path

    if folder:
        target_dir = vault / folder
    else:
        source_folders = {
            "apple_notes": "Resources/Apple Notes",
            "apple_reminders": "Resources/Apple Reminders",
            "apple_calendar": "Resources/Apple Calendar",
            "upload": "Resources/Uploads",
        }
        target_dir = vault / source_folders.get(source, "Resources")

    target_dir.mkdir(parents=True, exist_ok=True)

    filename = _sanitize_filename(title) + ".md"
    file_path = target_dir / filename

    # Avoid overwriting — append numeric suffix if exists
    counter = 1
    while file_path.exists():
        file_path = target_dir / f"{_sanitize_filename(title)}_{counter}.md"
        counter += 1

    md = build_note_markdown(
        title=title,
        content=content,
        source=source,
        source_id=source_id,
        tags=tags,
        extra_meta=extra_meta,
    )

    file_path.write_text(md, encoding="utf-8")
    logger.info("Written Obsidian note: %s", file_path)

    # Return path relative to vault
    return file_path.relative_to(vault)


async def update_note_frontmatter(
    obsidian_path: str,
    updates: dict,
) -> bool:
    """Update the YAML frontmatter of an existing Obsidian note.

    Reads the file, patches the frontmatter fields, and writes back.
    Returns True on success.
    """
    settings = get_settings()
    file_path = settings.resolved_vault_path / obsidian_path

    if not file_path.exists():
        logger.warning("Cannot update frontmatter, file missing: %s", file_path)
        return False

    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read note %s: %s", file_path, e)
        return False

    # Parse existing frontmatter
    if text.startswith("---\n"):
        end_idx = text.index("\n---\n", 4)
        fm_str = text[4:end_idx]
        body = text[end_idx + 5:]
        try:
            fm = yaml.safe_load(fm_str) or {}
        except yaml.YAMLError:
            fm = {}
    else:
        fm = {}
        body = text

    fm.update(updates)

    new_text = build_frontmatter(fm) + "\n" + body.lstrip("\n")
    file_path.write_text(new_text, encoding="utf-8")
    logger.info("Updated frontmatter for: %s", obsidian_path)
    return True


def note_from_apple_note(note) -> dict:
    """Convert AppleNote dataclass to write_note_to_vault kwargs."""
    return dict(
        title=note.name,
        content=note.body_text,
        source="apple_notes",
        source_id=note.id,
        folder=f"Resources/Apple Notes/{_sanitize_filename(note.folder)}",
        extra_meta={
            "apple_folder": note.folder,
            "apple_created": note.creation_date,
            "apple_modified": note.modification_date,
        },
    )


def note_from_apple_reminder(reminder) -> dict:
    """Convert AppleReminder dataclass to write_note_to_vault kwargs."""
    lines = [reminder.body] if reminder.body else []
    if reminder.due_date:
        lines.append(f"\n**截止日期**: {reminder.due_date}")
    if reminder.completed:
        lines.append(f"**状态**: 已完成")
        if reminder.completion_date:
            lines.append(f"**完成时间**: {reminder.completion_date}")
    else:
        lines.append(f"**状态**: 待完成")

    priority_map = {0: "无", 1: "高", 5: "中", 9: "低"}
    lines.append(f"**优先级**: {priority_map.get(reminder.priority, str(reminder.priority))}")

    return dict(
        title=reminder.name,
        content="\n".join(lines),
        source="apple_reminders",
        source_id=reminder.id,
        folder="Resources/Apple Reminders",
        extra_meta={
            "completed": reminder.completed,
            "due_date": reminder.due_date,
            "priority": reminder.priority,
            "reminder_list": reminder.list_name,
        },
    )


def note_from_apple_event(event) -> dict:
    """Convert AppleCalendarEvent dataclass to write_note_to_vault kwargs."""
    lines = []
    lines.append(f"**时间**: {event.start_date} → {event.end_date}")
    if event.all_day:
        lines.append("**全天事件**")
    if event.location:
        lines.append(f"**地点**: {event.location}")
    if event.description:
        lines.append(f"\n{event.description}")

    return dict(
        title=event.summary or "Untitled Event",
        content="\n".join(lines),
        source="apple_calendar",
        source_id=event.id,
        folder="Resources/Apple Calendar",
        extra_meta={
            "start_date": event.start_date,
            "end_date": event.end_date,
            "all_day": event.all_day,
            "location": event.location,
            "calendar": event.calendar_name,
        },
    )
