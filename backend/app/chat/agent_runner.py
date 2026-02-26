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

AGENT_SYSTEM_PROMPT = """你是"第二大脑"智能助手（Agent 模式）。你可以管理知识库，并与用户 Mac 上的 Apple 备忘录、提醒事项、日历实时交互。

## 当前时间（必读）
- 用户说「今天」「明天」「下午」「本周」等相对时间时，**必须先调用 get_current_datetime** 获取当前日期时间，再根据返回的 date_only / iso_local 计算 start_date、end_date、due_date。
- **严禁**猜测日期或使用 2023、2024 等过往年份。未调用 get_current_datetime 就创建日历/待办会导致创建失败或错误日期。

## 与 Apple 三件套的交互
- **读取/总结**：fetch_apple_data 从系统实时拉取。查「明天待办」「某日日历」时：先 get_current_datetime，再用 due_after/due_before（待办）或 days_back/days_forward（日历）传日期范围；再可用 summarize_content 总结。
- **写入**：create_apple_note / create_apple_reminder / create_apple_event 会真正在系统 App 里创建。
- 创建日历：start_date、end_date 格式必须为 ISO，如 2026-02-19T15:00:00（今天下午3点 = date_only + 'T15:00:00'，明天同一时间 = 明天的 date_only + 'T15:00:00'）。
- **若工具返回 error 或 success 为 false**：必须如实告诉用户「创建失败」，并转述错误信息，不要谎称已成功。

## 知识库检索（重要）
- **当用户问知识相关问题时，优先使用 search_knowledge 进行语义检索**，它会同时使用向量搜索和关键词匹配。
- search_knowledge 支持 folder_tag（文件夹标签过滤，如 '领域/技术'）和 content_tag（内容标签过滤，如 '学习'、'研究'）参数，可缩小搜索范围提高精准度。
- 如果用户提到了具体分类或标签，可先用 list_tags 查看标签体系，再带上 folder_tag / content_tag 参数搜索。
- 其他知识库工具: list_entities, get_entity_detail, query_graph, list_tags, update_entity_tags, create_entity, summarize_content, get_statistics

使用规则:
1. 相对时间 → 先 get_current_datetime，再算具体日期时间
2. 基于工具返回的真实数据回答；有 error 必须向用户说明失败原因
3. 用中文回答，简洁清晰"""


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
