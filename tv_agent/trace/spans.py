"""Trace 关联：request_id / trace_id / session_id 贯穿（供日志与 SSE 共用）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraceCorrelation:
    """一次用户可见「运行」的关联键。"""

    trace_id: str
    run_id: str
    request_id: str | None = None
    session_id: str | None = None
