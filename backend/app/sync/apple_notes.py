"""Apple Notes data extraction via macOS JXA (JavaScript for Automation)."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

JXA_SCRIPT = """
'use strict';
const Notes = Application('Notes');
const results = [];
const folders = Notes.folders();
for (let f = 0; f < folders.length; f++) {
    const folder = folders[f];
    const folderName = folder.name();
    const notes = folder.notes();
    for (let n = 0; n < notes.length; n++) {
        const note = notes[n];
        try {
            results.push({
                id: note.id(),
                name: note.name(),
                body: note.body(),
                folder: folderName,
                creationDate: note.creationDate().toISOString(),
                modificationDate: note.modificationDate().toISOString(),
            });
        } catch(e) {}
    }
}
JSON.stringify(results);
"""


class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-text converter for Apple Notes body."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip = True
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        import re
        text = "".join(self._parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_text(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


@dataclass
class AppleNote:
    id: str
    name: str
    body_html: str
    body_text: str
    folder: str
    creation_date: str
    modification_date: str
    attachments: list[str] = field(default_factory=list)


async def fetch_all_notes() -> list[AppleNote]:
    """Fetch all notes from Apple Notes via JXA. Must run on macOS."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", JXA_SCRIPT],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.error("JXA Notes error: %s", result.stderr)
            raise RuntimeError(f"Apple Notes JXA failed: {result.stderr[:300]}")

        raw = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JXA output: %s", e)
        raise RuntimeError("Apple Notes: invalid JXA output") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Apple Notes: JXA script timed out (>60s)")

    notes: list[AppleNote] = []
    for item in raw:
        body_html = item.get("body", "")
        notes.append(AppleNote(
            id=item["id"],
            name=item.get("name", "Untitled"),
            body_html=body_html,
            body_text=html_to_text(body_html),
            folder=item.get("folder", "Notes"),
            creation_date=item.get("creationDate", ""),
            modification_date=item.get("modificationDate", ""),
        ))

    logger.info("Fetched %d notes from Apple Notes", len(notes))
    return notes
