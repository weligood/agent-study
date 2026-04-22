"""
搜索结果 → 规范化标题实体：清洗、别名/年份线索、候选项打分、输出 canonical work id。

后续 availability / 推荐 / 历史 / 片单应优先使用 `canonical_work_id`，字符串仅作展示。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


# 常见中英文剧名别名（可随业务扩展）
_TITLE_ALIASES: dict[str, str] = {
    "the three-body problem": "三体",
    "three body": "三体",
    "breaking bad": "绝命毒师",
}


def scrub_title(raw: str) -> str:
    """清洗用户或搜索返回的标题：去空白、书名号、全角空格。"""
    t = (raw or "").strip()
    t = re.sub(r"^[《「『\"]+|[》」』\"]+$", "", t)
    t = t.replace("\u3000", " ").strip()
    return t


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", "", s.strip().lower())


def apply_alias(title: str) -> str:
    """若命中已知别名映射，返回中文规范名（否则原样）。"""
    k = _norm_key(title)
    for en, zh in _TITLE_ALIASES.items():
        if _norm_key(en) == k:
            return zh
    return title


def parse_hint_ints(hint: str | None) -> dict[str, int | None]:
    """从消歧 hint 中解析年份、季（如 S2）、集。"""
    out: dict[str, int | None] = {"year": None, "season": None, "episode": None}
    if not hint:
        return out
    h = hint.strip()
    m = re.search(r"(19|20)\d{2}", h)
    if m:
        out["year"] = int(m.group(0))
    m = re.search(r"(?i)S(\d+)", h)
    if m:
        out["season"] = int(m.group(1))
    m = re.search(r"(?i)E(\d+)|第(\d+)集", h)
    if m:
        out["episode"] = int(m.group(1) or m.group(2))
    return out


def _score_candidate(
    query_norm: str,
    match: dict[str, Any],
    hint_year: int | None,
) -> float:
    """同名条目简单打分：标题重合、年份命中加权。"""
    st = _norm_key(str(match.get("standard_title", "")))
    score = 0.0
    if query_norm and query_norm in st:
        score += 2.0
    if st and st in query_norm:
        score += 1.5
    if query_norm == st:
        score += 3.0
    y = match.get("release_year")
    if hint_year is not None and y == hint_year:
        score += 2.5
    elif y is not None:
        score += 0.3
    wid = str(match.get("id", "") or "")
    if wid.startswith("web-"):
        score += 0.1
    return score


class TitleCandidate(BaseModel):
    """带打分的候选项，供消歧展示。"""

    model_config = {"extra": "ignore"}

    standard_title: str
    release_year: int | None = None
    region: str | None = None
    work_id: str | None = Field(default=None, description="canonical 作品 id")
    score: float = 0.0
    brief_note: str | None = None


class TitleResolution(BaseModel):
    """规范化结果：唯一命中或需消歧。"""

    query_raw: str
    query_scrubbed: str
    canonical_work_id: str | None = None
    standard_title: str | None = None
    release_year: int | None = None
    region: str | None = None
    ambiguous: bool = False
    candidates: list[TitleCandidate] = Field(default_factory=list)
    hint_year: int | None = None


def resolve_title_for_query(
    query_title: str,
    disambiguation_hint: str | None,
    matches: list[dict[str, Any]],
    *,
    selected_work_id: str | None = None,
) -> TitleResolution:
    """
    基于元数据 `matches`（search 层 envelope）生成 TitleResolution。

    多条时按分数排序；`canonical_work_id` 仅在唯一高置信或单条时写入。
    若调用方已选定 `selected_work_id`，则直接锁定对应条目。
    """
    scrubbed = apply_alias(scrub_title(query_title))
    hint = parse_hint_ints(disambiguation_hint)
    hint_year = hint.get("year")

    if selected_work_id:
        filt = [m for m in matches if str(m.get("id", "")) == str(selected_work_id)]
        if len(filt) == 1:
            m = filt[0]
            return TitleResolution(
                query_raw=query_title,
                query_scrubbed=scrubbed,
                canonical_work_id=str(m.get("id")) if m.get("id") is not None else None,
                standard_title=str(m.get("standard_title", "")).strip() or None,
                release_year=m.get("release_year"),
                region=m.get("region"),
                ambiguous=False,
                candidates=[
                    TitleCandidate(
                        standard_title=str(m.get("standard_title", "")).strip(),
                        release_year=m.get("release_year"),
                        region=m.get("region"),
                        work_id=str(m.get("id")) if m.get("id") is not None else None,
                        score=10.0,
                        brief_note="user_selected",
                    )
                ],
                hint_year=hint_year,
            )

    qn = _norm_key(scrubbed)

    if not matches:
        return TitleResolution(
            query_raw=query_title,
            query_scrubbed=scrubbed,
            ambiguous=False,
            hint_year=hint_year,
        )

    scored: list[TitleCandidate] = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        sc = _score_candidate(qn, m, hint_year)
        scored.append(
            TitleCandidate(
                standard_title=str(m.get("standard_title", "")).strip(),
                release_year=m.get("release_year"),
                region=m.get("region"),
                work_id=str(m.get("id")) if m.get("id") is not None else None,
                score=sc,
                brief_note=None,
            )
        )
    scored.sort(key=lambda c: c.score, reverse=True)

    ambiguous = len(scored) > 1 and (scored[0].score - scored[1].score) < 0.8
    if len(scored) > 1 and not ambiguous and scored[0].score >= 3.5:
        ambiguous = False

    top = scored[0] if scored else None
    canonical = None
    stitle = None
    reg = None
    ry = None
    if len(scored) == 1:
        canonical = scored[0].work_id
        stitle = scored[0].standard_title
        ry = scored[0].release_year
        reg = scored[0].region
    elif not ambiguous and top and top.work_id:
        canonical = top.work_id
        stitle = top.standard_title
        ry = top.release_year
        reg = top.region

    return TitleResolution(
        query_raw=query_title,
        query_scrubbed=scrubbed,
        canonical_work_id=canonical,
        standard_title=stitle,
        release_year=ry,
        region=reg,
        ambiguous=ambiguous or len(scored) > 1,
        candidates=scored,
        hint_year=hint_year,
    )
