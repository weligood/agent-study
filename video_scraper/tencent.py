"""
腾讯视频 (Tencent Video / v.qq.com) 视频提取器。

参考项目：
- yt-dlp/yt-dlp: yt_dlp/extractor/tencent.py（VQQVideoIE, CKey 签名, API 调用）

支持的 URL 格式：
- https://v.qq.com/x/page/{vid}.html            （单视频页）
- https://v.qq.com/x/cover/{cid}/{vid}.html      （剧集页）

核心 API：
- 元数据：从网页 window.__pinia 提取
- 流地址：https://h5vv6.video.qq.com/getvinfo（需 CKey 签名）
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import string
import time
import urllib.parse
import urllib.request
from typing import Any

from video_scraper.base import BaseExtractor, ExtractionError, _SSL_CTX
from video_scraper.models import VideoFormat, VideoInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 腾讯视频清晰度映射
# ---------------------------------------------------------------------------
_QUALITY_MAP: dict[str, tuple[str, int, int, int]] = {
    # name: (标签, 宽度, 高度, 排序)
    "ld": ("270P 流畅", 480, 270, 10),
    "sd": ("480P 标清", 854, 480, 20),
    "hd": ("720P 高清", 1280, 720, 40),
    "shd": ("1080P 全高清", 1920, 1080, 60),
    "fhd": ("1080P60 臻彩", 1920, 1080, 70),
    "2k": ("2K 超清", 2560, 1440, 80),
    "4k": ("4K 超清", 3840, 2160, 90),
}

_TENCENT_HEADERS = {
    "Referer": "https://v.qq.com",
    "Origin": "https://v.qq.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _generate_guid() -> str:
    """生成 16 位随机 GUID（参考 yt-dlp）。"""
    return "".join(random.choices(string.digits + string.ascii_lowercase, k=16))


class TencentExtractor(BaseExtractor):
    """腾讯视频提取器。"""

    _VALID_URL = (
        r"https?://v\.qq\.com/x/"
        r"(?:page/(?P<id>\w+)"
        r"|cover/(?P<series_id>\w+)/(?P<vid>\w+))"
        r"\.html"
        r"(?:\?.*)?"
    )

    def _real_extract(self, url: str) -> VideoInfo:
        """从腾讯视频 URL 提取视频信息。"""
        m = re.match(self._VALID_URL, url)
        if not m:
            raise ExtractionError(f"无法解析腾讯视频 URL: {url}")

        video_id = m.group("id") or m.group("vid")
        series_id = m.group("series_id") or ""

        # Step 1: 下载网页，提取元数据
        webpage = self._request_text(url, headers=_TENCENT_HEADERS)
        metadata = self._parse_webpage_metadata(webpage, video_id)

        # Step 2: 尝试通过 API 获取视频流
        formats = self._get_formats(video_id, series_id, url)

        # Step 3: 构建 VideoInfo
        title = metadata.get("title", "未知标题")

        return VideoInfo(
            id=video_id,
            title=title,
            url=url,
            platform="tencent",
            duration=metadata.get("duration"),
            thumbnail=metadata.get("thumbnail"),
            uploader=metadata.get("uploader"),
            uploader_id="",
            description=metadata.get("description"),
            view_count=None,
            like_count=None,
            upload_date=None,
            formats=formats,
            extra={
                "series_id": series_id,
                "series_title": metadata.get("series_title"),
            },
        )

    def _parse_webpage_metadata(self, webpage: str, video_id: str) -> dict[str, Any]:
        """从网页中解析视频元数据。"""
        metadata: dict[str, Any] = {}

        # 方法 1: 从 __pinia 数据中提取（参考 yt-dlp VQQBaseIE）
        pinia_match = re.search(
            r"window\.__(?:pinia|PINIA__)\s*=\s*(\{.+?\})\s*(?:</script>|;)",
            webpage,
            re.DOTALL,
        )
        if pinia_match:
            try:
                pinia_data = json.loads(pinia_match.group(1))
                video_info = (
                    pinia_data.get("global", {}).get("videoInfo", {})
                    or pinia_data.get("videoInfo", {})
                )
                cover_info = (
                    pinia_data.get("global", {}).get("coverInfo", {})
                    or pinia_data.get("coverInfo", {})
                )

                metadata["title"] = video_info.get("title", "")
                metadata["description"] = video_info.get("desc", "")
                metadata["thumbnail"] = video_info.get("pic160x90", "")
                metadata["series_title"] = cover_info.get("title", "")
                metadata["duration"] = video_info.get("duration")

                if metadata.get("title"):
                    return metadata
            except (json.JSONDecodeError, AttributeError):
                logger.debug("解析 __pinia 数据失败")

        # 方法 2: 从 og meta 标签提取
        og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', webpage)
        og_desc = re.search(r'<meta\s+property="og:description"\s+content="([^"]*)"', webpage)
        og_image = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', webpage)

        if og_title:
            title = og_title.group(1)
            # 清理标题（参考 yt-dlp _get_clean_title）
            title = re.sub(
                r"\s*[_\-]\s*(?:Watch online|Watch HD Video Online|WeTV|腾讯视频|"
                r"(?:高清)?1080P在线观看平台).*?$",
                "", title,
            ).strip()
            metadata["title"] = title

        if og_desc:
            metadata["description"] = og_desc.group(1)
        if og_image:
            metadata["thumbnail"] = og_image.group(1)

        # 从 <title> 标签提取
        if not metadata.get("title"):
            title_match = re.search(r"<title>(.+?)</title>", webpage)
            if title_match:
                title = re.sub(r"\s*[-_].*腾讯视频.*$", "", title_match.group(1)).strip()
                metadata["title"] = title

        return metadata

    def _get_formats(self, video_id: str, series_id: str, url: str) -> list[VideoFormat]:
        """
        通过腾讯视频 API 获取视频流。

        参考 yt-dlp TencentBaseIE._get_video_api_response。
        注意：完整的 CKey 生成需要 AES 加密，此处使用简化版本尝试获取流信息。
        如果 CKey 验证失败，返回空列表但仍保留元数据。
        """
        guid = _generate_guid()
        ts = str(int(time.time()))

        # 简化版 CKey（不含 AES 加密，部分免费视频可用）
        raw = f"{video_id}|{ts}|mg3c3b04ba|3.5.57|{guid}|10901|{url[:48]}|mozilla|"
        ckey_hash = hashlib.md5(raw.encode()).hexdigest().upper()

        params = {
            "vid": video_id,
            "cid": series_id or video_id,
            "cKey": ckey_hash,
            "encryptVer": "8.1",
            "sphls": "2",
            "dtype": "3",
            "defn": "shd",
            "spsrt": "2",
            "sphttps": "1",
            "otype": "json",
            "spwm": "1",
            "hevclv": "28",
            "host": "v.qq.com",
            "referer": "v.qq.com",
            "ehost": url,
            "appVer": "3.5.57",
            "platform": "10901",
            "guid": guid,
            "flowid": "".join(random.choices(string.digits + string.ascii_lowercase, k=32)),
        }

        query_str = urllib.parse.urlencode(params)
        api_url = f"https://h5vv6.video.qq.com/getvinfo?{query_str}"

        try:
            text = self._request_text(api_url, headers=_TENCENT_HEADERS, timeout=15)
            # 响应格式: QZOutputJson={...};
            json_match = re.search(r"QZOutputJson\s*=\s*(\{.+\})\s*;?", text, re.DOTALL)
            if not json_match:
                logger.warning("腾讯视频 API 响应格式异常")
                return []

            data = json.loads(json_match.group(1))
        except Exception as e:
            logger.warning("腾讯视频 API 请求失败: %s", e)
            return []

        # 检查 API 错误
        msg = data.get("msg")
        if data.get("code") != "0.0" and msg:
            logger.warning("腾讯视频 API 错误: %s", msg)
            return []

        # 解析流信息
        return self._parse_api_formats(data)

    def _parse_api_formats(self, data: dict[str, Any]) -> list[VideoFormat]:
        """解析腾讯视频 API 返回的流信息。"""
        formats: list[VideoFormat] = []

        try:
            video_list = data.get("vl", {}).get("vi", [])
            if not video_list:
                return []

            video_info = video_list[0]
            format_list = data.get("fl", {}).get("fi", [])

            for ui in video_info.get("ul", {}).get("ui", []):
                stream_url = ui.get("url", "")
                hls_info = ui.get("hls", {})

                if hls_info or stream_url.endswith(".m3u8") or ".m3u8" in stream_url:
                    # M3U8 流
                    full_url = stream_url + hls_info.get("pt", "")
                    if full_url:
                        # 尝试匹配清晰度
                        br = video_info.get("br")
                        matched_format = None
                        for fi in format_list:
                            if fi.get("br") == br:
                                matched_format = fi
                                break

                        name = (matched_format or {}).get("name", "hd")
                        quality_info = _QUALITY_MAP.get(name, ("未知", 0, 0, 0))

                        formats.append(VideoFormat(
                            url=full_url,
                            ext="mp4",
                            quality=quality_info[0],
                            quality_number=quality_info[3],
                            width=video_info.get("vw") or quality_info[1],
                            height=video_info.get("vh") or quality_info[2],
                            filesize=None,
                            format_note=f"M3U8 stream, format={name}",
                        ))
                else:
                    # 直链
                    fn = video_info.get("fn", "")
                    fvkey = video_info.get("fvkey", "")
                    if stream_url and fn and fvkey:
                        full_url = f"{stream_url}{fn}?vkey={fvkey}"
                        formats.append(VideoFormat(
                            url=full_url,
                            ext="mp4",
                            quality="720P 高清",
                            quality_number=40,
                            width=video_info.get("vw", 0),
                            height=video_info.get("vh", 0),
                            filesize=None,
                            format_note="Direct download",
                        ))
        except Exception as e:
            logger.warning("解析腾讯视频流信息失败: %s", e)

        return formats
