"""超时、重试、日志等运行期参数视图。"""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings, get_settings


@dataclass(frozen=True)
class RuntimeConfigView:
    request_timeout_seconds: float
    graph_node_max_retries: int
    session_ttl_minutes: int
    log_level: str

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> RuntimeConfigView:
        s = settings or get_settings()
        return cls(
            request_timeout_seconds=float(s.request_timeout_seconds),
            graph_node_max_retries=int(s.graph_node_max_retries),
            session_ttl_minutes=int(s.session_ttl_minutes),
            log_level=str(s.log_level),
        )
