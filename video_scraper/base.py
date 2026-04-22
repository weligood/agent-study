"""
提取器基类：定义所有视频提取器的公共接口。

参考 yt-dlp InfoExtractor 的设计模式：
- _VALID_URL: 正则表达式，匹配此提取器支持的 URL
- _real_extract(): 子类实现的核心提取逻辑
- extract(): 公共入口，包含统一的错误处理
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from video_scraper.models import VideoInfo

logger = logging.getLogger(__name__)

# 通用浏览器 User-Agent
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 创建不验证 SSL 的上下文（企业网络中常因代理导致 SSL 错误）
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class ExtractionError(Exception):
    """提取失败时抛出。"""


class BaseExtractor(ABC):
    """
    视频提取器基类。

    子类需要：
    1. 设置 _VALID_URL 类属性（正则表达式）
    2. 实现 _real_extract(url) 方法
    """

    _VALID_URL: str = ""

    def __init__(self) -> None:
        self._compiled_url: re.Pattern[str] | None = None

    @property
    def compiled_url(self) -> re.Pattern[str]:
        """编译并缓存 _VALID_URL 正则。"""
        if self._compiled_url is None:
            self._compiled_url = re.compile(self._VALID_URL)
        return self._compiled_url

    @classmethod
    def suitable(cls, url: str) -> bool:
        """判断 URL 是否与此提取器匹配。"""
        return bool(re.match(cls._VALID_URL, url))

    def extract(self, url: str) -> VideoInfo:
        """
        公共提取入口：URL 校验 + 错误处理 + 调用子类实现。

        :param url: 视频页面 URL
        :return: 标准化的 VideoInfo
        :raises ExtractionError: 提取失败时
        """
        if not self.suitable(url):
            raise ExtractionError(f"URL 不匹配此提取器: {url}")

        logger.info("[%s] 开始提取: %s", self.__class__.__name__, url)
        try:
            info = self._real_extract(url)
            logger.info(
                "[%s] 提取成功: %s (%d 个格式)",
                self.__class__.__name__,
                info.title,
                len(info.formats),
            )
            return info
        except ExtractionError:
            raise
        except Exception as e:
            logger.exception("[%s] 提取失败: %s", self.__class__.__name__, e)
            raise ExtractionError(f"提取失败: {e}") from e

    @abstractmethod
    def _real_extract(self, url: str) -> VideoInfo:
        """
        子类实现：从 URL 提取视频信息。

        :param url: 视频页面 URL
        :return: VideoInfo 实例
        """
        ...

    # ------------------------------------------------------------------
    # 工具方法：供子类使用
    # ------------------------------------------------------------------

    @staticmethod
    def _request_json(
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 15,
    ) -> dict[str, Any]:
        """
        发起 GET 请求并解析为 JSON dict。

        :raises ExtractionError: 请求失败或解析失败时
        """
        hdrs = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            hdrs.update(headers)

        req = urllib.request.Request(url, headers=hdrs, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            raise ExtractionError(f"HTTP 请求失败 ({url}): {e}") from e

    @staticmethod
    def _request_text(
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 15,
    ) -> str:
        """发起 GET 请求，返回响应文本。"""
        hdrs = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            hdrs.update(headers)

        req = urllib.request.Request(url, headers=hdrs, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ExtractionError(f"HTTP 请求失败 ({url}): {e}") from e

    @staticmethod
    def _match_id(pattern: str, url: str, group: str = "id") -> str:
        """从 URL 中用正则提取 ID。"""
        m = re.match(pattern, url)
        if not m:
            raise ExtractionError(f"无法从 URL 中提取 ID: {url}")
        try:
            return m.group(group)
        except IndexError:
            return m.group(1)
