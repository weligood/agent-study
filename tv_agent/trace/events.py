"""
标准追踪事件负载（与 SSE 行格式解耦，见 `tv_agent.trace.sse`）。

事件名（与 data 负载配合，供前端订阅）：
trace.start / trace.step / trace.tool_call / trace.tool_result /
trace.human_needed / trace.warning / result.partial / result.final / error
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from tv_agent.trace.sse import SSE_NAMES, sse_packet

__all__ = ["SSE_NAMES", "TraceEvent", "sse_packet"]


class TraceEvent(BaseModel):
    """Pipeline、Agent、视频子图共用的追踪负载。"""

    model_config = {"extra": "ignore"}

    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase: str = Field(default="", description="如 metadata / platforms / agent_reasoning")
    event_type: str = Field(..., description="与 SSE 事件名对齐或子类型")
    source: Literal["pipeline_graph", "actor_pipeline", "agent", "video_graph", "system"] = "system"
    node: str | None = None
    tool: str | None = None
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
