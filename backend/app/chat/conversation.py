"""Conversation management: history storage, multi-turn context, summarization."""

from __future__ import annotations

import json
import logging
import uuid

from app.storage.sqlite_client import get_db

logger = logging.getLogger(__name__)


async def create_conversation(user_id: str = "", title: str = "") -> str:
    """Create a new conversation. Returns conversation ID."""
    db = await get_db()
    conv_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO conversations (id, user_id, title, created_at, updated_at)
           VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
        (conv_id, user_id, title or "新对话"),
    )
    await db.commit()
    return conv_id


async def list_conversations(user_id: str = "", limit: int = 50) -> list[dict]:
    """List conversations for a user, most recent first."""
    db = await get_db()
    if user_id:
        cursor = await db.execute(
            """SELECT id, title, created_at, updated_at, summary
               FROM conversations WHERE user_id = ?
               ORDER BY updated_at DESC LIMIT ?""",
            (user_id, limit),
        )
    else:
        cursor = await db.execute(
            """SELECT id, title, created_at, updated_at, summary
               FROM conversations
               ORDER BY updated_at DESC LIMIT ?""",
            (limit,),
        )
    return [dict(r) for r in await cursor.fetchall()]


async def get_conversation_messages(
    conversation_id: str,
    limit: int = 100,
) -> list[dict]:
    """Get all messages in a conversation."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, role, content, tool_calls, tool_results, sources, created_at
           FROM messages
           WHERE conversation_id = ?
           ORDER BY created_at ASC LIMIT ?""",
        (conversation_id, limit),
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    for row in rows:
        for key in ("tool_calls", "tool_results", "sources"):
            if row.get(key) and isinstance(row[key], str):
                try:
                    row[key] = json.loads(row[key])
                except json.JSONDecodeError:
                    pass
    return rows


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
    tool_calls: list[dict] | None = None,
    tool_results: list[dict] | None = None,
) -> str:
    """Add a message to a conversation. Returns message ID."""
    db = await get_db()
    msg_id = str(uuid.uuid4())

    await db.execute(
        """INSERT INTO messages
           (id, conversation_id, role, content, sources, tool_calls, tool_results, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            msg_id,
            conversation_id,
            role,
            content,
            json.dumps(sources, ensure_ascii=False) if sources else None,
            json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
        ),
    )

    title_text = content[:30] + "..." if len(content) > 30 else content
    await db.execute(
        """UPDATE conversations
           SET updated_at = datetime('now'),
               title = CASE WHEN title = '新对话' THEN ? ELSE title END
           WHERE id = ?""",
        (title_text, conversation_id),
    )
    await db.commit()
    return msg_id


async def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and all its messages."""
    db = await get_db()
    await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    result = await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    await db.commit()
    return result.rowcount > 0
