"""Apple Reminders data extraction and creation via macOS JXA."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


LIST_LISTS_JXA = """
'use strict';
var Reminders = Application("Reminders");
var lists = Reminders.lists();
var names = [];
for (var i = 0; i < lists.length; i++) { names.push(lists[i].name()); }
JSON.stringify(names);
"""


def _build_jxa_script(limit: int = 50, order: str = "newest", list_whitelist: list[str] | None = None) -> str:
    """Build JXA script: collect all reminders, sort by modification date, then take limit."""
    sort_dir = "desc" if order == "newest" else "asc"
    list_filter = ""
    if list_whitelist:
        escaped = json.dumps(list_whitelist)
        list_filter = f"var allowedLists = {escaped};"
    return f"""
'use strict';
var Reminders = Application("Reminders");
{list_filter}
var all = [];
var lists = Reminders.lists();
for (var i = 0; i < lists.length; i++) {{
    var list = lists[i];
    var listName = list.name();
    if (typeof allowedLists !== 'undefined' && allowedLists.indexOf(listName) < 0) continue;
    var items = list.reminders();
    for (var j = 0; j < items.length; j++) {{
        var r = items[j];
        try {{
            var mod = r.modificationDate() ? r.modificationDate().getTime() : 0;
            var obj = {{
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
                _mod: mod,
            }};
            try {{ if (r.completionDate()) obj.completionDate = r.completionDate().toISOString(); }} catch(e) {{}}
            try {{ if (r.dueDate()) obj.dueDate = r.dueDate().toISOString(); }} catch(e) {{}}
            all.push(obj);
        }} catch(e) {{}}
    }}
}}
all.sort(function(a, b) {{ return "{sort_dir}" === "desc" ? b._mod - a._mod : a._mod - b._mod; }});
var results = all.slice(0, {limit});
results.forEach(function(o) {{ delete o._mod; }});
JSON.stringify(results);
"""


CREATE_REMINDER_JXA = """
'use strict';
var Reminders = Application("Reminders");
var targetList = null;
var listName = "{list_name}";
if (listName) {{
    var lists = Reminders.lists();
    for (var i = 0; i < lists.length; i++) {{
        if (lists[i].name() === listName) {{
            targetList = lists[i];
            break;
        }}
    }}
}}
if (!targetList) {{
    targetList = Reminders.defaultList();
}}
var props = {{name: "{title}", body: "{body}"}};
{due_date_line}
{priority_line}
var reminder = Reminders.Reminder(props);
targetList.reminders.push(reminder);
JSON.stringify({{id: reminder.id(), name: reminder.name()}});
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


async def list_reminder_lists() -> list[str]:
    """List Apple Reminders list names (for user to choose which to sync)."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", LIST_LISTS_JXA],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return []
        raw = result.stdout.strip()
        if not raw:
            return []
        return json.loads(raw)
    except Exception:
        return []


def _filter_reminders_by_due(
    reminders: list[AppleReminder],
    due_after: str | None = None,
    due_before: str | None = None,
) -> list[AppleReminder]:
    """Filter reminders by due date range (ISO strings)."""
    if not due_after and not due_before:
        return reminders
    out = []
    for r in reminders:
        d = r.due_date
        if not d:
            continue
        if due_after and d < due_after:
            continue
        if due_before and d > due_before:
            continue
        out.append(r)
    return out


async def fetch_all_reminders(
    limit: int = 50,
    order: str = "newest",
    list_names: list[str] | None = None,
    due_after: str | None = None,
    due_before: str | None = None,
) -> list[AppleReminder]:
    """Fetch reminders via JXA with optional list filter and due date range (filtered in Python)."""
    script = _build_jxa_script(limit=min(limit * 2, 200), order=order, list_whitelist=list_names)
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("JXA Reminders error: %s", result.stderr)
            raise RuntimeError(f"Apple Reminders JXA failed: {result.stderr[:300]}")

        stdout = result.stdout.strip()
        if not stdout:
            return []
        raw = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JXA output: %s", e)
        raise RuntimeError("Apple Reminders: invalid JXA output") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Apple Reminders: JXA script timed out (>120s)")

    reminders = []
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
    reminders = _filter_reminders_by_due(reminders, due_after=due_after, due_before=due_before)
    reminders = reminders[:limit]
    logger.info("Fetched %d reminders (limit=%d, order=%s)", len(reminders), limit, order)
    return reminders


def _jxa_escape(s: str) -> str:
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


async def create_reminder(title: str, body: str = "", list_name: str = "", due_date: str = "", priority: int = 0) -> dict:
    """Create a new reminder in Apple Reminders."""
    escaped_title = _jxa_escape(title or "新提醒")
    escaped_body = _jxa_escape(body or "")
    escaped_list = _jxa_escape(list_name or "")

    due_date_line = ""
    if due_date and due_date.strip():
        safe_date = due_date.strip().replace('"', "")
        due_date_line = f'props.dueDate = new Date("{safe_date}");'

    priority_line = ""
    if priority:
        priority_line = f"props.priority = {int(priority)};"

    script = CREATE_REMINDER_JXA.format(
        title=escaped_title, body=escaped_body, list_name=escaped_list,
        due_date_line=due_date_line, priority_line=priority_line,
    )

    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create reminder: {result.stderr[:300]}")

        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
        return {"status": "created", "title": title}
    except Exception as e:
        logger.error("Create reminder failed: %s", e)
        raise
