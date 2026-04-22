"""搜索源与片库融合相关视图。"""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings, get_settings


@dataclass(frozen=True)
class SearchConfigView:
    searxng_base_url: str | None
    search_fallback_ddg: bool
    meilisearch_url: str | None
    meilisearch_index: str

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> SearchConfigView:
        s = settings or get_settings()
        return cls(
            searxng_base_url=s.searxng_base_url,
            search_fallback_ddg=bool(s.search_fallback_ddg),
            meilisearch_url=s.meilisearch_url,
            meilisearch_index=s.meilisearch_index,
        )
