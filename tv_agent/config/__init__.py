"""
从全局 `Settings` 投影出的分层配置视图（不在此处重复 env 字段定义）。

单一事实来源仍为 `app.core.config.Settings`；本包仅做逻辑分组，便于按主题阅读与测试打桩。
"""

from __future__ import annotations

from tv_agent.config.feature_flags import FeatureFlagsView
from tv_agent.config.llm import LLMConfigView
from tv_agent.config.product import ProductConfigView
from tv_agent.config.runtime import RuntimeConfigView
from tv_agent.config.search import SearchConfigView

__all__ = [
    "FeatureFlagsView",
    "LLMConfigView",
    "ProductConfigView",
    "RuntimeConfigView",
    "SearchConfigView",
    "layered_config",
]


def layered_config() -> dict[str, object]:
    """返回当前进程的一组只读视图（字典便于 JSON 调试）。"""
    return {
        "runtime": RuntimeConfigView.from_settings(),
        "llm": LLMConfigView.from_settings(),
        "search": SearchConfigView.from_settings(),
        "product": ProductConfigView.from_settings(),
        "feature_flags": FeatureFlagsView.from_settings(),
    }
