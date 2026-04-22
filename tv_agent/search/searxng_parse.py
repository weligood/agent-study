"""
将 SearXNG `format=json` 响应解析为与既有 tools 消费逻辑对齐的 `organic_results` + `knowledge_graph`。

参考 SearXNG 文档与典型 JSON：results、infoboxes、answers、suggestions、unresponsive_engines 等字段。
"""

from __future__ import annotations

import re
from typing import Any

# 将常见英文 / 维基信息框 label 映射到 tools._search_metadata 会读的 key（与 Google KG 风格对齐）
_ATTR_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "首播": ("首播", "first aired", "first aired on", "original release", "premiered", "release date", "上映时间", "首播时间"),
    "集数": ("集数", "episodes", "no. of episodes", "number of episodes", "总集数"),
    "国家/地区": ("国家/地区", "country of origin", "country", "产地", "地区"),
    "导演": ("导演", "directed by", "director", "creators", "created by"),
    "主演": ("主演", "starring", "cast", "主演阵容"),
    "类型": ("类型", "genre", "genres"),
    "description": ("description", "abstract", "summary", "简介", "概述"),
}


def _norm_label(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _canonical_kg_key(label: str) -> str | None:
    n = _norm_label(label)
    for canonical, variants in _ATTR_LABEL_ALIASES.items():
        for v in variants:
            if _norm_label(v) == n:
                return canonical
    return None


def _merge_infobox_into_kg(kg: dict[str, Any], box: dict[str, Any], *, prefix: str = "") -> None:
    """把单个 infobox 的 title / content / attributes / urls 写入 kg。"""
    pfx = f"{prefix}_" if prefix else ""
    title = box.get("infobox") or box.get("title")
    if title and not kg.get("title"):
        kg["title"] = title
    if title and pfx:
        kg[f"{pfx}title"] = title

    content = box.get("content")
    if isinstance(content, str) and content.strip():
        key = f"{pfx}description" if pfx else "description"
        if not kg.get("description"):
            kg[key] = content.strip()
        elif pfx and not kg.get(key):
            kg[key] = content.strip()

    img = box.get("img_src")
    if isinstance(img, str) and img.strip():
        kg[f"{pfx}thumbnail"] = img.strip()

    for a in box.get("attributes") or []:
        if not isinstance(a, dict):
            continue
        label = str(a.get("label", "") or "").strip()
        val = a.get("value", "")
        if not label or val is None or val == "":
            continue
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val if x is not None)
        else:
            val = str(val).strip()
        if not val:
            continue
        canon = _canonical_kg_key(label)
        if canon:
            if canon not in kg or not str(kg.get(canon, "")).strip():
                kg[canon] = val
        key_name = f"{pfx}{label}" if pfx else label
        if key_name not in kg:
            kg[key_name] = val

    for i, u in enumerate(box.get("urls") or []):
        if not isinstance(u, dict):
            continue
        t = str(u.get("title", "") or "").strip()
        href = str(u.get("url", "") or "").strip()
        if href:
            kg[f"{pfx}link_{i}" if pfx else f"official_link_{i}"] = href
            if t:
                kg[f"{pfx}link_{i}_title" if pfx else f"official_link_{i}_title"] = t


def parse_searxng_response(data: dict[str, Any], *, num_results: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    解析 SearXNG JSON，返回 (organic_results, knowledge_graph)。

    knowledge_graph 合并：answers → description；全部 infoboxes；首条 result 的 engine 等元数据。
    """
    organic: list[dict[str, Any]] = []
    kg: dict[str, Any] = {}

    for r in (data.get("results") or [])[:num_results]:
        if not isinstance(r, dict):
            continue
        u = str(r.get("url", "") or "")
        title = str(r.get("title", "") or "")
        snippet = str(r.get("content", "") or r.get("body", "") or "")
        eng = r.get("engine")
        extra_bits: list[str] = []
        if eng:
            extra_bits.append(f"引擎: {eng}")
        if r.get("publishedDate"):
            extra_bits.append(str(r["publishedDate"]))
        if r.get("template"):
            extra_bits.append(f"模板: {r['template']}")
        if extra_bits:
            snippet = (snippet + "\n" + " | ".join(extra_bits)).strip()
        organic.append(
            {
                "title": title,
                "snippet": snippet,
                "link": u,
                "displayed_link": u,
            }
        )

    # instant answers（部分实例返回 str 或 dict）
    answers = data.get("answers") or []
    answer_texts: list[str] = []
    for ans in answers:
        if isinstance(ans, str) and ans.strip():
            answer_texts.append(ans.strip())
        elif isinstance(ans, dict):
            t = ans.get("answer") or ans.get("text") or ans.get("content")
            if isinstance(t, str) and t.strip():
                answer_texts.append(t.strip())
    if answer_texts:
        kg["description"] = "\n".join(answer_texts)
        kg["answer_box"] = {"answer": answer_texts[0]}

    infoboxes = [b for b in (data.get("infoboxes") or []) if isinstance(b, dict)]
    for idx, box in enumerate(infoboxes):
        prefix = f"infobox_{idx}" if idx > 0 else ""
        _merge_infobox_into_kg(kg, box, prefix=prefix)

    # 若仍无 title，用第一个 infobox 的 infobox 字段
    if not kg.get("title") and infoboxes:
        t0 = infoboxes[0].get("infobox") or infoboxes[0].get("title")
        if t0:
            kg["title"] = str(t0)

    # suggestions / corrections 写入 kg 供上层参考
    if data.get("suggestions"):
        kg["suggestions"] = data["suggestions"]
    if data.get("corrections"):
        kg["corrections"] = data["corrections"]
    if data.get("unresponsive_engines"):
        kg["unresponsive_engines"] = data["unresponsive_engines"]

    n = data.get("number_of_results")
    if n is not None:
        kg["number_of_results"] = n

    return organic, kg
