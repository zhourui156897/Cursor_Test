"""Unified LLM service layer: chat completion + embedding via OpenAI-compatible API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings, get_user_config

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None
_llm_available: bool | None = None


def _get_api_key() -> str:
    """Get API key from user_config (set via Settings UI), fallback to empty."""
    cfg = get_user_config()
    return cfg.get("llm", {}).get("api_key", "") if cfg else ""


def _auth_headers() -> dict[str, str]:
    key = _get_api_key()
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=10.0),
        )
    return _http_client


async def close_client():
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


async def check_available() -> bool:
    """Quick check if the LLM API is reachable."""
    global _llm_available
    settings = get_settings()
    client = await _get_client()
    try:
        resp = await client.get(
            f"{settings.llm_api_url.rstrip('/')}/models",
            headers=_auth_headers(),
            timeout=3.0,
        )
        _llm_available = resp.status_code == 200
    except Exception:
        _llm_available = False
    return _llm_available


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_format: dict | None = None,
) -> str:
    """Call LLM chat completion endpoint. Returns assistant message content."""
    settings = get_settings()
    client = await _get_client()
    url = f"{settings.llm_api_url.rstrip('/')}/chat/completions"

    payload: dict[str, Any] = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = await client.post(url, json=payload, headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error("LLM chat error: %s %s", e.response.status_code, e.response.text[:500])
        raise RuntimeError(f"LLM API error: {e.response.status_code}") from e
    except Exception as e:
        logger.error("LLM chat failed: %s", e)
        raise RuntimeError(f"LLM API unavailable: {e}") from e


async def get_embedding(text: str, *, model: str | None = None) -> list[float]:
    """Get embedding vector for a single text."""
    settings = get_settings()
    client = await _get_client()
    url = f"{settings.llm_api_url.rstrip('/')}/embeddings"

    try:
        resp = await client.post(url, json={
            "model": model or settings.embedding_model,
            "input": text,
        }, headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]
    except httpx.HTTPStatusError as e:
        logger.error("Embedding error: %s %s", e.response.status_code, e.response.text[:500])
        raise RuntimeError(f"Embedding API error: {e.response.status_code}") from e
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise RuntimeError(f"Embedding API unavailable: {e}") from e


async def get_embeddings_batch(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """Get embedding vectors for multiple texts in one call."""
    settings = get_settings()
    client = await _get_client()
    url = f"{settings.llm_api_url.rstrip('/')}/embeddings"

    try:
        resp = await client.post(url, json={
            "model": model or settings.embedding_model,
            "input": texts,
        }, headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    except Exception as e:
        logger.error("Batch embedding failed: %s", e)
        raise RuntimeError(f"Batch embedding failed: {e}") from e
