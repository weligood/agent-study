"""
LangChain Tool Calling Agent：提示词、解析、结构化兜底与执行入口。

子模块：
- `prompt` — System / Chat 模板
- `parsing` — 模型输出 JSON 解析
- `extraction` — 结构化 LLM 兜底
- `runner` — AgentExecutor 与 `run_*_query`
"""

from __future__ import annotations

from .extraction import _agent_text_to_result
from .parsing import _try_parse_agent_output, parse_agent_output_to_result
from .prompt import SYSTEM_PROMPT, build_agent_prompt
from .runner import build_executor, run_availability_query, run_actor_search_query

__all__ = [
    "SYSTEM_PROMPT",
    "_agent_text_to_result",
    "_try_parse_agent_output",
    "build_agent_prompt",
    "build_executor",
    "parse_agent_output_to_result",
    "run_actor_search_query",
    "run_availability_query",
]
