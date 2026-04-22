"""
优酷 (Youku) 视频提取器。

参考项目：
- yt-dlp/yt-dlp: yt_dlp/extractor/youku.py（核心 API 与 CNA 获取逻辑）

支持的 URL 格式：
- https://v.youku.com/v_show/id_XXXXXXXXXXXX.html
- https://player.youku.com/player.php/sid/XXXXXXXXXXXX/v.swf
- https://play.youku.com/v_show/id_XXXXXXXXXXXX.html
- https://play.tudou.com/v_show/id_XXXXXXXXXXXX.html
"""

from __future__ import annotations

import json
import logging
import random
import re
import string
import time
import urllib.parse
from typing import Any

from video_scraper.base import BaseExtractor, ExtractionError, _SSL_CTX
from video_scraper.models import VideoFormat, VideoInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 优酷清晰度映射（stream_type -> 标签/分辨率）
# ---------------------------------------------------------------------------
_QUALITY_MAP: dict[str, tuple[str, int, int, int]] = {
    # stream_type: (标签, 宽度, 高度, 排序数值)
    "3gp": ("240P 极速", 426, 240, 10),
    "3gphd": ("360P 流畅", 640, 360, 20),
    "flv": ("480P 标清", 854, 480, 30),
    "flvhd": ("480P 标清", 854, 480, 30),
    "mp4": ("480P 标清", 854, 480, 30),
    "mp4hd": ("720P 高清", 1280, 720, 50),
    "mp4hd2": ("1080P 全高清", 1920, 1080, 70),
    "mp4hd3": ("2K 超清", 2560, 1440, 80),
    "hd2": ("1080P60 高帧率", 1920, 1080, 75),
    "hd3": ("4K 超清", 3840, 2160, 90),
}

# 请求头
_YOUKU_HEADERS = {
    "Referer": "https://v.youku.com",
    "Origin": "https://v.youku.com",
}


def _generate_ysuid() -> str:
    """生成 __ysuid cookie 值（参考 yt-dlp）：时间戳 + 3位随机字母。"""
    return f"{int(time.time())}{''.join(random.choices(string.ascii_letters, k=3))}"


class YoukuExtractor(BaseExtractor):
    """优酷视频提取器。"""

    _VALID_URL = (
        r"https?://(?:v|play(?:er)?)\."
        r"(?:youku|tudou)\.com/"
        r"(?:v_show/id_|player\.php/sid/)"
        r"(?P<id>[A-Za-z0-9=]+)"
        r"(?:\.html|/v\.swf|)"
        r"(?:\?.*)?"
    )

    def _real_extract(self, url: str) -> VideoInfo:
        """从优酷视频 URL 提取视频信息。"""
        # 提取视频 ID
        m = re.match(self._VALID_URL, url)
        if not m:
            raise ExtractionError(f"无法解析优酷 URL: {url}")
        video_id = m.group("id")
        # 去掉尾部的 ==
        video_id = video_id.rstrip("=")

        # Step 1: 获取 CNA (utid) — 通过 mmstat.com
        cna = self._get_cna()
        logger.debug("获取到 CNA: %s", cna)

        # Step 2: 调用优酷 ups API 获取视频数据
        video_data, streams = self._get_ups_data(video_id, cna, url)

        # Step 3: 解析视频格式列表
        formats = self._parse_formats(streams)

        # Step 4: 构建 VideoInfo
        title = video_data.get("title", "未知标题")
        seconds = video_data.get("seconds")
        duration = int(seconds) if seconds else None

        return VideoInfo(
            id=video_id,
            title=title,
            url=f"https://v.youku.com/v_show/id_{video_id}.html",
            platform="youku",
            duration=duration,
            thumbnail=video_data.get("logo"),
            uploader=video_data.get("username"),
            uploader_id=str(video_data.get("userid", "")),
            description=video_data.get("desc"),
            view_count=None,  # ups API 不直接返回播放量
            like_count=None,
            upload_date=None,
            formats=formats,
            extra={
                "tags": video_data.get("tags", []),
                "category": video_data.get("category"),
            },
        )

    def _get_cna(self) -> str:
        """
        获取 CNA (utid) token。

        参考 yt-dlp: 请求 log.mmstat.com/eg.js，从响应的 ETag 头提取 CNA。
        若失败则生成一个随机值。
        """
        import urllib.request

        try:
            req = urllib.request.Request(
                "https://log.mmstat.com/eg.js",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                etag = resp.headers.get("ETag", "")
                # ETag 格式: '"xxxxxxxxxxxx"'，去掉引号
                cna = etag.strip('"').strip("'")
                if cna:
                    return cna
        except Exception as e:
            logger.warning("获取 CNA 失败，使用随机值: %s", e)

        # 降级：生成随机 CNA
        return _generate_ysuid()

    def _get_ups_data(
        self, video_id: str, cna: str, referer: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        调用优酷 ups/get.json API 获取视频元数据和流地址。

        参考 yt-dlp YoukuIE._real_extract。
        """
        params = urllib.parse.urlencode({
            "vid": video_id,
            "ccode": "0564",
            "client_ip": "192.168.1.1",
            "utid": cna,
            "client_ts": str(time.time() / 1000),
        })
        api_url = f"https://ups.youku.com/ups/get.json?{params}"

        headers = {
            **_YOUKU_HEADERS,
            "Referer": referer,
            "Cookie": f"__ysuid={_generate_ysuid()}; xreferrer=https://www.youku.com; cna={cna}",
        }

        data = self._request_json(api_url, headers=headers)

        # 检查 API 返回
        api_data = data.get("data", {})

        error = api_data.get("error")
        if error:
            code = error.get("code", -1)
            note = error.get("note", "未知错误")
            if "版权" in note:
                raise ExtractionError(f"优酷提示: 该视频因版权原因无法观看 (code={code})")
            elif "私密" in note:
                raise ExtractionError(f"优酷提示: 该视频为私密视频 (code={code})")
            else:
                raise ExtractionError(f"优酷 API 错误 (code={code}): {note}")

        video_data = api_data.get("video", {})
        if not video_data:
            raise ExtractionError("优酷 API 未返回视频数据")

        streams = api_data.get("stream", [])

        return video_data, streams

    def _parse_formats(self, streams: list[dict[str, Any]]) -> list[VideoFormat]:
        """解析优酷流数据为标准 VideoFormat 列表。"""
        formats: list[VideoFormat] = []

        for stream in streams:
            # 跳过片尾广告流
            if stream.get("channel_type") == "tail":
                continue

            stream_type = stream.get("stream_type", "")
            m3u8_url = stream.get("m3u8_url", "")

            if not m3u8_url:
                continue

            quality_info = _QUALITY_MAP.get(
                stream_type, ("未知", 0, 0, 0)
            )

            formats.append(VideoFormat(
                url=m3u8_url,
                ext="mp4",
                quality=quality_info[0],
                quality_number=quality_info[3],
                width=stream.get("width") or quality_info[1],
                height=stream.get("height") or quality_info[2],
                filesize=stream.get("size"),
                format_note=f"M3U8 stream, type={stream_type}",
            ))

        return formats
