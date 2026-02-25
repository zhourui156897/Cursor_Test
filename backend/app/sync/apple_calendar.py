"""Apple Calendar data extraction and creation via macOS JXA."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _build_jxa_script(limit: int = 50, order: str = "newest", days_back: int = 30, days_forward: int = 90) -> str:
    sort_dir = "desc" if order == "newest" else "asc"
    return f"""
'use strict';
var Calendar = Application("Calendar");
var now = new Date();
var start = new Date(now.getTime() - {days_back} * 86400000);
var end = new Date(now.getTime() + {days_forward} * 86400000);
var allEvents = [];
var cals = Calendar.calendars();
for (var c = 0; c < cals.length; c++) {{
    var cal = cals[c];
    var calName = cal.name();
    var events = cal.events.whose({{
        _and: [
            {{ startDate: {{ _greaterThan: start }} }},
            {{ startDate: {{ _lessThan: end }} }}
        ]
    }})();
    for (var e = 0; e < events.length; e++) {{
        var ev = events[e];
        try {{
            allEvents.push({{
                ref: ev,
                cal: calName,
                ts: ev.startDate().getTime()
            }});
        }} catch(e2) {{}}
    }}
}}
allEvents.sort(function(a, b) {{
    return "{sort_dir}" === "desc" ? b.ts - a.ts : a.ts - b.ts;
}});
var results = [];
var count = Math.min({limit}, allEvents.length);
for (var i = 0; i < count; i++) {{
    var ev = allEvents[i].ref;
    try {{
        results.push({{
            id: ev.uid(),
            summary: ev.summary(),
            description: ev.description() || '',
            location: ev.location() || '',
            startDate: ev.startDate().toISOString(),
            endDate: ev.endDate().toISOString(),
            allDay: ev.alldayEvent(),
            calendar: allEvents[i].cal,
            recurrence: ev.recurrence() || '',
        }});
    }} catch(e2) {{}}
}}
JSON.stringify(results);
"""


CREATE_EVENT_JXA = """
'use strict';
var Calendar = Application("Calendar");
var targetCal = null;
var calName = "{calendar}";
if (calName) {{
    var cals = Calendar.calendars();
    for (var i = 0; i < cals.length; i++) {{
        if (cals[i].name() === calName) {{
            targetCal = cals[i];
            break;
        }}
    }}
}}
if (!targetCal) {{
    targetCal = Calendar.calendars()[0];
}}
var evt = Calendar.Event({{
    summary: "{title}",
    startDate: new Date("{start_date}"),
    endDate: new Date("{end_date}"),
    description: "{description}",
    location: "{location}",
    alldayEvent: {all_day},
}});
targetCal.events.push(evt);
JSON.stringify({{id: evt.uid(), summary: evt.summary()}});
"""


@dataclass
class AppleCalendarEvent:
    id: str
    summary: str
    description: str
    location: str
    start_date: str
    end_date: str
    all_day: bool
    calendar_name: str
    recurrence: str


async def fetch_all_events(
    limit: int = 50,
    order: str = "newest",
    days_back: int = 30,
    days_forward: int = 90,
) -> list[AppleCalendarEvent]:
    """Fetch calendar events from Apple Calendar via JXA. Optional time range (days_back/days_forward from now)."""
    script = _build_jxa_script(limit=limit, order=order, days_back=days_back, days_forward=days_forward)
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("JXA Calendar error: %s", result.stderr)
            raise RuntimeError(f"Apple Calendar JXA failed: {result.stderr[:300]}")

        stdout = result.stdout.strip()
        if not stdout:
            return []
        raw = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JXA output: %s", e)
        raise RuntimeError("Apple Calendar: invalid JXA output") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Apple Calendar: JXA script timed out (>120s)")

    events: list[AppleCalendarEvent] = []
    for item in raw:
        events.append(AppleCalendarEvent(
            id=item["id"],
            summary=item.get("summary", ""),
            description=item.get("description", ""),
            location=item.get("location", ""),
            start_date=item.get("startDate", ""),
            end_date=item.get("endDate", ""),
            all_day=item.get("allDay", False),
            calendar_name=item.get("calendar", "Calendar"),
            recurrence=item.get("recurrence", ""),
        ))

    logger.info("Fetched %d events (limit=%d, order=%s)", len(events), limit, order)
    return events


def _jxa_escape(s: str) -> str:
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


async def create_event(
    title: str, start_date: str, end_date: str,
    description: str = "", location: str = "",
    calendar: str = "", all_day: bool = False,
) -> dict:
    """Create a new event in Apple Calendar."""
    # JXA new Date() accepts ISO strings; strip timezone if needed for compatibility
    start = (start_date or "").strip()[:25]
    end = (end_date or "").strip()[:25]
    if not start or not end:
        raise ValueError("start_date and end_date are required")
    escaped = {
        "title": _jxa_escape(title or "新事件"),
        "start_date": start.replace('"', ""),
        "end_date": end.replace('"', ""),
        "description": _jxa_escape(description or ""),
        "location": _jxa_escape(location or ""),
        "calendar": _jxa_escape(calendar or ""),
        "all_day": "true" if all_day else "false",
    }
    script = CREATE_EVENT_JXA.format(**escaped)

    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create event: {result.stderr[:300]}")

        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
        return {"status": "created", "title": title}
    except Exception as e:
        logger.error("Create calendar event failed: %s", e)
        raise
