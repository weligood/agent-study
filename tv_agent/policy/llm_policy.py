"""与 LLM 调用相关的上限与开关（从 Settings 读取，便于单测替换）。"""

from __future__ import annotations

from config import Settings, get_settings


def agent_iterations_cap(settings: Settings | None = None) -> int:
    return int((settings or get_settings()).agent_max_iterations)
