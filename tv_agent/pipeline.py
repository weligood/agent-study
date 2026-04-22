"""
确定性检索：剧名走 LangGraph 子图；演员走单步搜索。

架构（自底向上）：
- **资源层**：`tv_agent.resources`、`tv_agent.tools.internal`、`tv_agent.search`、`video_scraper`
- **规范化层**：`tv_agent.resolution`（标题清洗、消歧、canonical id）
- **编排骨架**：本模块 + `tv_agent.graphs`（LangGraph 为主路径）
- **推理插件**：`tv_agent.agent`（高复杂度 / 视频 URL / 多轮追问时在 `tv_query_mode=agent` 启用）
- **偏好层**：`tv_agent.preferences`（对结果的过滤与排序，不改变检索调用）
- **追踪层**：`tv_agent.trace`（含 `events` / `callbacks`，SSE / TraceEvent）
- **推荐助手层**：`tv_agent.recommendation`（相似与替代内容）

与 `tv_agent.agent`（Tool Agent）互为补充。视频 URL 判断见 `tv_agent.policy.source_policy`。
"""

from __future__ import annotations

import logging

from tv_agent.graphs.tv_availability import run_tv_availability_graph
from tv_agent.preferences import UserQueryPreferences, apply_preferences
from tv_agent.domain.schemas import (
    CandidateTitle,
    ResultStatus,
    TVAvailabilityResult,
)
from tv_agent.policy.source_policy import video_url_requires_agent
from tv_agent.tools import _search_by_actor_web

logger = logging.getLogger(__name__)

_DEFAULT_DISCLAIMER = (
    "信息来源于公开检索聚合，版权与片库随时间变化，仅供参考；不提供任何非官方获取方式。"
)


def run_availability_pipeline(
    user_input: str,
    *,
    disambiguation_hint: str | None = None,
    preferences: UserQueryPreferences | None = None,
) -> TVAvailabilityResult:
    """
    剧名查询：由 `tv_agent.graphs.tv_availability` LangGraph 编排（元数据 → 消歧/平台 → 相似）。
    """
    r = run_tv_availability_graph(
        user_input,
        disambiguation_hint=disambiguation_hint,
    )
    return apply_preferences(r, preferences)


def run_actor_pipeline(
    actor_name: str,
    *,
    disambiguation_hint: str | None = None,
    preferences: UserQueryPreferences | None = None,
) -> TVAvailabilityResult:
    """
    演员查询：返回候选作品列表；不调用大模型。`disambiguation_hint` 预留与 Agent 对齐。
    """
    _ = disambiguation_hint
    actor = actor_name.strip()
    if not actor:
        return apply_preferences(
            TVAvailabilityResult(
                query_title=actor_name,
                result_status=ResultStatus.NOT_FOUND,
                confidence="演员名为空",
                disclaimer=_DEFAULT_DISCLAIMER,
            ),
            preferences,
        )

    raw = _search_by_actor_web(actor)
    if not raw.get("ok"):
        return apply_preferences(
            TVAvailabilityResult(
                query_title=actor,
                result_status=ResultStatus.NOT_FOUND,
                confidence=raw.get("message"),
                disclaimer=_DEFAULT_DISCLAIMER,
            ),
            preferences,
        )

    related = list(raw.get("related_works") or [])
    candidates: list[CandidateTitle] = []
    for w in related:
        if not isinstance(w, dict):
            continue
        candidates.append(
            CandidateTitle(
                standard_title=str(w.get("standard_title", "")).strip(),
                release_year=w.get("release_year"),
                region=w.get("region"),
                brief_note=None,
                work_id=w.get("work_id"),
            )
        )

    if not candidates:
        return apply_preferences(
            TVAvailabilityResult(
                query_title=actor,
                result_status=ResultStatus.NOT_FOUND,
                confidence=raw.get("message") or "未找到该演员的电视剧作品列表",
                disclaimer=_DEFAULT_DISCLAIMER,
            ),
            preferences,
        )

    r = TVAvailabilityResult(
        query_title=actor,
        candidate_titles=candidates,
        result_status=ResultStatus.AMBIGUOUS,
        confidence=raw.get("message") or "请从列表中选择具体剧集后可查询正版平台信息。",
        disclaimer=_DEFAULT_DISCLAIMER,
    )
    return apply_preferences(r, preferences)


def query_looks_like_video_url(text: str) -> bool:
    """若用户输入为视频页 URL，应走 Agent（含 extract/download 工具）。"""
    return video_url_requires_agent(text)
