"""结构化抽取与解析链组合（JSON 失败时的 LLM 兜底）。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import Settings
from tv_agent.domain.schemas import TVAvailabilityResult
from tv_agent.llm_client import get_structured_extractor_runnable

from .parsing import parse_agent_output_to_result, _try_parse_agent_output

logger = logging.getLogger(__name__)

_STRUCTURE_EXTRACTOR_SYSTEM = """你是结构化抽取器。根据「用户请求」与「Agent 最终回答」生成 TVAvailabilityResult。

硬性规则：
- 不得编造 Agent 或工具结果中未出现的平台名、URL、剧集名；不确定的字段用 null，列表用 []。
- 必须如实反映 Agent 是否表示「未找到」「需消歧」等语义，映射到 result_status。
- disclaimer 须说明信息可能变更、仅供参考，且不提供任何非官方获取途径。
"""


def _extract_result_via_structured_llm(
    cfg: Settings,
    *,
    agent_input: str,
    agent_output: str,
    fallback_query: str,
) -> TVAvailabilityResult:
    """在 JSON 解析失败时，使用 API 原生结构化输出填充 TVAvailabilityResult。"""
    structured = get_structured_extractor_runnable(cfg, TVAvailabilityResult)
    human = (
        f"canonical_query（query_title 必须与此一致）: {fallback_query}\n\n"
        f"用户请求:\n{agent_input}\n\n"
        f"Agent 最终回答:\n{agent_output}"
    )
    out = structured.invoke(
        [
            SystemMessage(content=_STRUCTURE_EXTRACTOR_SYSTEM),
            HumanMessage(content=human),
        ]
    )
    if not isinstance(out, TVAvailabilityResult):
        raise TypeError(f"structured output 类型异常: {type(out)}")
    return out.model_copy(update={"query_title": fallback_query.strip() or out.query_title})


def _agent_text_to_result(
    cfg: Settings,
    *,
    agent_input: str,
    agent_output: str,
    fallback_query: str,
) -> TVAvailabilityResult:
    """优先快速 JSON 解析；失败则调用结构化抽取，再失败则返回原有降级结果。"""
    direct = _try_parse_agent_output(agent_output)
    if direct is not None:
        return direct.model_copy(
            update={"query_title": fallback_query.strip() or direct.query_title},
        )
    try:
        return _extract_result_via_structured_llm(
            cfg,
            agent_input=agent_input,
            agent_output=agent_output,
            fallback_query=fallback_query,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("结构化抽取失败，回退到降级结果: %s", e)
        return parse_agent_output_to_result(agent_output, fallback_query=fallback_query)


__all__ = ["_agent_text_to_result"]
