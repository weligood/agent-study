"""
标题规范化与消歧（地基层）。

与 LangGraph / Agent 解耦：图与工具通过 `resolve_title_for_query` 消费 matches。
"""

from tv_agent.resolution.title_resolver import (
    TitleResolution,
    resolve_title_for_query,
    scrub_title,
)

__all__ = ["TitleResolution", "resolve_title_for_query", "scrub_title"]
