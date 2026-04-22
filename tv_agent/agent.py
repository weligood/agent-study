"""
LangChain Tool Calling Agent 装配：模型、工具、Prompt、Executor。

解析模型最终输出中的 JSON，并校验为 `TVAvailabilityResult`。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_openai import ChatOpenAI

from config import Settings, get_settings
from tv_agent.prompt import build_agent_prompt
from tv_agent.schemas import ResultStatus, TVAvailabilityResult
from tv_agent.tools import get_tv_legal_tools

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出中提取单个 JSON 对象；兼容 Markdown 围栏。"""
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    start = s.find("{")
    if start == -1:
        raise ValueError("输出中未找到 JSON 对象起始")
    decoder = json.JSONDecoder()
    obj, _end = decoder.raw_decode(s[start:])
    if not isinstance(obj, dict):
        raise ValueError("JSON 顶层必须是对象")
    return obj


def parse_agent_output_to_result(agent_output: str, fallback_query: str) -> TVAvailabilityResult:
    """将 Agent 最终文本解析为 `TVAvailabilityResult`；失败时返回降级结果。"""
    try:
        data = _extract_json_object(agent_output)
        return TVAvailabilityResult.model_validate(data)
    except Exception as e:  # noqa: BLE001
        logger.warning("解析 Agent JSON 失败，使用降级结果: %s", e)
        return TVAvailabilityResult(
            query_title=fallback_query,
            result_status=ResultStatus.PARTIAL,
            confidence="模型输出无法解析为结构化 JSON；请检查 prompt 遵循度或提高模型能力。",
            disclaimer=(
                "本结果为解析失败降级输出，不代表任何平台可用性；"
                "禁止用于盗版或绕过版权保护之目的。"
            ),
        )


def build_executor(
    settings: Settings | None = None,
    *,
    memory: Any | None = None,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> AgentExecutor:
    """创建绑定核心工具的 AgentExecutor（Tool Calling）。"""
    cfg = settings or get_settings()
    if not cfg.openai_api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY，无法初始化对话模型。")

    llm = ChatOpenAI(
        model=cfg.model_name,
        temperature=0,
        timeout=cfg.request_timeout_seconds,
        api_key=cfg.openai_api_key,
        base_url=cfg.openai_base_url,
    )
    tools = get_tv_legal_tools()
    prompt = build_agent_prompt()
    agent_runnable = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent_runnable,
        tools=tools,
        verbose=False,
        max_iterations=cfg.agent_max_iterations,
        handle_parsing_errors=True,
        return_intermediate_steps=False,
        memory=memory,
        callbacks=callbacks,
    )


def _run_query(
    agent_input: str,
    fallback_query: str,
    settings: Settings | None = None,
    *,
    memory: Any | None = None,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> TVAvailabilityResult:
    """通用查询执行：构建 Executor → invoke → 解析结果。"""
    executor = build_executor(settings, memory=memory, callbacks=callbacks)
    try:
        invoke_kwargs: dict[str, Any] = {"input": agent_input}
        if memory is None:
            invoke_kwargs["chat_history"] = []
        raw = executor.invoke(invoke_kwargs)
    except Exception as e:  # noqa: BLE001
        logger.exception("AgentExecutor 调用失败: %s", e)
        return TVAvailabilityResult(
            query_title=fallback_query,
            result_status=ResultStatus.NOT_FOUND,
            confidence=f"Agent 执行失败（已捕获）：{e!s}",
            disclaimer="因执行异常未形成有效检索结论；不提供任何非官方获取方式。",
        )

    output = raw.get("output", "")
    if not isinstance(output, str):
        output = str(output)
    return parse_agent_output_to_result(output, fallback_query=fallback_query)


def run_availability_query(
    user_input: str,
    settings: Settings | None = None,
    *,
    disambiguation_hint: str | None = None,
    memory: Any | None = None,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> TVAvailabilityResult:
    """
    执行一次完整查询：调用 Agent，再将输出解析为结构化结果。

    :param user_input: 剧名（或用户自然语言中的剧名主体）。
    :param disambiguation_hint: 可选，年份或 work_id 等，供 Web/API 显式消歧。
    :param memory: 可选的 LangChain Memory 实例。
    :param callbacks: 可选的回调处理器列表。
    """
    title = user_input.strip()
    if disambiguation_hint and disambiguation_hint.strip():
        agent_input = (
            "请查询以下电视剧的正版播放平台与元信息。\n"
            f"剧名：{title}\n"
            f"消歧提示（年份或 work_id）：{disambiguation_hint.strip()}"
        )
    else:
        agent_input = f"请查询以下电视剧的正版播放平台与元信息。\n剧名：{title}"
    return _run_query(agent_input, title, settings, memory=memory, callbacks=callbacks)


def run_actor_search_query(
    actor_name: str,
    settings: Settings | None = None,
    *,
    disambiguation_hint: str | None = None,
    memory: Any | None = None,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> TVAvailabilityResult:
    """
    按演员查询：返回该演员参演的电视剧列表。

    :param actor_name: 演员姓名。
    :param disambiguation_hint: 可选，年份或 work_id 等。
    :param memory: 可选的 LangChain Memory 实例。
    :param callbacks: 可选的回调处理器列表。
    """
    actor = actor_name.strip()
    if disambiguation_hint and disambiguation_hint.strip():
        agent_input = (
            "请查询以下演员参演的电视剧列表，并列出每部剧的基础信息。\n"
            f"演员：{actor}\n"
            f"消歧提示（年份或 work_id）：{disambiguation_hint.strip()}"
        )
    else:
        agent_input = f"请查询以下演员参演的电视剧列表，并列出每部剧的基础信息。\n演员：{actor}"
    return _run_query(agent_input, actor, settings, memory=memory, callbacks=callbacks)
