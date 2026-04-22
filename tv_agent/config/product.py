"""产品级默认行为（查询模式、下载门）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config import Settings, get_settings


@dataclass(frozen=True)
class ProductConfigView:
    tv_query_mode: Literal["pipeline", "agent"]
    tv_download_enabled: bool

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ProductConfigView:
        s = settings or get_settings()
        return cls(tv_query_mode=s.tv_query_mode, tv_download_enabled=bool(s.tv_download_enabled))
