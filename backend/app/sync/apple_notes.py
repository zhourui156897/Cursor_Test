"""Apple Notes data extraction via macOS JXA (JavaScript for Automation)."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


LIST_FOLDERS_JXA = """
'use strict';
var Notes = Application("Notes");
var folders = Notes.folders();
var names = [];
for (var i = 0; i < folders.length; i++) { names.push(folders[i].name()); }
JSON.stringify(names);
"""


def _build_jxa_script(limit: int = 50, order: str = "newest", folder_whitelist: list[str] | None = None) -> str:
    sort_dir = "desc" if order == "newest" else "asc"
    folder_filter = ""
    if folder_whitelist:
        escaped = json.dumps(folder_whitelist)
        folder_filter = f"var allowedFolders = {escaped};"
    return f"""
'use strict';
var Notes = Application("Notes");
var results = [];
{folder_filter}
var folders = Notes.folders();
var limit = {limit};
var allNotes = [];
for (var f = 0; f < folders.length; f++) {{
    var folder = folders[f];
    var folderName = folder.name();
    if (typeof allowedFolders !== 'undefined' && allowedFolders.indexOf(folderName) < 0) continue;
    var notes = folder.notes();
    for (var n = 0; n < notes.length; n++) {{
        var note = notes[n];
        try {{
            allNotes.push({{
                ref: note,
                folder: folderName,
                mod: note.modificationDate().getTime()
            }});
        }} catch(e) {{}}
    }}
}}
allNotes.sort(function(a, b) {{
    return "{sort_dir}" === "desc" ? b.mod - a.mod : a.mod - b.mod;
}});
var count = Math.min(limit, allNotes.length);
for (var i = 0; i < count; i++) {{
    var item = allNotes[i];
    var note = item.ref;
    try {{
        var bodyHtml = note.body();
        if (bodyHtml && bodyHtml.length > 50000) bodyHtml = bodyHtml.substring(0, 50000);
        results.push({{
            id: note.id(),
            name: note.name(),
            body: bodyHtml,
            folder: item.folder,
            creationDate: note.creationDate().toISOString(),
            modificationDate: note.modificationDate().toISOString(),
        }});
    }} catch(e) {{}}
}}
JSON.stringify(results);
"""


CREATE_NOTE_JXA = """
'use strict';
var Notes = Application("Notes");
var targetFolder = null;
var folderName = "{folder}";
if (folderName) {{
    var folders = Notes.folders();
    for (var i = 0; i < folders.length; i++) {{
        if (folders[i].name() === folderName) {{
            targetFolder = folders[i];
            break;
        }}
    }}
}}
var note = Notes.Note({{name: "{title}", body: "{body}"}});
if (targetFolder) {{
    targetFolder.notes.push(note);
}} else {{
    Notes.notes.push(note);
}}
JSON.stringify({{id: note.id(), name: note.name()}});
"""


class _HTMLStripper(HTMLParser):
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


async def list_note_folders() -> list[str]:
    """List Apple Notes folder names (for user to choose which to sync)."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", LIST_FOLDERS_JXA],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            logger.warning("JXA list folders error: %s", result.stderr)
            return []
        raw = result.stdout.strip()
        if not raw:
            return []
        return json.loads(raw)
    except Exception as e:
        logger.warning("list_note_folders failed: %s", e)
        return []


async def fetch_all_notes(limit: int = 50, order: str = "newest", folder_whitelist: list[str] | None = None) -> list[AppleNote]:
    """Fetch notes from Apple Notes via JXA with limit, ordering, and optional folder filter."""
    script = _build_jxa_script(limit=limit, order=order, folder_whitelist=folder_whitelist)
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("JXA Notes error: %s", result.stderr)
            raise RuntimeError(f"Apple Notes JXA failed: {result.stderr[:300]}")

        stdout = result.stdout.strip()
        if not stdout:
            logger.warning("JXA Notes returned empty output")
            return []
        raw = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JXA output (len=%d): %s", len(result.stdout), e)
        raise RuntimeError("Apple Notes: invalid JXA output") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Apple Notes: JXA script timed out (>120s)")

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

    logger.info("Fetched %d notes from Apple Notes (limit=%d, order=%s)", len(notes), limit, order)
    return notes


def _jxa_escape(s: str) -> str:
    """Escape string for use inside JXA double-quoted string."""
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


async def create_note(title: str, body: str, folder: str = "") -> dict:
    """Create a new note in Apple Notes."""
    escaped_title = _jxa_escape(title or "新备忘录")
    escaped_body = _jxa_escape(body or "")
    escaped_folder = _jxa_escape(folder or "")

    script = CREATE_NOTE_JXA.format(title=escaped_title, body=escaped_body, folder=escaped_folder)

    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.error("Create note JXA error: %s", result.stderr)
            raise RuntimeError(f"Failed to create note: {result.stderr[:300]}")

        stdout = result.stdout.strip()
        if stdout:
            return json.loads(stdout)
        return {"status": "created", "title": title}
    except Exception as e:
        logger.error("Create note failed: %s", e)
        raise
