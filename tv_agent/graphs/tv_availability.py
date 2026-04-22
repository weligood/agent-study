"""
剧名「正版可查」LangGraph：准备 → 元数据 →（消歧/继续）→ 平台 → 相似推荐 → 汇总。

每节点可单独观测 `node_trace` / `graph_errors`；搜索调用带有限次重试（可配置）。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from config import Settings, get_settings
from tv_agent.availability import platform_dicts_to_offers
from tv_agent.graphs.state import TVAvailabilityGraphState
from tv_agent.resolution.title_resolver import resolve_title_for_query, scrub_title
from tv_agent.domain.schemas import (
    AvailabilityStatus,
    CandidateTitle,
    PaymentType,
    PlatformInfo,
    ResultStatus,
    TVAvailabilityResult,
)
from tv_agent.recommendation.alternatives import (
    fetch_similar_envelope,
    similar_envelope_to_candidates,
)
from tv_agent.tools import _search_metadata, _search_platforms

logger = logging.getLogger(__name__)

_DEFAULT_DISCLAIMER = (
    "信息来源于公开检索聚合，版权与片库随时间变化，仅供参考；不提供任何非官方获取方式。"
)


def _trace(state: TVAvailabilityGraphState, step: str) -> list[str]:
    return list(state.get("node_trace", [])) + [step]


def _platform_dict_to_model(p: dict[str, Any]) -> PlatformInfo:
    raw_status = (p.get("availability_status") or "unknown").lower()
    try:
        status = AvailabilityStatus(raw_status)
    except ValueError:
        status = AvailabilityStatus.UNKNOWN
    raw_pay = (p.get("payment_type") or "unknown").lower()
    try:
        pay = PaymentType(raw_pay)
    except ValueError:
        pay = PaymentType.UNKNOWN
    return PlatformInfo(
        platform_name=str(p.get("platform_name", "")),
        availability_status=status,
        membership_required=p.get("membership_required"),
        payment_type=pay,
        offline_download_supported=p.get("offline_download_supported"),
        official_url=p.get("official_url"),
        logo_url=p.get("logo_url"),
        notes=p.get("notes"),
    )


def _match_to_candidate(m: dict[str, Any], score: float | None = None) -> CandidateTitle:
    return CandidateTitle(
        standard_title=str(m.get("standard_title", "")).strip(),
        release_year=m.get("release_year"),
        region=m.get("region"),
        brief_note=None,
        work_id=m.get("id"),
        score=score,
    )


def _retry_transient_ok(
    label: str,
    fn: Any,
    *,
    max_attempts: int,
    state: TVAvailabilityGraphState,
) -> tuple[Any, TVAvailabilityGraphState]:
    """对返回 dict 且含 ok 字段的搜索调用做有限重试（网络类失败）。"""
    attempts = max(1, max_attempts)
    last: dict[str, Any] | None = None
    errs = list(state.get("graph_errors", []))
    trace = list(state.get("node_trace", []))
    for i in range(attempts):
        try:
            last = fn()
        except Exception as e:  # noqa: BLE001
            msg = f"{label}#{i}:exception:{e!s}"
            logger.warning(msg)
            errs.append(msg)
            last = {"ok": False, "matches": [], "message": str(e)}
        trace.append(f"{label}:try={i + 1}/{attempts}")
        if isinstance(last, dict) and last.get("ok"):
            return last, {**state, "node_trace": trace, "graph_errors": errs}
        msg_l = str((last or {}).get("message") or "").lower()
        transient = any(
            x in msg_l for x in ("timeout", "超时", "timed out", "503", "502", "connection")
        )
        if i < attempts - 1 and transient:
            errs.append(f"{label}#{i}:transient_retry")
            continue
        break
    return last or {"ok": False, "matches": [], "message": "unknown"}, {
        **state,
        "node_trace": trace,
        "graph_errors": errs,
    }


def node_prepare(state: TVAvailabilityGraphState) -> dict[str, Any]:
    raw = (state.get("query_title") or "").strip()
    return {"query_title": raw, "node_trace": _trace(state, "prepare")}


def route_after_prepare(state: TVAvailabilityGraphState) -> Literal["empty", "metadata"]:
    if not (state.get("query_title") or "").strip():
        return "empty"
    return "metadata"


def node_sink_empty_title(state: TVAvailabilityGraphState) -> dict[str, Any]:
    r = TVAvailabilityResult(
        query_title=state.get("query_title") or "",
        result_status=ResultStatus.NOT_FOUND,
        confidence="剧名为空",
        disclaimer=_DEFAULT_DISCLAIMER,
    )
    return {"final_result": r.model_dump(mode="json"), "node_trace": _trace(state, "sink_empty_title")}


def node_fetch_metadata(state: TVAvailabilityGraphState) -> dict[str, Any]:
    cfg = get_settings()
    title = scrub_title(state["query_title"])
    hint = state.get("disambiguation_hint")

    def call() -> dict[str, Any]:
        return _search_metadata(title, hint)

    payload, st = _retry_transient_ok(
        "fetch_metadata",
        call,
        max_attempts=cfg.graph_node_max_retries,
        state=state,
    )
    return {**st, "metadata": payload}


def route_after_metadata(state: TVAvailabilityGraphState) -> Literal["ambiguous", "no_meta", "single"]:
    meta = state.get("metadata") or {}
    if not meta.get("ok"):
        return "no_meta"
    matches: list[dict[str, Any]] = list(meta.get("matches") or [])
    if not matches:
        return "no_meta"
    if len(matches) > 1 or meta.get("disambiguation_required") is True:
        return "ambiguous"
    return "single"


def node_sink_ambiguous(state: TVAvailabilityGraphState) -> dict[str, Any]:
    meta = state.get("metadata") or {}
    title = state["query_title"]
    hint = state.get("disambiguation_hint")
    matches = list(meta.get("matches") or [])
    tres = resolve_title_for_query(title, hint, matches)
    if tres.candidates:
        candidates = [
            CandidateTitle(
                standard_title=c.standard_title,
                release_year=c.release_year,
                region=c.region,
                brief_note=c.brief_note,
                work_id=c.work_id,
                score=c.score,
            )
            for c in tres.candidates
        ]
    else:
        candidates = [_match_to_candidate(m) for m in matches]
    r = TVAvailabilityResult(
        query_title=title,
        canonical_work_id=tres.canonical_work_id,
        candidate_titles=candidates,
        result_status=ResultStatus.AMBIGUOUS,
        confidence="存在多部候选或需要消歧，请选择具体作品后继续查询平台信息。",
        disclaimer=_DEFAULT_DISCLAIMER,
    )
    return {"final_result": r.model_dump(mode="json"), "node_trace": _trace(state, "sink_ambiguous")}


def node_sink_no_meta(state: TVAvailabilityGraphState) -> dict[str, Any]:
    meta = state.get("metadata") or {}
    title = state["query_title"]
    r = TVAvailabilityResult(
        query_title=title,
        result_status=ResultStatus.NOT_FOUND,
        confidence=meta.get("message") or "未匹配到剧集元数据",
        disclaimer=_DEFAULT_DISCLAIMER,
    )
    return {"final_result": r.model_dump(mode="json"), "node_trace": _trace(state, "sink_no_meta")}


def node_fetch_platforms(state: TVAvailabilityGraphState) -> dict[str, Any]:
    cfg = get_settings()
    meta = state.get("metadata") or {}
    m0 = (meta.get("matches") or [{}])[0]
    work_id = str(m0.get("id", ""))
    standard_title = str(m0.get("standard_title", state["query_title"])).strip()
    release_year = m0.get("release_year")

    def call() -> dict[str, Any]:
        return _search_platforms(work_id, standard_title, release_year)

    payload, st = _retry_transient_ok(
        "fetch_platforms",
        call,
        max_attempts=cfg.graph_node_max_retries,
        state=state,
    )
    return {**st, "platforms": payload}


def node_fetch_similar(state: TVAvailabilityGraphState) -> dict[str, Any]:
    cfg = get_settings()
    meta = state.get("metadata") or {}
    m0 = (meta.get("matches") or [{}])[0]
    work_id = str(m0.get("id", ""))
    standard_title = str(m0.get("standard_title", state["query_title"])).strip()

    def call() -> dict[str, Any]:
        return fetch_similar_envelope(work_id, standard_title)

    payload, st = _retry_transient_ok(
        "fetch_similar",
        call,
        max_attempts=cfg.graph_node_max_retries,
        state=state,
    )
    return {**st, "similar": payload}


def node_assemble_single(state: TVAvailabilityGraphState) -> dict[str, Any]:
    title = state["query_title"]
    meta = state.get("metadata") or {}
    plat = state.get("platforms") or {}
    sim = state.get("similar") or {}

    m0 = (meta.get("matches") or [{}])[0]
    standard_title = str(m0.get("standard_title", title)).strip()
    release_year = m0.get("release_year")
    region = m0.get("region")
    seasons = m0.get("seasons")
    episodes = m0.get("episodes")
    alt = list(m0.get("alternative_titles") or [])

    platforms: list[PlatformInfo] = []
    geo: str | None = None
    plat_ok = bool(plat.get("ok"))
    if plat_ok:
        for p in plat.get("platforms") or []:
            if isinstance(p, dict):
                platforms.append(_platform_dict_to_model(p))
        geo = plat.get("geo_restrictions")

    similar_titles: list[CandidateTitle] = (
        similar_envelope_to_candidates(sim) if sim.get("ok") else []
    )

    if not plat_ok:
        status = ResultStatus.PARTIAL
        confidence = plat.get("message") or "平台检索失败或未配置搜索 API"
    elif not platforms:
        status = ResultStatus.PARTIAL
        confidence = plat.get("message") or "未在检索结果中发现明确的正版平台条目"
    else:
        status = ResultStatus.SUCCESS
        confidence = "数据由 LangGraph 检索子图生成（联网搜索聚合），未使用大模型编排。"

    matches = list(meta.get("matches") or [])
    tres = resolve_title_for_query(title, state.get("disambiguation_hint"), matches)
    canonical = tres.canonical_work_id or (str(m0.get("id")) if m0.get("id") is not None else None)
    plat_rows = [p for p in (plat.get("platforms") or []) if isinstance(p, dict)]
    # geo_restrictions 为说明文字，不作为 ISO 地区码填入 offer.region
    stream_offers = platform_dicts_to_offers(plat_rows, geo_region=None)

    r = TVAvailabilityResult(
        query_title=title,
        canonical_work_id=canonical,
        standard_title=standard_title,
        alternative_titles=alt,
        release_year=release_year,
        region=region,
        seasons=seasons,
        episodes=episodes,
        platforms=platforms,
        streaming_offers=stream_offers,
        similar_titles=similar_titles,
        geo_restrictions=geo,
        result_status=status,
        confidence=confidence,
        disclaimer=_DEFAULT_DISCLAIMER,
    )
    return {
        "final_result": r.model_dump(mode="json"),
        "node_trace": _trace(state, "assemble_single"),
    }


@lru_cache(maxsize=1)
def _build_compiled_graph() -> Any:
    g = StateGraph(TVAvailabilityGraphState)
    g.add_node("prepare", node_prepare)
    g.add_node("sink_empty_title", node_sink_empty_title)
    g.add_node("fetch_metadata", node_fetch_metadata)
    g.add_node("sink_ambiguous", node_sink_ambiguous)
    g.add_node("sink_no_meta", node_sink_no_meta)
    g.add_node("fetch_platforms", node_fetch_platforms)
    g.add_node("fetch_similar", node_fetch_similar)
    g.add_node("assemble_single", node_assemble_single)

    g.add_edge(START, "prepare")
    g.add_conditional_edges(
        "prepare",
        route_after_prepare,
        {"empty": "sink_empty_title", "metadata": "fetch_metadata"},
    )
    g.add_edge("sink_empty_title", END)
    g.add_conditional_edges(
        "fetch_metadata",
        route_after_metadata,
        {
            "ambiguous": "sink_ambiguous",
            "no_meta": "sink_no_meta",
            "single": "fetch_platforms",
        },
    )
    g.add_edge("sink_ambiguous", END)
    g.add_edge("sink_no_meta", END)
    g.add_edge("fetch_platforms", "fetch_similar")
    g.add_edge("fetch_similar", "assemble_single")
    g.add_edge("assemble_single", END)

    return g.compile()


def run_tv_availability_graph(
    user_input: str,
    *,
    disambiguation_hint: str | None = None,
    settings: Settings | None = None,
) -> TVAvailabilityResult:
    """
    执行剧名查询图，返回与原先 pipeline 一致的 `TVAvailabilityResult`。

    若需使配置变更反映到已编译图，调用方应先 `clear_settings_cache()`（测试场景）。
    """
    _ = settings  # 预留与显式注入 Settings 对齐；节点内使用 get_settings()
    initial: TVAvailabilityGraphState = {
        "query_title": user_input,
        "disambiguation_hint": disambiguation_hint,
        "node_trace": [],
        "graph_errors": [],
    }
    app = _build_compiled_graph()
    out = app.invoke(initial)
    fr = out.get("final_result")
    if not isinstance(fr, dict):
        return TVAvailabilityResult(
            query_title=user_input.strip(),
            result_status=ResultStatus.NOT_FOUND,
            confidence="图执行未产生 final_result",
            disclaimer=_DEFAULT_DISCLAIMER,
            pipeline_node_trace=list(out.get("node_trace") or []),
        )
    base = TVAvailabilityResult.model_validate(fr)
    node_trace = list(out.get("node_trace") or [])
    return base.model_copy(update={"pipeline_node_trace": node_trace})


def clear_tv_graph_compile_cache() -> None:
    """测试或热重载图结构时清空编译缓存。"""
    _build_compiled_graph.cache_clear()
