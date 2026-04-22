"""
视频提取 LangGraph：先分类 URL → 仅进入对应平台提取节点，不依次尝试所有 Extractor。

与原先「for 循环 suitable」语义一致，但决策与单次爬取在图中可观测（node_trace），便于日志与扩展。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from tv_agent.graphs.state import VideoExtractGraphState
from video_scraper.base import BaseExtractor, ExtractionError
from video_scraper.models import VideoInfo
from video_scraper.registry import EXTRACTOR_CLASSES, get_extractor, get_extractor_routes

logger = logging.getLogger(__name__)


def _trace(state: VideoExtractGraphState, step: str) -> list[str]:
    return list(state.get("node_trace", [])) + [step]


def node_classify(state: VideoExtractGraphState) -> dict[str, Any]:
    u = (state.get("url") or "").strip()
    trace = _trace(state, "classify")
    for route, cls in get_extractor_routes():
        if cls.suitable(u):
            trace = trace + [f"route:{route}"]
            logger.info("视频提取图：URL 路由至 %s", route)
            return {"url": u, "platform_route": route, "node_trace": trace}
    logger.info("视频提取图：无匹配平台")
    return {"url": u, "platform_route": "unknown", "node_trace": trace + ["route:unknown"]}


def route_after_classify(state: VideoExtractGraphState) -> str:
    return state.get("platform_route") or "unknown"


def _make_extract_node(cls: type[BaseExtractor], route: str):
    def node(state: VideoExtractGraphState) -> dict[str, Any]:
        u = state["url"]
        t = _trace(state, f"extract:{route}")
        try:
            info = get_extractor(cls).extract(u)
            return {"result": info, "node_trace": t, "error": None}
        except ExtractionError as e:
            logger.warning("[%s] %s", route, e)
            return {"error": str(e), "node_trace": t, "result": None}
        except Exception as e:  # noqa: BLE001
            logger.exception("[%s] 提取异常", route)
            return {"error": f"提取失败: {e}", "node_trace": t, "result": None}

    node.__name__ = f"node_extract_{route}"
    return node


def node_sink_unsupported(state: VideoExtractGraphState) -> dict[str, Any]:
    u = state.get("url", "")
    names = ", ".join(c.__name__.replace("Extractor", "") for c in EXTRACTOR_CLASSES)
    msg = f"不支持的视频 URL: {u}\n当前支持的平台: {names}"
    return {
        "error": msg,
        "node_trace": _trace(state, "sink_unsupported"),
        "result": None,
    }


def _build_compiled_graph() -> Any:
    routes = get_extractor_routes()
    g = StateGraph(VideoExtractGraphState)
    g.add_node("classify", node_classify)
    for route, cls in routes:
        g.add_node(f"extract_{route}", _make_extract_node(cls, route))
    g.add_node("sink_unsupported", node_sink_unsupported)

    path_map: dict[str, str] = {route: f"extract_{route}" for route, _ in routes}
    path_map["unknown"] = "sink_unsupported"

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route_after_classify, path_map)
    for route, _ in routes:
        g.add_edge(f"extract_{route}", END)
    g.add_edge("sink_unsupported", END)
    return g.compile()


@lru_cache(maxsize=1)
def _compiled_graph() -> Any:
    return _build_compiled_graph()


def clear_video_extract_graph_cache() -> None:
    """图结构或注册表变更时清空编译缓存（测试或热加载）。"""
    _compiled_graph.cache_clear()


def extract_info_via_graph(url: str) -> VideoInfo:
    """
    经 LangGraph 路由后仅调用一个平台提取器；失败则抛出 ExtractionError。
    """
    out = _compiled_graph().invoke({"url": url.strip(), "node_trace": []})
    err = out.get("error")
    if err:
        raise ExtractionError(str(err))
    res = out.get("result")
    if not isinstance(res, VideoInfo):
        raise ExtractionError("提取未返回有效的 VideoInfo")
    return res
