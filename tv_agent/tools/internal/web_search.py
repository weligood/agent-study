"""
联网检索实现：元数据、平台、演员、相似剧（SearXNG / DuckDuckGo）。

供 LangGraph 节点与 LangChain Agent 工具层共用；本模块不含 @tool 装饰器。
"""

from __future__ import annotations

import re
from typing import Any

from tv_agent.resources.provider_catalog import (
    PLATFORM_KEYWORDS,
    PLATFORM_LOGOS_MAP,
    build_search_url,
)
from tv_agent.search.backends import run_unified_web_search


def _normalize_title(title: str) -> str:
    """基础清洗：去首尾空白、书名号、常见引号；统一 lower 便于英文匹配。"""
    t = title.strip()
    t = re.sub(r"^[《「『\"]+|[》」』\"]+$", "", t)
    return t.strip().lower()


def search_api_query(query: str, num_results: int = 5) -> dict[str, Any] | None:
    """
    统一联网搜索（SearXNG → 可选 DuckDuckGo 回退）：返回含 organic_results / knowledge_graph 的 dict，失败返回 None。
    """
    return run_unified_web_search(query, num_results=num_results)


def search_metadata(title: str, hint: str | None) -> dict[str, Any]:
    """通过联网搜索获取电视剧元数据线索。"""
    query = f"{title} 电视剧 豆瓣"
    if hint:
        query = f"{title} {hint} 电视剧 豆瓣"
    raw = search_api_query(query, num_results=5)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "query_title": title,
            "normalized_key": _normalize_title(title),
            "disambiguation_required": False,
            "matches": [],
            "message": "联网搜索不可用：请配置 SEARXNG_BASE_URL，或启用 SEARCH_FALLBACK_DDG 并安装 duckduckgo-search。",
        }

    kg = raw.get("knowledge_graph", {})
    organic = raw.get("organic_results", [])

    standard_title = kg.get("title", title.strip())
    release_year = None
    episodes = None
    region = None

    for key in ("首播", "first_aired", "首播时间", "上映时间"):
        val = kg.get(key, "")
        if val:
            m = re.search(r"(\d{4})", str(val))
            if m:
                release_year = int(m.group(1))
                break
    for key in ("集数", "episodes", "总集数"):
        val = kg.get(key, "")
        if val:
            m = re.search(r"(\d+)", str(val))
            if m:
                episodes = int(m.group(1))
                break
    for key in ("国家/地区", "country", "地区", "产地"):
        val = kg.get(key, "")
        if val:
            region = str(val)
            break

    if not release_year or not episodes:
        for item in organic[:5]:
            snippet = item.get("snippet", "") + " " + item.get("title", "")
            if not release_year:
                m = re.search(r"(\d{4})年", snippet)
                if m:
                    yr = int(m.group(1))
                    if 1950 <= yr <= 2030:
                        release_year = yr
            if not episodes:
                m = re.search(r"(\d+)集", snippet)
                if m:
                    episodes = int(m.group(1))

    match_entry = {
        "standard_title": standard_title,
        "alternative_titles": [],
        "release_year": release_year,
        "region": region or "未知",
        "seasons": 1,
        "episodes": episodes,
        "source_tier": "web_search",
        "id": f"web-{_normalize_title(standard_title)}-{release_year or 'unknown'}",
    }

    return {
        "ok": True,
        "source": "web_search",
        "query_title": title,
        "normalized_key": _normalize_title(title),
        "disambiguation_required": False,
        "matches": [match_entry],
        "message": f"通过联网搜索获取到 '{standard_title}' 的线索信息。",
    }


def search_platforms(work_id: str, title: str, year: int | None) -> dict[str, Any]:
    """通过联网搜索获取电视剧的正版播放平台线索。"""
    query = f"{title} 在线观看 正版 哪个平台"
    if year:
        query = f"{title} {year} 在线观看 正版 哪个平台"
    raw = search_api_query(query, num_results=8)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "work_id": work_id,
            "standard_title": title,
            "platforms": [],
            "message": "联网搜索不可用：请配置 SEARXNG_BASE_URL，或启用 SEARCH_FALLBACK_DDG 并安装 duckduckgo-search。",
        }

    organic = raw.get("organic_results", [])
    kg = raw.get("knowledge_graph", {})

    found_platforms: dict[str, str] = {}

    for item in organic:
        link = item.get("link", "")
        text = (item.get("title", "") + " " + item.get("snippet", "") + " " + link).lower()
        for keyword, platform_name in PLATFORM_KEYWORDS:
            if keyword.lower() in text and platform_name not in found_platforms:
                found_platforms[platform_name] = build_search_url(platform_name, title)

    for key in ("在线观看", "streaming", "观看渠道", "播放平台"):
        val = kg.get(key)
        if isinstance(val, list):
            for v in val:
                name = str(v.get("name", v) if isinstance(v, dict) else v)
                for _, pn in PLATFORM_KEYWORDS:
                    if pn.lower() in name.lower() or name.lower() in pn.lower():
                        if pn not in found_platforms:
                            found_platforms[pn] = build_search_url(pn, title)
        elif isinstance(val, str):
            for _, pn in PLATFORM_KEYWORDS:
                if pn in val:
                    if pn not in found_platforms:
                        found_platforms[pn] = build_search_url(pn, title)

    if not found_platforms:
        return {
            "ok": True,
            "source": "web_search",
            "work_id": work_id,
            "standard_title": title,
            "release_year": year,
            "platforms": [],
            "geo_restrictions": None,
            "message": f"未在联网搜索结果中发现 '{title}' 的正版播放平台。",
        }

    platforms_list = []
    for pname, url in found_platforms.items():
        platforms_list.append({
            "platform_name": pname,
            "availability_status": "available",
            "membership_required": pname not in ("央视网",),
            "payment_type": "free" if pname in ("央视网", "哔哩哔哩") else "subscription",
            "offline_download_supported": False,
            "official_url": url,
            "logo_url": PLATFORM_LOGOS_MAP.get(pname, ""),
            "notes": "通过联网搜索获取的平台线索，请以平台实际片库为准。",
        })

    return {
        "ok": True,
        "source": "web_search",
        "work_id": work_id,
        "standard_title": title,
        "release_year": year,
        "platforms": platforms_list,
        "geo_restrictions": "正版片库通常受地域与版权窗口影响。",
        "message": f"通过联网搜索发现 {len(platforms_list)} 个正版播放平台线索。",
    }


def search_by_actor_web(actor_name: str) -> dict[str, Any]:
    """通过联网搜索获取演员参演的电视剧列表。"""
    actor = actor_name.strip()
    query = f"{actor} 主演 电视剧 作品列表"
    raw = search_api_query(query, num_results=8)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "actor": actor,
            "related_works": [],
            "message": "联网搜索不可用：请配置 SEARXNG_BASE_URL，或启用 SEARCH_FALLBACK_DDG 并安装 duckduckgo-search。",
        }

    organic = raw.get("organic_results", [])
    kg = raw.get("knowledge_graph", {})

    works: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    for key in ("电视作品", "电视剧", "tv_shows", "known_for", "作品"):
        val = kg.get(key)
        if isinstance(val, list):
            for v in val:
                name = str(v.get("name", v) if isinstance(v, dict) else v).strip()
                if name and name not in seen_titles:
                    seen_titles.add(name)
                    year_match = re.search(r"\((\d{4})\)", str(v)) if isinstance(v, dict) else None
                    works.append({
                        "standard_title": name,
                        "release_year": int(year_match.group(1)) if year_match else None,
                        "region": "未知",
                        "episodes": None,
                        "work_id": f"web-{_normalize_title(name)}-unknown",
                    })

    for item in organic[:5]:
        snippet = item.get("snippet", "") + " " + item.get("title", "")
        titles_in_snippet = re.findall(r"《([^》]+)》", snippet)
        for t in titles_in_snippet:
            t = t.strip()
            if t and t not in seen_titles and len(t) <= 20:
                seen_titles.add(t)
                year_match = re.search(rf"{re.escape(t)}.*?(\d{{4}})", snippet)
                works.append({
                    "standard_title": t,
                    "release_year": int(year_match.group(1)) if year_match else None,
                    "region": "未知",
                    "episodes": None,
                    "work_id": f"web-{_normalize_title(t)}-unknown",
                })

    return {
        "ok": True,
        "source": "web_search",
        "actor": actor,
        "related_works": works,
        "message": f"通过联网搜索找到 {len(works)} 部 '{actor}' 的相关作品。",
    }


def search_similar_web(work_id: str, title: str) -> dict[str, Any]:
    """通过联网搜索获取相似剧推荐。"""
    query = f"{title} 类似的电视剧 推荐"
    raw = search_api_query(query, num_results=8)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "work_id": work_id,
            "similar_works": [],
            "message": "联网搜索不可用：请配置 SEARXNG_BASE_URL，或启用 SEARCH_FALLBACK_DDG 并安装 duckduckgo-search。",
        }

    organic = raw.get("organic_results", [])
    works: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    seen_titles.add(_normalize_title(title))

    for item in organic[:8]:
        snippet = item.get("snippet", "") + " " + item.get("title", "")
        titles_in_snippet = re.findall(r"《([^》]+)》", snippet)
        for t in titles_in_snippet:
            t = t.strip()
            if t and _normalize_title(t) not in seen_titles and len(t) <= 20:
                seen_titles.add(_normalize_title(t))
                works.append({
                    "standard_title": t,
                    "release_year": None,
                    "region": "未知",
                    "episodes": None,
                    "work_id": f"web-{_normalize_title(t)}-unknown",
                    "brief_note": None,
                })
                if len(works) >= 6:
                    break
        if len(works) >= 6:
            break

    return {
        "ok": True,
        "source": "web_search",
        "work_id": work_id,
        "similar_works": works,
        "message": f"通过联网搜索推荐 {len(works)} 部相似作品。",
    }


# 图节点与旧代码使用的下划线别名
_search_metadata = search_metadata
_search_platforms = search_platforms
_search_by_actor_web = search_by_actor_web
_search_similar_web = search_similar_web
_search_api_query = search_api_query
