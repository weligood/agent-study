"""
大模型客户端：进程内复用 ChatOpenAI、缓存 Tool-Calling Agent Runnable、缓存结构化抽取链。

减少每次请求重复构造客户端与 `create_tool_calling_agent` 的开销；配置变更请调用 `clear_llm_caches()`（已由 `clear_settings_cache` 触发）。
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_classic.agents import create_tool_calling_agent
from langchain_openai import ChatOpenAI

from config import Settings
from tv_agent.agent.prompt import build_agent_prompt
from tv_agent.tools import get_tv_legal_tools

logger = logging.getLogger(__name__)

_llm_by_key: dict[tuple[Any, ...], ChatOpenAI] = {}
_agent_bundle_by_key: dict[tuple[Any, ...], tuple[Any, list[Any]]] = {}
_structured_extractor_by_key: dict[tuple[Any, ...], Any] = {}


def _llm_cache_key(cfg: Settings, *, role: Literal["agent", "extractor"]) -> tuple[Any, ...]:
    model = cfg.model_name if role == "agent" else (cfg.extractor_model_name or cfg.model_name)
    return (
        role,
        model,
        cfg.openai_base_url or "",
        float(cfg.request_timeout_seconds),
        cfg.openai_api_key or "",
        int(cfg.openai_max_retries),
        bool(cfg.agent_parallel_tool_calls),
    )


def get_chat_llm(cfg: Settings, *, role: Literal["agent", "extractor"] = "agent") -> ChatOpenAI:
    """
    获取（并缓存）ChatOpenAI 实例。

    - **agent**：可启用 `parallel_tool_calls` 以并行执行多个工具（视网关支持而定）。
    - **extractor**：用于结构化抽取，不注入 tool 相关 model_kwargs。
    """
    key = _llm_cache_key(cfg, role=role)
    hit = _llm_by_key.get(key)
    if hit is not None:
        return hit

    model = cfg.model_name if role == "agent" else (cfg.extractor_model_name or cfg.model_name)
    model_kwargs: dict[str, Any] = {}
    if role == "agent" and cfg.agent_parallel_tool_calls:
        model_kwargs["parallel_tool_calls"] = True

    llm = ChatOpenAI(
        model=model,
        temperature=0,
        max_retries=cfg.openai_max_retries,
        timeout=cfg.request_timeout_seconds,
        api_key=cfg.openai_api_key,
        base_url=cfg.openai_base_url,
        model_kwargs=model_kwargs,
    )
    _llm_by_key[key] = llm
    return llm


def get_tool_calling_agent_bundle(cfg: Settings) -> tuple[Any, list[Any]]:
    """
    缓存 `create_tool_calling_agent` 与本次绑定的 tools 列表。

    AgentExecutor 必须与 agent 使用同一组 tool 对象引用，故与 runnable 一并缓存返回。
    """
    key = _llm_cache_key(cfg, role="agent")
    hit = _agent_bundle_by_key.get(key)
    if hit is not None:
        return hit

    llm = get_chat_llm(cfg, role="agent")
    tools = get_tv_legal_tools()
    prompt = build_agent_prompt()
    agent_runnable = create_tool_calling_agent(llm, tools, prompt)
    bundle = (agent_runnable, tools)
    _agent_bundle_by_key[key] = bundle
    logger.debug("已缓存 tool-calling agent runnable: model=%s", cfg.model_name)
    return bundle


def get_structured_extractor_runnable(cfg: Settings, schema: type[Any]) -> Any:
    """按「抽取模型 + 连接 + schema」缓存 `with_structured_output` Runnable。"""
    model = cfg.extractor_model_name or cfg.model_name
    key = (
        model,
        cfg.openai_base_url or "",
        float(cfg.request_timeout_seconds),
        cfg.openai_api_key or "",
        int(cfg.openai_max_retries),
        getattr(schema, "__name__", str(schema)),
    )
    hit = _structured_extractor_by_key.get(key)
    if hit is not None:
        return hit

    llm = get_chat_llm(cfg, role="extractor")
    r = llm.with_structured_output(schema)
    _structured_extractor_by_key[key] = r
    return r


def clear_llm_caches() -> None:
    """清空进程内 LLM / Agent / 抽取链缓存。"""
    _llm_by_key.clear()
    _agent_bundle_by_key.clear()
    _structured_extractor_by_key.clear()
