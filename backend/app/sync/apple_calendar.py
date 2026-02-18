"""Apple Calendar data extraction via macOS JXA."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Fetch events from the past 30 days + next 90 days by default
JXA_SCRIPT = """
'use strict';
const Calendar = Application('Calendar');
const now = new Date();
const start = new Date(now.getTime() - 30 * 86400000);
const end = new Date(now.getTime() + 90 * 86400000);
const results = [];
const cals = Calendar.calendars();
for (let c = 0; c < cals.length; c++) {
    const cal = cals[c];
    const calName = cal.name();
    const events = cal.events.whose({
        _and: [
            { startDate: { _greaterThan: start } },
            { startDate: { _lessThan: end } }
        ]
    })();
    for (let e = 0; e < events.length; e++) {
        const ev = events[e];
        try {
            results.push({
                id: ev.uid(),
                summary: ev.summary(),
                description: ev.description() || '',
                location: ev.location() || '',
                startDate: ev.startDate().toISOString(),
                endDate: ev.endDate().toISOString(),
                allDay: ev.alldayEvent(),
                calendar: calName,
                recurrence: ev.recurrence() || '',
            });
        } catch(e2) {}
    }
}
JSON.stringify(results);
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


async def fetch_all_events() -> list[AppleCalendarEvent]:
    """Fetch calendar events from Apple Calendar via JXA."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", JXA_SCRIPT],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.error("JXA Calendar error: %s", result.stderr)
            raise RuntimeError(f"Apple Calendar JXA failed: {result.stderr[:300]}")

        raw = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JXA output: %s", e)
        raise RuntimeError("Apple Calendar: invalid JXA output") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Apple Calendar: JXA script timed out (>60s)")

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

    logger.info("Fetched %d events from Apple Calendar", len(events))
    return events
