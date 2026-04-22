"""注册给 LangChain Agent 的 @tool 能力（严格 schema / 文档串 / 策略边界）。"""

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

__all__ = [
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
    "search_by_actor",
    "search_streaming_platforms",
    "search_titles",
    "search_tv_metadata",
    "web_search_tv_info",
]
