"""模型与 Agent 行为相关视图。"""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings, get_settings


@dataclass(frozen=True)
class LLMConfigView:
    model_name: str
    extractor_model_name: str
    openai_max_retries: int
    agent_max_iterations: int
    agent_parallel_tool_calls: bool

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> LLMConfigView:
        s = settings or get_settings()
        return cls(
            model_name=s.model_name,
            extractor_model_name=s.extractor_model_name or s.model_name,
            openai_max_retries=int(s.openai_max_retries),
            agent_max_iterations=int(s.agent_max_iterations),
            agent_parallel_tool_calls=bool(s.agent_parallel_tool_calls),
        )
