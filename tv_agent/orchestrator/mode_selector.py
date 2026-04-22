"""决定确定性图、带消歧的图路径、Agent 或人机确认门。"""

from __future__ import annotations

from enum import StrEnum

from config import Settings, get_settings

from tv_agent.orchestrator.intent_router import QueryIntent
from tv_agent.policy.source_policy import video_url_requires_agent


class ExecutionMode(StrEnum):
    """执行形态（用于 trace / metrics 分桶）。"""

    GRAPH_PIPELINE = "graph_pipeline"
    """剧名：LangGraph；演员：同步检索（预留扩展为图）。"""

    AGENT_TOOL_CALLING = "agent_tool_calling"
    """LangChain Agent + 注册工具。"""

    HUMAN_CONFIRM_GATE = "human_confirm_gate"
    """下载等高风险动作：prepare → 用户 confirm（策略层配合）。"""


def select_execution_mode(
    intent: QueryIntent,
    user_text: str,
    *,
    settings: Settings | None = None,
) -> ExecutionMode:
    cfg = settings or get_settings()
    if cfg.tv_query_mode == "agent" or video_url_requires_agent(user_text):
        return ExecutionMode.AGENT_TOOL_CALLING
    if intent in (QueryIntent.TITLE_AVAILABILITY, QueryIntent.ACTOR_WORKS, QueryIntent.RECOMMENDATION):
        return ExecutionMode.GRAPH_PIPELINE
    return ExecutionMode.AGENT_TOOL_CALLING
