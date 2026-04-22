"""
用户偏好与约束过滤（偏好层）：在资源层结果之上裁剪 offers / 相似推荐。

与 LangGraph 骨架、Agent 推理层解耦；API 通过 `TvQueryRequest.preferences` 传入。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tv_agent.availability import sort_streaming_offers
from tv_agent.domain.schemas import CandidateTitle, StreamingOffer, TVAvailabilityResult


class UserQueryPreferences(BaseModel):
    """查询级偏好：仅影响本次响应的展示与排序，不改变底层检索逻辑。"""

    model_config = {"extra": "ignore"}

    allowed_access_types: list[str] | None = Field(
        default=None,
        description="若设置，仅保留这些 access_type（subscription/rent/buy/free/unknown）",
    )
    excluded_access_types: list[str] = Field(
        default_factory=list,
        description="排除的访问类型，如 rent",
    )
    excluded_providers: list[str] = Field(
        default_factory=list,
        description="排除的平台名（子串不区分大小写匹配 provider）",
    )
    min_offer_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="offer.confidence 下限",
    )
    official_only: bool = Field(
        default=False,
        description="为 true 时仅保留 official=true 的 offer",
    )
    excluded_keywords_in_similar: list[str] = Field(
        default_factory=list,
        description="相似剧标题若包含任一子串（忽略大小写）则剔除",
    )


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _offer_passes(o: StreamingOffer, prefs: UserQueryPreferences) -> bool:
    if o.confidence < prefs.min_offer_confidence:
        return False
    if prefs.official_only and not o.official:
        return False
    at = o.access_type
    if at in prefs.excluded_access_types:
        return False
    if prefs.allowed_access_types is not None and at not in prefs.allowed_access_types:
        return False
    pn = _norm(o.provider)
    for ex in prefs.excluded_providers:
        if ex and _norm(ex) in pn:
            return False
    return True


def _similar_passes(c: CandidateTitle, prefs: UserQueryPreferences) -> bool:
    title = _norm(c.standard_title)
    for kw in prefs.excluded_keywords_in_similar:
        if kw and _norm(kw) in title:
            return False
    return True


def apply_preferences(
    result: TVAvailabilityResult,
    prefs: UserQueryPreferences | None,
) -> TVAvailabilityResult:
    """返回应用偏好后的新结果（不修改入参）。"""
    if prefs is None:
        return result
    offers = [o for o in result.streaming_offers if _offer_passes(o, prefs)]
    offers = sort_streaming_offers(offers, confidence_desc=True)
    similar = [c for c in result.similar_titles if _similar_passes(c, prefs)]
    candidates = [c for c in result.candidate_titles if _similar_passes(c, prefs)]
    return result.model_copy(
        update={
            "streaming_offers": offers,
            "similar_titles": similar,
            "candidate_titles": candidates,
        },
    )


__all__ = ["UserQueryPreferences", "apply_preferences"]
