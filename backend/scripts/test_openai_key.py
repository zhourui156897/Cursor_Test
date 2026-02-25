#!/usr/bin/env python3
"""测试 OpenAI API Key 是否有效，并列出可用的 Chat / Embedding 模型。
使用方式（key 不要提交到 Git）:
  export OPENAI_API_KEY="sk-proj-xxx..."
  cd backend && source .venv/bin/activate && python scripts/test_openai_key.py
"""
from __future__ import annotations

import os
import sys

try:
    import httpx
except ImportError:
    print("请先安装: pip install httpx")
    sys.exit(1)

BASE = "https://api.openai.com/v1"
KEY = os.environ.get("OPENAI_API_KEY", "").strip()
if not KEY:
    print("请设置环境变量: export OPENAI_API_KEY='sk-proj-...'")
    sys.exit(1)


def main() -> None:
    headers = {"Authorization": f"Bearer {KEY}"}
    timeout = 30.0

    # 1. 列出模型
    print("正在请求 /models ...")
    try:
        r = httpx.get(f"{BASE}/models", headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        print(f"列出模型失败 HTTP {e.response.status_code}: {e.response.text[:300]}")
        return
    except Exception as e:
        print(f"请求失败: {e}")
        return

    models = [m["id"] for m in data.get("data", [])]
    chat = sorted({x for x in models if "gpt" in x.lower() and ("turbo" in x or "gpt-4" in x or "gpt-3.5" in x)})
    embed = sorted({x for x in models if "embedding" in x.lower()})
    print("--- 可用模型（与本项目相关）---")
    print("Chat 类:", chat[:25] if len(chat) > 25 else chat)
    print("Embedding 类:", embed[:15] if len(embed) > 15 else embed)

    # 2. 测试 Chat（优先 gpt-4o，否则 gpt-3.5-turbo）
    for model in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]:
        if any(m == model or m.startswith(model + "-") for m in models):
            break
    else:
        model = "gpt-3.5-turbo"
    print(f"\n正在测试 Chat 模型: {model} ...")
    try:
        r = httpx.post(
            f"{BASE}/chat/completions",
            headers={**headers, "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "回复ok"}], "max_tokens": 10},
            timeout=timeout,
        )
        r.raise_for_status()
        out = r.json()
        content = (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
        print(f"  Chat 测试成功，回复: {content.strip()!r}")
    except httpx.HTTPStatusError as e:
        print(f"  Chat 测试失败 HTTP {e.response.status_code}: {e.response.text[:200]}")

    # 3. 测试 Embedding（本项目用 text-embedding-3-small）
    emb_model = "text-embedding-3-small"
    if emb_model not in models and embed:
        emb_model = embed[0]
    print(f"\n正在测试 Embedding 模型: {emb_model} ...")
    try:
        r = httpx.post(
            f"{BASE}/embeddings",
            headers={**headers, "Content-Type": "application/json"},
            json={"model": emb_model, "input": "测试"},
            timeout=timeout,
        )
        r.raise_for_status()
        out = r.json()
        vec = (out.get("data") or [{}])[0].get("embedding", [])
        print(f"  Embedding 测试成功，维度: {len(vec)}")
        if emb_model == "text-embedding-3-small" and len(vec) != 1536:
            print("  注意: text-embedding-3-small 通常为 1536 维，本项目默认 embedding_dim=1536")
    except httpx.HTTPStatusError as e:
        print(f"  Embedding 测试失败 HTTP {e.response.status_code}: {e.response.text[:200]}")

    print("\n第二大脑项目推荐配置（在 user_config.yaml / 设置页）:")
    print("  model: gpt-4o")
    print("  embedding_model: text-embedding-3-small")
    print("  embedding_dim: 1536")


if __name__ == "__main__":
    main()
