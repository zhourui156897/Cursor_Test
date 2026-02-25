"""Chat API: multi-turn Q&A with RAG + Agent mode, SSE streaming support."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.chat.conversation import (
    create_conversation,
    list_conversations,
    get_conversation_messages,
    add_message,
    delete_conversation,
)
from app.chat.rag_pipeline import run_rag
from app.chat.agent_runner import run_agent
from app.services.llm_service import check_available

logger = logging.getLogger(__name__)


def _raise_if_readonly(e: Exception) -> None:
    """若为数据库只读错误，则抛出 503 并提示修复方式（最佳实践：不降级，明确报错）."""
    msg = str(e).lower()
    if "readonly" in msg and "database" in msg:
        path = str(get_settings().resolved_data_dir)
        raise HTTPException(
            503,
            detail=f"数据目录不可写，无法保存对话。请执行后重启后端: chmod -R u+rwx {path}",
        ) from e


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    stream: bool = False
    mode: str = "rag"  # "rag" or "agent"


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: list[dict] = []
    tool_calls: list[dict] = []


class ConversationCreate(BaseModel):
    title: str = ""


@router.post("/send", response_model=ChatResponse)
async def send_message(req: ChatRequest):
    """Send a message and get a RAG or Agent-powered response."""
    try:
        conv_id = req.conversation_id
        if not conv_id:
            conv_id = await create_conversation(title=req.message[:30])
        await add_message(conv_id, "user", req.message)
    except Exception as e:
        _raise_if_readonly(e)
        raise

    history = await get_conversation_messages(conv_id, limit=20)
    history_dicts = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]

    if req.mode == "agent":
        try:
            result = await run_agent(req.message, history=history_dicts if history_dicts else None)
        except Exception as e:
            _raise_if_readonly(e)
            raise HTTPException(500, detail=f"Agent 执行失败: {e!s}")
        try:
            await add_message(conv_id, "assistant", result["answer"], sources=[])
        except Exception as e:
            _raise_if_readonly(e)
            raise
        return ChatResponse(
            conversation_id=conv_id,
            answer=result["answer"],
            sources=[],
            tool_calls=result.get("tool_calls", []),
        )

    try:
        ctx = await run_rag(req.message, history=history_dicts if history_dicts else None)
    except Exception as e:
        _raise_if_readonly(e)
        raise HTTPException(500, detail=f"RAG 执行失败: {e!s}")
    try:
        await add_message(conv_id, "assistant", ctx.answer, sources=ctx.sources)
    except Exception as e:
        _raise_if_readonly(e)
        raise
    return ChatResponse(
        conversation_id=conv_id,
        answer=ctx.answer,
        sources=ctx.sources,
    )


@router.post("/send/stream")
async def send_message_stream(req: ChatRequest):
    """Send a message and stream the response via SSE."""
    try:
        conv_id = req.conversation_id
        if not conv_id:
            conv_id = await create_conversation(title=req.message[:30])
        await add_message(conv_id, "user", req.message)
    except Exception as e:
        _raise_if_readonly(e)
        raise

    history = await get_conversation_messages(conv_id, limit=20)
    history_dicts = [{"role": m["role"], "content": m["content"]} for m in history[:-1]]

    async def event_stream():
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conv_id})}\n\n"

        if req.mode == "agent":
            result = await run_agent(req.message, history=history_dicts if history_dicts else None)
            for tc in result.get("tool_calls", []):
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tc['tool'], 'args': tc['arguments']}, ensure_ascii=False)}\n\n"
            chunks = _split_into_chunks(result["answer"], 20)
            for chunk in chunks:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
            try:
                await add_message(conv_id, "assistant", result["answer"])
            except Exception as e:
                _raise_if_readonly(e)
                raise
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        else:
            ctx = await run_rag(req.message, history=history_dicts if history_dicts else None)
            chunks = _split_into_chunks(ctx.answer, 20)
            for chunk in chunks:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
            try:
                await add_message(conv_id, "assistant", ctx.answer, sources=ctx.sources)
            except Exception as e:
                _raise_if_readonly(e)
                raise
            yield f"data: {json.dumps({'type': 'sources', 'sources': ctx.sources}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations")
async def list_all_conversations(limit: int = 50):
    """List all conversations."""
    return await list_conversations(limit=limit)


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    """Get all messages in a conversation."""
    return await get_conversation_messages(conversation_id)


@router.post("/conversations")
async def create_new_conversation(req: ConversationCreate):
    """Create a new empty conversation."""
    conv_id = await create_conversation(title=req.title)
    return {"id": conv_id}


@router.delete("/conversations/{conversation_id}")
async def delete_conv(conversation_id: str):
    """Delete a conversation."""
    ok = await delete_conversation(conversation_id)
    if not ok:
        raise HTTPException(404, "对话不存在")
    return {"deleted": True}


def _split_into_chunks(text: str, size: int) -> list[str]:
    """Split text into chunks for simulated streaming."""
    return [text[i:i+size] for i in range(0, len(text), size)] if text else [""]
