"""静态半结构化知识底座（平台目录、地区码、别名等），与 search / resolution 解耦。"""

from tv_agent.resources.genre_catalog import COMMON_TV_GENRES
from tv_agent.resources.provider_catalog import (
    PLATFORM_KEYWORDS,
    PLATFORM_LOGOS_MAP,
    build_search_url,
)
from tv_agent.resources.region_catalog import ISO_REGION_HINTS
from tv_agent.resources.title_aliases import normalize_series_alias

__all__ = [
    "COMMON_TV_GENRES",
    "ISO_REGION_HINTS",
    "PLATFORM_KEYWORDS",
    "PLATFORM_LOGOS_MAP",
    "build_search_url",
    "normalize_series_alias",
]
