"""预留的特性开关视图（后续可映射到独立 env 而不膨胀 Settings）。"""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings, get_settings


@dataclass(frozen=True)
class FeatureFlagsView:
    use_agent_by_default: bool

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> FeatureFlagsView:
        s = settings or get_settings()
        return cls(use_agent_by_default=s.tv_query_mode == "agent")
