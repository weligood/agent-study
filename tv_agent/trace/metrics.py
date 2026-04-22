"""
请求级指标与错误分类（轻量占位，可对接 Prometheus / OpenTelemetry）。

与 `events.TraceEvent` 互补：事件偏「日志流」，本模块偏「可聚合观测」。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorTaxonomy(StrEnum):
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    AMBIGUITY = "ambiguity"
    TOOL_FAILURE = "tool_failure"
    POLICY_BLOCK = "policy_block"
    UNKNOWN = "unknown"


class RequestMetrics(BaseModel):
    """单次请求可挂载到 trace 扩展字段或日志上下文的指标摘要。"""

    model_config = {"extra": "ignore"}

    total_ms: float | None = None
    graph_nodes_ms: float | None = None
    tools_ms: float | None = None
    llm_ms: float | None = None
    intent: str | None = None
    execution_mode: str | None = None
    success: bool | None = None
    error_class: ErrorTaxonomy | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
