"""
向后兼容：Agent / 工具仍可使用 `from config import get_settings`。

实际定义见 `app.core.config`（pydantic-settings）。
"""

from __future__ import annotations

from app.core.config import ROOT_DIR, Settings, clear_settings_cache, get_settings

__all__ = ["ROOT_DIR", "Settings", "get_settings", "clear_settings_cache"]
