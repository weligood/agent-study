"""SSE 行格式与事件名常量（与 `TraceEvent` 负载模型解耦）。"""

from __future__ import annotations

import json
from typing import Any

SSE_NAMES = (
    "trace.start",
    "trace.step",
    "trace.tool_call",
    "trace.tool_result",
    "trace.human_needed",
    "trace.warning",
    "result.partial",
    "result.final",
    "error",
)


def sse_packet(event_name: str, data: dict[str, Any]) -> str:
    """生成一条 SSE：`event: <name>` + `data: <json>`。"""
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
