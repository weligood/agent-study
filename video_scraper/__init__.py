"""
video_scraper - 视频信息提取与下载模块。

参考 yt-dlp 的 Extractor 插件架构设计：
- 每个平台一个 Extractor 子类
- 统一的 extract_info() 入口自动匹配合适的提取器
- 标准化的 VideoInfo 输出格式
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from video_scraper.base import BaseExtractor, ExtractionError
from video_scraper.bilibili import BilibiliExtractor
from video_scraper.iqiyi import IqiyiExtractor
from video_scraper.tencent import TencentExtractor
from video_scraper.youku import YoukuExtractor
from video_scraper.models import DownloadResult, VideoFormat, VideoInfo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 提取器注册表：扩展新平台时在此列表添加
# ---------------------------------------------------------------------------
_EXTRACTORS: list[type[BaseExtractor]] = [
    YoukuExtractor,
    BilibiliExtractor,
    TencentExtractor,
    IqiyiExtractor,
    # 未来扩展：MangoTV, ...
]

# 提取器单例缓存
_extractor_instances: dict[str, BaseExtractor] = {}


def _get_extractor(cls: type[BaseExtractor]) -> BaseExtractor:
    """获取提取器单例。"""
    name = cls.__name__
    if name not in _extractor_instances:
        _extractor_instances[name] = cls()
    return _extractor_instances[name]


def extract_info(url: str) -> VideoInfo:
    """
    从视频 URL 提取元数据。

    自动遍历注册的提取器，找到第一个匹配的执行提取。

    :param url: 视频页面 URL
    :return: 标准化的 VideoInfo
    :raises ExtractionError: 无匹配提取器或提取失败
    """
    url = url.strip()
    for extractor_cls in _EXTRACTORS:
        if extractor_cls.suitable(url):
            extractor = _get_extractor(extractor_cls)
            return extractor.extract(url)

    raise ExtractionError(
        f"不支持的视频 URL: {url}\n"
        f"当前支持的平台: {', '.join(e.__name__.replace('Extractor', '') for e in _EXTRACTORS)}"
    )


def get_supported_platforms() -> list[str]:
    """返回当前支持的平台列表。"""
    return [e.__name__.replace("Extractor", "") for e in _EXTRACTORS]


__all__ = [
    "BaseExtractor",
    "ExtractionError",
    "VideoInfo",
    "VideoFormat",
    "DownloadResult",
    "extract_info",
    "get_supported_platforms",
]
