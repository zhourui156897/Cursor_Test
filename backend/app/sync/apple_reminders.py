"""Apple Reminders data extraction via macOS JXA."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

JXA_SCRIPT = """
'use strict';
const Reminders = Application('Reminders');
const results = [];
const lists = Reminders.lists();
for (let i = 0; i < lists.length; i++) {
    const list = lists[i];
    const listName = list.name();
    const items = list.reminders();
    for (let j = 0; j < items.length; j++) {
        const r = items[j];
        try {
            const obj = {
                id: r.id(),
                name: r.name(),
                body: r.body() || '',
                completed: r.completed(),
                completionDate: null,
                dueDate: null,
                priority: r.priority(),
                list: listName,
                creationDate: r.creationDate() ? r.creationDate().toISOString() : null,
                modificationDate: r.modificationDate() ? r.modificationDate().toISOString() : null,
            };
            try { if (r.completionDate()) obj.completionDate = r.completionDate().toISOString(); } catch(e) {}
            try { if (r.dueDate()) obj.dueDate = r.dueDate().toISOString(); } catch(e) {}
            results.push(obj);
        } catch(e) {}
    }
}
JSON.stringify(results);
"""


@dataclass
class AppleReminder:
    id: str
    name: str
    body: str
    completed: bool
    completion_date: str | None
    due_date: str | None
    priority: int
    list_name: str
    creation_date: str | None
    modification_date: str | None
    tags: list[str] = field(default_factory=list)


async def fetch_all_reminders() -> list[AppleReminder]:
    """Fetch all reminders from Apple Reminders via JXA."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", JXA_SCRIPT],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.error("JXA Reminders error: %s", result.stderr)
            raise RuntimeError(f"Apple Reminders JXA failed: {result.stderr[:300]}")

        raw = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JXA output: %s", e)
        raise RuntimeError("Apple Reminders: invalid JXA output") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Apple Reminders: JXA script timed out (>60s)")

    reminders: list[AppleReminder] = []
    for item in raw:
        reminders.append(AppleReminder(
            id=item["id"],
            name=item.get("name", ""),
            body=item.get("body", ""),
            completed=item.get("completed", False),
            completion_date=item.get("completionDate"),
            due_date=item.get("dueDate"),
            priority=item.get("priority", 0),
            list_name=item.get("list", "Reminders"),
            creation_date=item.get("creationDate"),
            modification_date=item.get("modificationDate"),
        ))

    logger.info("Fetched %d reminders from Apple Reminders", len(reminders))
    return reminders
