"""Agent runner: LLM agent that iteratively calls tools to answer complex queries.

Supports OpenAI function-calling format. The agent loop:
1. Send message + tool definitions to LLM
2. If LLM returns tool calls → execute them, append results
3. Repeat until LLM returns a final text answer or max iterations reached
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings, get_user_config
from app.chat.agent_tools import TOOL_SCHEMAS, execute_tool
from app.services.llm_service import _get_client, _auth_headers

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8

AGENT_SYSTEM_PROMPT = """你是"第二大脑"智能助手（Agent 模式）。你可以调用多种工具来帮助用户管理、搜索、分析个人知识库。

你的能力:
- search_knowledge: 在知识库中语义搜索
- get_entity_detail: 查看实体详情
- list_entities: 列出实体
- query_graph: 查询知识图谱关系
- list_tags: 查看标签体系
- create_entity: 创建新笔记
- update_entity_tags: 为实体打标签
- summarize_content: 生成内容摘要
- get_statistics: 查看知识库统计

使用规则:
1. 先分析用户意图，决定需要调用哪些工具
2. 可以连续调用多个工具来完成复杂任务
3. 基于工具返回的真实数据回答，不要编造
4. 创建或修改数据前，先确认用户意图
5. 用中文回答，简洁清晰"""


async def run_agent(
    query: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run the agent loop. Returns final answer + tool call log."""

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
    ]

    if history:
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    tool_log: list[dict[str, Any]] = []
    final_answer = ""

    settings = get_settings()
    client = await _get_client()
    url = f"{settings.llm_api_url.rstrip('/')}/chat/completions"

    for iteration in range(MAX_ITERATIONS):
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 4096,
        }

        try:
            resp = await client.post(url, json=payload, headers=_auth_headers(), timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Agent LLM call failed at iteration %d: %s", iteration, e)
            final_answer = f"Agent 调用 LLM 失败: {e}"
            break

        choice = data["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "")

        if msg.get("tool_calls"):
            messages.append(msg)

            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info("Agent tool call [%d]: %s(%s)", iteration, fn_name, fn_args)
                result_str = await execute_tool(fn_name, fn_args)

                tool_log.append({
                    "iteration": iteration,
                    "tool": fn_name,
                    "arguments": fn_args,
                    "result_preview": result_str[:500],
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

            continue

        final_answer = msg.get("content", "")
        break
    else:
        final_answer = final_answer or "Agent 达到最大迭代次数，请尝试简化问题。"

    return {
        "answer": final_answer,
        "tool_calls": tool_log,
        "iterations": len(tool_log),
    }
