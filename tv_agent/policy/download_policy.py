"""下载相关策略门与人机确认语义（集中配置，避免散落在 video tool）。"""

from __future__ import annotations

from config import Settings, get_settings


def is_download_enabled(settings: Settings | None = None) -> bool:
    return bool((settings or get_settings()).tv_download_enabled)


def download_policy_message() -> str:
    """未开放下载时的统一说明文案。"""
    return "策略门：当前未开放下载（需配置 TV_DOWNLOAD_ENABLED=true）。"


def prepare_requires_user_confirm() -> bool:
    """prepare_download 路径一律要求显式 confirm（人机协同）。"""
    return True
