"""
工具包入口：对外保持稳定的 import 路径。

- **internal**：图节点 / pipeline 直连的内部检索函数（无 @tool）
- **agent_tools**：注册给 LangChain 的 @tool 与 `get_tv_legal_tools`
"""

from __future__ import annotations

from tv_agent.tools.agent_tools.legal_tools import (
    fetch_availability,
    fetch_similar_titles,
    get_tv_legal_tools,
    recommend_similar_tv,
    resolve_title,
    search_by_actor,
    search_streaming_platforms,
    search_titles,
    search_tv_metadata,
    web_search_tv_info,
)
from tv_agent.tools.agent_tools.video_tools import (
    confirm_download,
    download_video,
    extract_video_info,
    extract_video_page,
    prepare_download,
)
from tv_agent.tools.internal.web_search import (
    _search_api_query,
    _search_by_actor_web,
    _search_metadata,
    _search_platforms,
    _search_similar_web,
    search_api_query,
    search_by_actor_web,
    search_metadata,
    search_platforms,
    search_similar_web,
)

__all__ = [
    "_search_api_query",
    "_search_by_actor_web",
    "_search_metadata",
    "_search_platforms",
    "_search_similar_web",
    "confirm_download",
    "download_video",
    "extract_video_info",
    "extract_video_page",
    "fetch_availability",
    "fetch_similar_titles",
    "get_tv_legal_tools",
    "prepare_download",
    "recommend_similar_tv",
    "resolve_title",
    "search_api_query",
    "search_by_actor",
    "search_by_actor_web",
    "search_metadata",
    "search_platforms",
    "search_similar_web",
    "search_streaming_platforms",
    "search_titles",
    "search_tv_metadata",
    "web_search_tv_info",
]
