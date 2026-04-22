"""把意图与模式选择收敛为单一计划对象，供服务层与 SSE 复用。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from config import Settings, get_settings

from tv_agent.orchestrator.intent_router import QueryIntent, route_query_intent
from tv_agent.orchestrator.mode_selector import ExecutionMode, select_execution_mode


@dataclass(frozen=True)
class ExecutionPlan:
    """一次查询的可观测决策快照。"""

    intent: QueryIntent
    execution_mode: ExecutionMode
    use_agent: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    human_confirm_for_download: bool = True

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "execution_mode": self.execution_mode.value,
            "use_agent": self.use_agent,
            "reasons": list(self.reasons),
            "human_confirm_for_download": self.human_confirm_for_download,
        }


def build_execution_plan(
    query_type: Literal["title", "actor"],
    user_text: str,
    *,
    settings: Settings | None = None,
) -> ExecutionPlan:
    cfg = settings or get_settings()
    intent = route_query_intent(query_type, user_text)
    mode = select_execution_mode(intent, user_text, settings=cfg)
    use_agent = mode == ExecutionMode.AGENT_TOOL_CALLING

    reasons: list[str] = []
    if cfg.tv_query_mode == "agent":
        reasons.append("产品配置 tv_query_mode=agent：启用 LangChain 工具编排而非纯 LangGraph pipeline。")
    if intent == QueryIntent.VIDEO_PAGE:
        reasons.append("输入为 HTTP(S) URL：需视频页解析/下载类工具，不走纯剧名 LangGraph。")
    if not use_agent:
        if intent == QueryIntent.ACTOR_WORKS:
            reasons.append("演员入口：使用确定性演员作品检索（当前为单步联网聚合）。")
        elif intent == QueryIntent.TITLE_AVAILABILITY:
            reasons.append("剧名入口：使用 LangGraph 子图完成元数据→平台→相似的结构化检索。")
        elif intent == QueryIntent.RECOMMENDATION:
            reasons.append("推荐/相似类用语：仍走确定性图，由相似节点满足。")
    if not reasons:
        reasons.append("按意图与配置选择执行路径。")

    return ExecutionPlan(
        intent=intent,
        execution_mode=mode,
        use_agent=use_agent,
        reasons=tuple(reasons),
        human_confirm_for_download=True,
    )
