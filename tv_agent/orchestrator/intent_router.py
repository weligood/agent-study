"""根据 API query_type 与文本形态识别高层意图。"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from tv_agent.policy.source_policy import video_url_requires_agent


class QueryIntent(StrEnum):
    """用户请求意图（粗粒度，供路由与观测分桶）。"""

    TITLE_AVAILABILITY = "title_availability"
    ACTOR_WORKS = "actor_works"
    VIDEO_PAGE = "video_page"
    RECOMMENDATION = "recommendation"
    DOWNLOAD = "download"
    GENERAL = "general"


def route_query_intent(
    query_type: Literal["title", "actor"],
    text: str,
) -> QueryIntent:
    """
    识别意图。

    - 演员入口固定为 ACTOR_WORKS。
    - HTTP(S) 输入视为视频页/解析类请求（走 Agent 工具链）。
    - 简单启发式：含「推荐」「相似」等词时标记 RECOMMENDATION（仍可能由 pipeline 满足）。
    """
    if query_type == "actor":
        return QueryIntent.ACTOR_WORKS
    t = text.strip()
    if video_url_requires_agent(t):
        return QueryIntent.VIDEO_PAGE
    low = t.lower()
    if any(k in low for k in ("推荐", "相似", "像", "recommend", "similar")):
        return QueryIntent.RECOMMENDATION
    return QueryIntent.TITLE_AVAILABILITY
