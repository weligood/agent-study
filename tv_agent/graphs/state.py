"""
LangGraph 工作流状态（与 `tv_agent.domain.schemas` 中的领域结果模型分离）。

领域模型描述「对外的业务结果」；本模块描述「运行时的图状态」：中间 dict、重试轨迹、
消歧上下文、节点 trace、错误累积等，便于 durable execution / checkpoint / human-in-the-loop。
"""

from __future__ import annotations

from typing import Any, TypedDict


class TVAvailabilityGraphState(TypedDict, total=False):
    """剧名正版可查子图状态（各节点增量 merge）。"""

    query_title: str
    disambiguation_hint: str | None
    metadata: dict[str, Any]
    platforms: dict[str, Any]
    similar: dict[str, Any]
    node_trace: list[str]
    graph_errors: list[str]
    final_result: dict[str, Any]


class ActorSearchState(TypedDict, total=False):
    """演员作品检索链状态（当前 pipeline 为单步，预留扩展多节点图）。"""

    actor_query: str
    disambiguation_hint: str | None
    raw_search_envelope: dict[str, Any]
    node_trace: list[str]


class VideoExtractGraphState(TypedDict, total=False):
    """视频页提取子图状态；`result` 运行时为 VideoInfo，此处不绑定具体类型以免循环依赖。"""

    url: str
    platform_route: str
    node_trace: list[str]
    error: str | None
    result: Any
