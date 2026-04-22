"""
LangChain 工具：电视剧元数据与正版平台信息查询。

通过 SearchAPI.io（Google 搜索）获取真实数据，无本地模拟数据。
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from langchain_core.tools import tool

from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 基础工具函数
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """基础清洗：去首尾空白、书名号、常见引号；统一 lower 便于英文匹配。"""
    t = title.strip()
    t = re.sub(r"^[《「『\"]+|[》」』\"]+$", "", t)
    return t.strip().lower()


def _fetch_json_get(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any] | None:
    """使用标准库发起 GET 请求并解析 JSON（失败返回 None，不打断 Agent）。"""
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(body)
            return parsed if isinstance(parsed, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("远程搜索请求失败: %s", e)
        return None


def _search_api_query(query: str, num_results: int = 5) -> dict[str, Any] | None:
    """
    调用 SearchAPI.io Google 搜索 API。

    返回原始 JSON 响应（含 organic_results 等），失败返回 None。
    """
    settings = get_settings()
    base = (settings.search_base_url or "").rstrip("/")
    key = settings.search_api_key
    if not base or not key:
        return None

    params = urllib.parse.urlencode({
        "engine": "google",
        "q": query,
        "api_key": key,
        "num": str(num_results),
        "hl": "zh-CN",
        "gl": "cn",
    })
    url = f"{base}?{params}"
    return _fetch_json_get(url, {"Accept": "application/json"}, settings.request_timeout_seconds)


# ---------------------------------------------------------------------------
# 已知视频平台关键词 -> 平台名
# ---------------------------------------------------------------------------
_PLATFORM_KEYWORDS: list[tuple[str, str]] = [
    ("iqiyi", "爱奇艺"), ("爱奇艺", "爱奇艺"),
    ("v.qq.com", "腾讯视频"), ("腾讯视频", "腾讯视频"),
    ("youku", "优酷"), ("优酷", "优酷"),
    ("bilibili", "哔哩哔哩"), ("哔哩哔哩", "哔哩哔哩"), ("B站", "哔哩哔哩"),
    ("mgtv", "芒果TV"), ("芒果TV", "芒果TV"), ("芒果", "芒果TV"),
    ("netflix", "Netflix"),
    ("cctv", "央视网"), ("央视", "央视网"),
    ("mango", "芒果TV"),
]

_PLATFORM_LOGOS_MAP = {
    "爱奇艺": "https://www.iqiyi.com/favicon.ico",
    "腾讯视频": "https://v.qq.com/favicon.ico",
    "优酷": "https://www.youku.com/favicon.ico",
    "芒果TV": "https://www.mgtv.com/favicon.ico",
    "哔哩哔哩": "https://www.bilibili.com/favicon.ico",
    "Netflix": "https://www.netflix.com/favicon.ico",
    "央视网": "https://tv.cctv.com/favicon.ico",
}


def _build_search_url(platform_name: str, title: str) -> str:
    """为平台构建 PC 版搜索链接（使用主域名，避免子域名被屏蔽）。"""
    encoded = urllib.parse.quote(title)
    url_map = {
        "爱奇艺": f"https://www.iqiyi.com/search/{encoded}",
        "腾讯视频": f"https://v.qq.com/x/search/?q={encoded}",
        "优酷": f"https://www.youku.com/search/{encoded}",
        "哔哩哔哩": f"https://www.bilibili.com/search?keyword={encoded}",
        "芒果TV": f"https://www.mgtv.com/so/{encoded}.html",
        "Netflix": f"https://www.netflix.com/search?q={encoded}",
        "央视网": f"https://tv.cctv.com/search/?qtext={encoded}",
    }
    return url_map.get(platform_name, f"https://www.google.com/search?q={encoded}+{urllib.parse.quote(platform_name)}")


# ---------------------------------------------------------------------------
# 元数据查询（Google 搜索）
# ---------------------------------------------------------------------------

def _search_metadata(title: str, hint: str | None) -> dict[str, Any]:
    """通过 Google 搜索获取电视剧真实元数据。"""
    query = f"{title} 电视剧 豆瓣"
    if hint:
        query = f"{title} {hint} 电视剧 豆瓣"
    raw = _search_api_query(query, num_results=5)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "query_title": title,
            "normalized_key": _normalize_title(title),
            "disambiguation_required": False,
            "matches": [],
            "message": "搜索 API 未配置或不可用，请检查 SEARCH_BASE_URL 和 SEARCH_API_KEY 环境变量。",
        }

    kg = raw.get("knowledge_graph", {})
    organic = raw.get("organic_results", [])

    # 从 knowledge_graph 提取
    standard_title = kg.get("title", title.strip())
    release_year = None
    episodes = None
    region = None

    # 尝试从 KG attributes 提取
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

    # 如果 KG 没有，从 organic snippets 提取
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
        "message": f"通过 Google 搜索获取到 '{standard_title}' 的真实信息。",
    }


# ---------------------------------------------------------------------------
# 平台查询（Google 搜索）
# ---------------------------------------------------------------------------

def _search_platforms(work_id: str, title: str, year: int | None) -> dict[str, Any]:
    """通过 Google 搜索获取电视剧的真实正版播放平台。"""
    query = f"{title} 在线观看 正版 哪个平台"
    if year:
        query = f"{title} {year} 在线观看 正版 哪个平台"
    raw = _search_api_query(query, num_results=8)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "work_id": work_id,
            "standard_title": title,
            "platforms": [],
            "message": "搜索 API 未配置或不可用，请检查 SEARCH_BASE_URL 和 SEARCH_API_KEY 环境变量。",
        }

    organic = raw.get("organic_results", [])
    kg = raw.get("knowledge_graph", {})

    # 收集发现的平台 {平台名: 最佳链接}
    found_platforms: dict[str, str] = {}

    # 从 organic_results 中发现平台
    for item in organic:
        link = item.get("link", "")
        text = (item.get("title", "") + " " + item.get("snippet", "") + " " + link).lower()
        for keyword, platform_name in _PLATFORM_KEYWORDS:
            if keyword.lower() in text and platform_name not in found_platforms:
                found_platforms[platform_name] = _build_search_url(platform_name, title)

    # 从 knowledge_graph 的 streaming 信息提取
    for key in ("在线观看", "streaming", "观看渠道", "播放平台"):
        val = kg.get(key)
        if isinstance(val, list):
            for v in val:
                name = str(v.get("name", v) if isinstance(v, dict) else v)
                for _, pn in _PLATFORM_KEYWORDS:
                    if pn.lower() in name.lower() or name.lower() in pn.lower():
                        if pn not in found_platforms:
                            found_platforms[pn] = _build_search_url(pn, title)
        elif isinstance(val, str):
            for _, pn in _PLATFORM_KEYWORDS:
                if pn in val:
                    if pn not in found_platforms:
                        found_platforms[pn] = _build_search_url(pn, title)

    if not found_platforms:
        return {
            "ok": True,
            "source": "web_search",
            "work_id": work_id,
            "standard_title": title,
            "release_year": year,
            "platforms": [],
            "geo_restrictions": None,
            "message": f"未在 Google 搜索结果中发现 '{title}' 的正版播放平台。",
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
            "logo_url": _PLATFORM_LOGOS_MAP.get(pname, ""),
            "notes": "通过 Google 搜索获取的真实平台信息，请以平台实际片库为准。",
        })

    return {
        "ok": True,
        "source": "web_search",
        "work_id": work_id,
        "standard_title": title,
        "release_year": year,
        "platforms": platforms_list,
        "geo_restrictions": "正版片库通常受地域与版权窗口影响。",
        "message": f"通过 Google 搜索发现 {len(platforms_list)} 个正版播放平台。",
    }


# ---------------------------------------------------------------------------
# 演员查询（Google 搜索）
# ---------------------------------------------------------------------------

def _search_by_actor_web(actor_name: str) -> dict[str, Any]:
    """通过 Google 搜索获取演员参演的电视剧列表。"""
    actor = actor_name.strip()
    query = f"{actor} 主演 电视剧 作品列表"
    raw = _search_api_query(query, num_results=8)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "actor": actor,
            "related_works": [],
            "message": "搜索 API 未配置或不可用，请检查环境变量。",
        }

    organic = raw.get("organic_results", [])
    kg = raw.get("knowledge_graph", {})

    works: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    # 从 KG 提取
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

    # 从 organic snippets 提取剧名（用书名号匹配）
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
        "message": f"通过 Google 搜索找到 {len(works)} 部 '{actor}' 的相关作品。",
    }


# ---------------------------------------------------------------------------
# 相似剧推荐（Google 搜索）
# ---------------------------------------------------------------------------

def _search_similar_web(work_id: str, title: str) -> dict[str, Any]:
    """通过 Google 搜索获取相似剧推荐。"""
    query = f"{title} 类似的电视剧 推荐"
    raw = _search_api_query(query, num_results=8)
    if raw is None:
        return {
            "ok": False,
            "source": "web_search",
            "work_id": work_id,
            "similar_works": [],
            "message": "搜索 API 未配置或不可用，请检查环境变量。",
        }

    organic = raw.get("organic_results", [])
    works: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    # 排除自身
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
        "message": f"通过 Google 搜索推荐 {len(works)} 部相似作品。",
    }


# ---------------------------------------------------------------------------
# LangChain 工具定义
# ---------------------------------------------------------------------------

@tool
def search_tv_metadata(query_title: str, disambiguation_hint: str | None = None) -> str:
    """
    查询电视剧基础信息：标准名、别名、年份、地区、季/集等。

    :param query_title: 用户输入或清洗后的剧名。
    :param disambiguation_hint: 可选消歧提示：四位年份。
    :return: JSON 字符串（envelope），供 Agent 解析。
    """
    logger.info("search_tv_metadata: query=%r hint=%r", query_title, disambiguation_hint)
    try:
        payload = _search_metadata(query_title, disambiguation_hint)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("search_tv_metadata 失败: %s", e)
        return json.dumps(
            {
                "ok": False,
                "source": "error",
                "query_title": query_title,
                "matches": [],
                "message": f"元数据查询异常（已抑制）：{e!s}",
            },
            ensure_ascii=False,
        )


@tool
def search_streaming_platforms(work_id: str, standard_title: str, release_year: str | None = None) -> str:
    """
    查询正版播放平台：会员/付费、官方链接、地区限制说明等。

    :param work_id: 元数据工具返回的内部作品标识。
    :param standard_title: 标准剧名（辅助搜索）。
    :param release_year: 上映年份字符串，可空。
    :return: JSON 字符串（envelope）。
    """
    year_int: int | None
    try:
        year_int = int(release_year) if release_year not in (None, "", "null") else None
    except ValueError:
        year_int = None

    logger.info(
        "search_streaming_platforms: work_id=%r title=%r year=%r",
        work_id, standard_title, release_year,
    )
    try:
        payload = _search_platforms(work_id, standard_title, year_int)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("search_streaming_platforms 失败: %s", e)
        return json.dumps(
            {
                "ok": False,
                "source": "error",
                "work_id": work_id,
                "platforms": [],
                "message": f"平台查询异常（已抑制）：{e!s}",
            },
            ensure_ascii=False,
        )


@tool
def search_by_actor(actor_name: str) -> str:
    """
    根据演员姓名查询其参演的电视剧列表。

    :param actor_name: 演员姓名（如 "张译"、"胡歌"）。
    :return: JSON 字符串，包含 related_works 列表。
    """
    logger.info("search_by_actor: actor=%r", actor_name)
    try:
        payload = _search_by_actor_web(actor_name)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("search_by_actor 失败: %s", e)
        return json.dumps(
            {
                "ok": False,
                "source": "error",
                "actor": actor_name,
                "related_works": [],
                "message": f"演员查询异常（已抑制）：{e!s}",
            },
            ensure_ascii=False,
        )


@tool
def recommend_similar_tv(work_id: str, standard_title: str) -> str:
    """
    根据剧名推荐风格或题材相似的电视剧。

    :param work_id: 元数据工具返回的内部作品标识。
    :param standard_title: 标准剧名。
    :return: JSON 字符串，包含 similar_works 列表。
    """
    logger.info("recommend_similar_tv: work_id=%r title=%r", work_id, standard_title)
    try:
        payload = _search_similar_web(work_id, standard_title)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("recommend_similar_tv 失败: %s", e)
        return json.dumps(
            {
                "ok": False,
                "source": "error",
                "work_id": work_id,
                "similar_works": [],
                "message": f"相似剧推荐异常（已抑制）：{e!s}",
            },
            ensure_ascii=False,
        )


@tool
def web_search_tv_info(search_query: str) -> str:
    """
    使用 Google 搜索获取电视剧的真实信息（播放平台、演员、评分等）。

    构建搜索关键词时建议加上 "正版 播放平台" 或 "哪里可以看" 等限定词。

    :param search_query: 搜索关键词，如 "庆余年 正版 在哪看" 或 "张译 最新电视剧 2024"。
    :return: JSON 字符串，包含搜索结果摘要。
    """
    logger.info("web_search_tv_info: query=%r", search_query)
    try:
        raw = _search_api_query(search_query)
        if raw is None:
            return json.dumps({
                "ok": False,
                "source": "web_search",
                "message": "搜索 API 未配置或不可用，请检查环境变量。",
                "results": [],
            }, ensure_ascii=False)

        # 提取 organic_results 中的关键信息
        organic = raw.get("organic_results", [])
        results = []
        for item in organic[:8]:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "displayed_link": item.get("displayed_link", ""),
            })

        # 提取知识面板（如果有）
        knowledge_graph = raw.get("knowledge_graph", {})
        kg_info = None
        if knowledge_graph:
            kg_info = {
                "title": knowledge_graph.get("title"),
                "type": knowledge_graph.get("type"),
                "description": knowledge_graph.get("description"),
                "attributes": {k: v for k, v in knowledge_graph.items()
                               if k in ("导演", "主演", "集数", "首播", "类型",
                                        "director", "starring", "episodes",
                                        "first_aired", "genre", "network")},
            }

        # 提取 answer_box（如果有）
        answer_box = raw.get("answer_box", {})
        answer = None
        if answer_box:
            answer = {
                "title": answer_box.get("title"),
                "answer": answer_box.get("answer") or answer_box.get("snippet"),
            }

        return json.dumps({
            "ok": True,
            "source": "web_search_google",
            "query": search_query,
            "knowledge_graph": kg_info,
            "answer_box": answer,
            "organic_results": results,
            "message": f"从 Google 搜索获取到 {len(results)} 条结果。请基于这些信息综合回答。",
        }, ensure_ascii=False)

    except Exception as e:  # noqa: BLE001
        logger.exception("web_search_tv_info 失败: %s", e)
        return json.dumps({
            "ok": False,
            "source": "error",
            "message": f"Web 搜索异常：{e!s}",
            "results": [],
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 视频爬取工具（基于 video_scraper 模块）
# ---------------------------------------------------------------------------

@tool
def extract_video_info(video_url: str) -> str:
    """
    从视频 URL 提取元数据（标题、时长、上传者、清晰度列表等），不下载视频文件。

    支持的平台：优酷（youku.com）、哔哩哔哩（bilibili.com）。
    URL 示例：
    - 优酷: https://v.youku.com/v_show/id_XXXXXXXXXXXX.html
    - B站: https://www.bilibili.com/video/BVxxxxxxxxxx

    :param video_url: 视频页面 URL。
    :return: JSON 字符串，包含视频标题、时长、可用清晰度等信息。
    """
    logger.info("extract_video_info: url=%r", video_url)
    try:
        from video_scraper import extract_info as _extract_info

        info = _extract_info(video_url)
        # 返回精简信息给 Agent（不暴露流直链）
        result = {
            "ok": True,
            "platform": info.platform,
            "video_id": info.id,
            "title": info.title,
            "url": info.url,
            "duration": info.duration,
            "duration_display": f"{info.duration // 60}分{info.duration % 60}秒" if info.duration else None,
            "thumbnail": info.thumbnail,
            "uploader": info.uploader,
            "uploader_id": info.uploader_id,
            "description": (info.description or "")[:200],
            "view_count": info.view_count,
            "like_count": info.like_count,
            "upload_date": info.upload_date,
            "available_qualities": [
                {"quality": f.quality, "width": f.width, "height": f.height, "format": f.ext}
                for f in info.formats if f.url  # 只列出有直链的格式
            ],
            "total_formats": len(info.formats),
            "extra": info.extra,
            "message": f"成功提取 '{info.title}' 的视频信息，共 {len(info.formats)} 个可用格式。",
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("extract_video_info 失败: %s", e)
        return json.dumps({
            "ok": False,
            "message": f"视频信息提取失败: {e!s}",
            "video_url": video_url,
        }, ensure_ascii=False)


@tool
def download_video(video_url: str, quality: str = "highest") -> str:
    """
    下载指定 URL 的视频文件到本地，可选清晰度。

    先提取视频信息，再执行下载。默认选择最高清晰度。

    :param video_url: 视频页面 URL。
    :param quality: 清晰度选择：'highest'（最高）、'lowest'（最低），或具体标签如 '1080P 高清'。
    :return: JSON 字符串，包含下载结果（文件路径、大小、耗时等）。
    """
    logger.info("download_video: url=%r quality=%r", video_url, quality)
    try:
        from video_scraper import extract_info as _extract_info
        from video_scraper.downloader import download_video as _download

        info = _extract_info(video_url)
        result = _download(info, quality=quality)
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("download_video 失败: %s", e)
        return json.dumps({
            "success": False,
            "message": f"视频下载失败: {e!s}",
            "video_url": video_url,
        }, ensure_ascii=False)


def get_tv_legal_tools() -> list:
    """注册给 Agent 的工具列表。"""
    return [
        search_tv_metadata,
        search_streaming_platforms,
        search_by_actor,
        recommend_similar_tv,
        web_search_tv_info,
        extract_video_info,
        download_video,
    ]
