"""
LangChain @tool：剧名检索、消歧、平台、相似、联网补充与视频工具注册。

内部检索实现见 `tv_agent.tools.internal`；视频工具见同包的 `video_tools`。
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from tv_agent.resolution.title_resolver import resolve_title_for_query
from tv_agent.tools.internal.web_search import (
    search_api_query,
    search_by_actor_web,
    search_metadata,
    search_platforms,
    search_similar_web,
)

logger = logging.getLogger(__name__)


def _tool_search_metadata_payload(query_title: str, disambiguation_hint: str | None) -> str:
    logger.info("search_titles: query=%r hint=%r", query_title, disambiguation_hint)
    try:
        payload = search_metadata(query_title, disambiguation_hint)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("search_titles 失败: %s", e)
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
def search_titles(query_title: str, disambiguation_hint: str | None = None) -> str:
    """
    联网检索剧集元数据线索（标准名、年份、地区、季/集、matches 列表）。

    不负责消歧打分；消歧与 canonical id 请使用 `resolve_title`。
    """
    return _tool_search_metadata_payload(query_title, disambiguation_hint)


@tool
def search_tv_metadata(query_title: str, disambiguation_hint: str | None = None) -> str:
    """[兼容] 与 search_titles 相同。"""
    return _tool_search_metadata_payload(query_title, disambiguation_hint)


@tool
def resolve_title(
    metadata_json: str,
    disambiguation_hint: str | None = None,
    selected_work_id: str | None = None,
) -> str:
    """
    对 `search_titles` 返回的 JSON 做清洗、打分与 canonical work id 解析。

    :param metadata_json: `search_titles` 的完整返回字符串。
    :param disambiguation_hint: 年份 / S季 / 集等线索。
    :param selected_work_id: 用户选定条目的 work_id，传入后直接锁定。
    """
    logger.info("resolve_title: hint=%r selected=%r", disambiguation_hint, selected_work_id)
    try:
        env = json.loads(metadata_json)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"ok": False, "message": f"metadata_json 解析失败: {e!s}"},
            ensure_ascii=False,
        )
    if not isinstance(env, dict):
        return json.dumps({"ok": False, "message": "metadata_json 须为 JSON 对象"}, ensure_ascii=False)
    matches = list(env.get("matches") or [])
    qt = str(env.get("query_title", ""))
    tres = resolve_title_for_query(
        qt,
        disambiguation_hint,
        matches,
        selected_work_id=selected_work_id,
    )
    return json.dumps(
        {
            "ok": True,
            "title_resolution": tres.model_dump(mode="json"),
            "matches": matches,
            "message": "标题规范化完成；`fetch_availability` 请使用 title_resolution.canonical_work_id 与 standard_title。",
        },
        ensure_ascii=False,
    )


def _tool_streaming_platforms_payload(
    work_id: str,
    standard_title: str,
    release_year: str | None,
    *,
    log_tag: str,
) -> str:
    year_int: int | None
    try:
        year_int = int(release_year) if release_year not in (None, "", "null") else None
    except ValueError:
        year_int = None

    logger.info("%s: work_id=%r title=%r year=%r", log_tag, work_id, standard_title, release_year)
    try:
        payload = search_platforms(work_id, standard_title, year_int)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("%s 失败: %s", log_tag, e)
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
def fetch_availability(work_id: str, standard_title: str, release_year: str | None = None) -> str:
    """
    查询正版播放平台（会员/付费、官方链接、地区说明等）。

    :param work_id: `resolve_title` 返回的 canonical_work_id。
    :param standard_title: 标准剧名。
    :param release_year: 四位年份字符串，可空。
    """
    return _tool_streaming_platforms_payload(
        work_id, standard_title, release_year, log_tag="fetch_availability",
    )


@tool
def search_streaming_platforms(work_id: str, standard_title: str, release_year: str | None = None) -> str:
    """[兼容] 同 fetch_availability。"""
    return _tool_streaming_platforms_payload(
        work_id, standard_title, release_year, log_tag="search_streaming_platforms",
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
        payload = search_by_actor_web(actor_name)
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


def _tool_similar_titles_payload(work_id: str, standard_title: str, *, log_tag: str) -> str:
    logger.info("%s: work_id=%r title=%r", log_tag, work_id, standard_title)
    try:
        payload = search_similar_web(work_id, standard_title)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("%s 失败: %s", log_tag, e)
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
def fetch_similar_titles(work_id: str, standard_title: str) -> str:
    """
    根据 canonical work id 与标准剧名，检索相似剧集推荐。

    :param work_id: `resolve_title` 返回的 canonical_work_id。
    :param standard_title: 标准剧名。
    """
    return _tool_similar_titles_payload(work_id, standard_title, log_tag="fetch_similar_titles")


@tool
def recommend_similar_tv(work_id: str, standard_title: str) -> str:
    """[兼容] 同 fetch_similar_titles。"""
    return _tool_similar_titles_payload(work_id, standard_title, log_tag="recommend_similar_tv")


@tool
def web_search_tv_info(search_query: str) -> str:
    """
    使用联网搜索获取电视剧的公开信息（播放平台、演员、评分等）。

    构建搜索关键词时建议加上 "正版 播放平台" 或 "哪里可以看" 等限定词。

    :param search_query: 搜索关键词，如 "庆余年 正版 在哪看" 或 "张译 最新电视剧 2024"。
    :return: JSON 字符串，包含搜索结果摘要。
    """
    logger.info("web_search_tv_info: query=%r", search_query)
    try:
        raw = search_api_query(search_query)
        if raw is None:
            return json.dumps({
                "ok": False,
                "source": "web_search",
                "message": "联网搜索不可用：请配置 SEARXNG_BASE_URL，或启用 SEARCH_FALLBACK_DDG 并安装 duckduckgo-search。",
                "results": [],
            }, ensure_ascii=False)

        organic = raw.get("organic_results", [])
        results = []
        for item in organic[:8]:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "displayed_link": item.get("displayed_link", ""),
            })

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

        answer_box = raw.get("answer_box", {})
        answer = None
        if answer_box:
            answer = {
                "title": answer_box.get("title"),
                "answer": answer_box.get("answer") or answer_box.get("snippet"),
            }

        return json.dumps({
            "ok": True,
            "source": "web_search",
            "query": search_query,
            "knowledge_graph": kg_info,
            "answer_box": answer,
            "organic_results": results,
            "message": f"从联网搜索获取到 {len(results)} 条结果。请基于这些信息综合回答。",
        }, ensure_ascii=False)

    except Exception as e:  # noqa: BLE001
        logger.exception("web_search_tv_info 失败: %s", e)
        return json.dumps({
            "ok": False,
            "source": "error",
            "message": f"Web 搜索异常：{e!s}",
            "results": [],
        }, ensure_ascii=False)


def get_tv_legal_tools() -> list:
    """注册给 Agent 的工具列表（单一职责、结构化输出）。"""
    # 延迟导入，避免与 `agent_tools` 包 `__init__` 的加载顺序形成循环依赖
    from tv_agent.tools.agent_tools import video_tools as _video_tools

    return [
        search_titles,
        resolve_title,
        fetch_availability,
        fetch_similar_titles,
        search_by_actor,
        web_search_tv_info,
        _video_tools.extract_video_page,
        _video_tools.prepare_download,
        _video_tools.confirm_download,
    ]


__all__ = [
    "fetch_availability",
    "fetch_similar_titles",
    "get_tv_legal_tools",
    "recommend_similar_tv",
    "resolve_title",
    "search_by_actor",
    "search_streaming_platforms",
    "search_titles",
    "search_tv_metadata",
    "web_search_tv_info",
]
