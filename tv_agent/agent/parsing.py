"""Agent 最终文本 → JSON → `TVAvailabilityResult` 的解析。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from tv_agent.domain.schemas import ResultStatus, TVAvailabilityResult

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


def _try_parse_agent_output(agent_output: str) -> TVAvailabilityResult | None:
    """若能从输出中解析出合法 JSON，则返回模型实例；否则返回 None。"""
    try:
        data = _extract_json_object(agent_output)
        return TVAvailabilityResult.model_validate(data)
    except Exception:
        return None


__all__ = ["parse_agent_output_to_result", "_try_parse_agent_output", "_extract_json_object"]
