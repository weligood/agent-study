"""AgentExecutor 构建与剧名/演员查询入口。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_classic.agents import AgentExecutor
from langchain_core.callbacks import BaseCallbackHandler

from config import Settings, get_settings
from tv_agent.domain.schemas import ResultStatus, TVAvailabilityResult
from tv_agent.llm_client import get_tool_calling_agent_bundle

from .extraction import _agent_text_to_result

logger = logging.getLogger(__name__)


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

    agent_runnable, tools = get_tool_calling_agent_bundle(cfg)
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
    cfg = settings or get_settings()
    return _agent_text_to_result(
        cfg,
        agent_input=agent_input,
        agent_output=output,
        fallback_query=fallback_query,
    )


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


__all__ = [
    "build_executor",
    "run_availability_query",
    "run_actor_search_query",
]
