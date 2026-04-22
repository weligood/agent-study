"""
相似 / 替代剧集：统一入口，便于后续换源、重排或融合个性化信号。
"""

from __future__ import annotations

from typing import Any

from tv_agent.domain.schemas import CandidateTitle
from tv_agent.tools.internal.web_search import _search_similar_web


def fetch_similar_envelope(work_id: str, standard_title: str) -> dict[str, Any]:
    """调用底层相似检索，返回原始 envelope（含 similar_works）。"""
    return _search_similar_web(work_id, standard_title)


def similar_envelope_to_candidates(sim: dict[str, Any]) -> list[CandidateTitle]:
    """将相似检索 envelope 转为 `CandidateTitle` 列表。"""
    out: list[CandidateTitle] = []
    if not sim.get("ok"):
        return out
    for s in sim.get("similar_works") or []:
        if not isinstance(s, dict):
            continue
        out.append(
            CandidateTitle(
                standard_title=str(s.get("standard_title", "")).strip(),
                release_year=s.get("release_year"),
                region=s.get("region"),
                brief_note=s.get("brief_note"),
                work_id=s.get("work_id"),
                score=None,
            )
        )
    return out
