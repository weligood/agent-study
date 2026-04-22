"""
video_scraper - 视频信息提取与下载模块。

参考 yt-dlp 的 Extractor 插件架构设计：
- 每个平台一个 Extractor 子类
- 统一入口 `extract_info()` 经 LangGraph 按 URL 路由到单一平台节点再提取
- 标准化的 VideoInfo 输出格式
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from video_scraper.base import BaseExtractor, ExtractionError
from video_scraper.extract_graph import extract_info_via_graph
from video_scraper.models import DownloadResult, VideoFormat, VideoInfo
from video_scraper.registry import EXTRACTOR_CLASSES, get_extractor, get_extractor_routes

if TYPE_CHECKING:
    pass

# 向后兼容：历史代码可能引用 `_EXTRACTORS`
_EXTRACTORS = EXTRACTOR_CLASSES


def _get_extractor(cls: type[BaseExtractor]) -> BaseExtractor:
    """向后兼容别名，等价于 `registry.get_extractor`。"""
    return get_extractor(cls)


def extract_info(url: str) -> VideoInfo:
    """
    从视频 URL 提取元数据。

    经 LangGraph 分类后**仅执行匹配到的那一个**平台提取器，不遍历尝试全部平台。

    :param url: 视频页面 URL
    :return: 标准化的 VideoInfo
    :raises ExtractionError: 无匹配提取器或提取失败
    """
    return extract_info_via_graph(url)


def get_supported_platforms() -> list[str]:
    """返回当前支持的平台列表。"""
    return [e.__name__.replace("Extractor", "") for e in EXTRACTOR_CLASSES]


__all__ = [
    "BaseExtractor",
    "ExtractionError",
    "VideoInfo",
    "VideoFormat",
    "DownloadResult",
    "extract_info",
    "get_supported_platforms",
    "EXTRACTOR_CLASSES",
    "get_extractor",
    "get_extractor_routes",
]
