"""
提取器注册表与单例工厂。

供 `video_scraper` 包与 `extract_graph` 共用，避免循环导入。
"""

from __future__ import annotations

from video_scraper.base import BaseExtractor
from video_scraper.bilibili import BilibiliExtractor
from video_scraper.iqiyi import IqiyiExtractor
from video_scraper.tencent import TencentExtractor
from video_scraper.youku import YoukuExtractor

# 顺序与 LangGraph 分类优先级一致：先匹配的先路由（仅一条 URL 会命中一个分支）
EXTRACTOR_CLASSES: list[type[BaseExtractor]] = [
    YoukuExtractor,
    BilibiliExtractor,
    TencentExtractor,
    IqiyiExtractor,
]

_extractor_instances: dict[str, BaseExtractor] = {}


def route_key(cls: type[BaseExtractor]) -> str:
    """图节点名用的小写路由键，如 youku、bilibili。"""
    return cls.__name__.replace("Extractor", "").lower()


def get_extractor_routes() -> list[tuple[str, type[BaseExtractor]]]:
    """[(route_key, cls), ...] 与 EXTRACTOR_CLASSES 顺序一致。"""
    return [(route_key(c), c) for c in EXTRACTOR_CLASSES]


def get_extractor(cls: type[BaseExtractor]) -> BaseExtractor:
    """获取提取器单例。"""
    name = cls.__name__
    if name not in _extractor_instances:
        _extractor_instances[name] = cls()
    return _extractor_instances[name]
