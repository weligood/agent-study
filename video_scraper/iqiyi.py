"""
爱奇艺 (iQiyi) 视频提取器。

参考项目：
- yt-dlp/yt-dlp: yt_dlp/extractor/iqiyi.py（IqiyiIE, MD5 签名, tmts API）

支持的 URL 格式：
- https://www.iqiyi.com/v_{id}.html      （视频页）
- https://www.iqiyi.com/w_{id}.html      （视频页）
- https://www.iqiyi.com/a_{id}.html      （专辑页 - 取第一集）

核心 API：
- 元数据：从网页 HTML 提取 tvid / video_id
- 流地址：http://cache.m.iqiyi.com/jp/tmts/{tvid}/{video_id}/（MD5 签名）
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.parse
from typing import Any

from video_scraper.base import BaseExtractor, ExtractionError, _SSL_CTX
from video_scraper.models import VideoFormat, VideoInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 爱奇艺清晰度映射（vd -> 标签/分辨率）
# 参考 yt-dlp IqiyiIE._FORMATS_MAP
# ---------------------------------------------------------------------------
_QUALITY_MAP: dict[int, tuple[str, int, int, int]] = {
    # vd: (标签, 宽度, 高度, 排序)
    96: ("216P 极速", 384, 216, 5),
    1: ("360P 流畅", 640, 360, 10),
    2: ("480P 标清", 854, 480, 20),
    21: ("504P 标清", 896, 504, 25),
    4: ("720P 高清", 1280, 720, 40),
    17: ("720P 高清", 1280, 720, 40),
    5: ("1080P 全高清", 1920, 1080, 60),
    18: ("1080P 高帧率", 1920, 1080, 70),
}

_IQIYI_HEADERS = {
    "Referer": "https://www.iqiyi.com",
    "Origin": "https://www.iqiyi.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# 签名密钥（参考 yt-dlp）
_SIGN_KEY = "d5fb4bd9d50c4be6948c97edd7254b0e"
_SRC = "76f90cbd92f94a2e925d83e8ccd22cb7"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class IqiyiExtractor(BaseExtractor):
    """爱奇艺视频提取器。"""

    _VALID_URL = (
        r"https?://(?:(?:[^.]+\.)?iqiyi\.com|www\.pps\.tv)"
        r"/(?P<type>[vwa])_(?P<id>\w+)\.html"
        r"(?:\?.*)?"
    )

    def _real_extract(self, url: str) -> VideoInfo:
        """从爱奇艺 URL 提取视频信息。"""
        m = re.match(self._VALID_URL, url)
        if not m:
            raise ExtractionError(f"无法解析爱奇艺 URL: {url}")

        page_type = m.group("type")
        page_id = m.group("id")

        # Step 1: 下载网页
        webpage = self._request_text(url, headers=_IQIYI_HEADERS)

        # Step 2: 提取 tvid 和 video_id
        tvid = self._extract_field(
            webpage,
            [
                r'data-(?:player|shareplattrigger)-tvid\s*=\s*[\'"](\d+)',
                r'"tvId"\s*:\s*(\d+)',
                r'tvid\s*[:=]\s*[\'"]?(\d+)',
                r'param\[\'tvid\'\]\s*=\s*"(\d+)"',
            ],
            "tvid",
        )

        video_id = self._extract_field(
            webpage,
            [
                r'data-(?:player|shareplattrigger)-videoid\s*=\s*[\'"]([a-f\d]+)',
                r'"vid"\s*:\s*"([a-f\d]+)"',
                r'vid\s*[:=]\s*[\'"]?([a-f\d]+)',
                r'param\[\'vid\'\]\s*=\s*"([a-f\d]+)"',
            ],
            "video_id",
        )

        # Step 3: 提取网页中的元数据
        title = self._extract_title(webpage)
        description = self._extract_description(webpage)
        thumbnail = self._extract_thumbnail(webpage)

        # Step 4: 获取视频流
        formats = self._get_formats(tvid, video_id)

        return VideoInfo(
            id=video_id,
            title=title,
            url=url,
            platform="iqiyi",
            duration=None,
            thumbnail=thumbnail,
            uploader=None,
            uploader_id="",
            description=description,
            view_count=None,
            like_count=None,
            upload_date=None,
            formats=formats,
            extra={
                "tvid": tvid,
                "page_type": page_type,
            },
        )

    @staticmethod
    def _extract_field(webpage: str, patterns: list[str], field_name: str) -> str:
        """从网页中依次尝试多个正则提取字段。"""
        for pattern in patterns:
            m = re.search(pattern, webpage)
            if m:
                return m.group(1)
        raise ExtractionError(f"无法从网页中提取 {field_name}")

    @staticmethod
    def _extract_title(webpage: str) -> str:
        """提取视频标题。"""
        # 优先从特定元素提取
        for pattern in [
            r'id="widget-videotitle"[^>]*>([^<]+)',
            r'class="mod-play-tit"[^>]*>([^<]+)',
            r'data-videochanged-title="word"[^>]*>([^<]+)',
            r'<meta\s+property="og:title"\s+content="([^"]*)"',
            r"<title>(.+?)</title>",
        ]:
            m = re.search(pattern, webpage)
            if m:
                title = m.group(1).strip()
                # 清理标题后缀
                title = re.sub(r"\s*[-_|].*(?:爱奇艺|iQIYI|iqiyi).*$", "", title).strip()
                if title:
                    return title
        return "未知标题"

    @staticmethod
    def _extract_description(webpage: str) -> str | None:
        m = re.search(r'<meta\s+(?:property="og:description"|name="description")\s+content="([^"]*)"', webpage)
        return m.group(1) if m else None

    @staticmethod
    def _extract_thumbnail(webpage: str) -> str | None:
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', webpage)
        return m.group(1) if m else None

    def _get_formats(self, tvid: str, video_id: str) -> list[VideoFormat]:
        """
        通过 tmts API 获取视频流地址。

        参考 yt-dlp IqiyiIE.get_raw_data。
        """
        formats: list[VideoFormat] = []

        for attempt in range(3):
            try:
                data = self._call_tmts_api(tvid, video_id)
            except ExtractionError:
                if attempt < 2:
                    logger.debug("第 %d 次尝试失败，重试中...", attempt + 1)
                    import time as _time
                    _time.sleep(2)
                    continue
                break

            code = data.get("code", "")
            if code == "A00111":
                logger.warning("爱奇艺: 该视频仅限中国大陆地区观看")
                break
            if code != "A00000":
                logger.warning("爱奇艺 API 错误 (code=%s): %s", code, data.get("msg", ""))
                if attempt < 2:
                    import time as _time
                    _time.sleep(2)
                    continue
                break

            vidl = data.get("data", {}).get("vidl", [])
            for stream in vidl:
                m3u8_url = stream.get("m3utx", "")
                if not m3u8_url:
                    continue

                vd = stream.get("vd", 0)
                quality_info = _QUALITY_MAP.get(vd, ("未知", 0, 0, 0))

                formats.append(VideoFormat(
                    url=m3u8_url,
                    ext="mp4",
                    quality=quality_info[0],
                    quality_number=quality_info[3],
                    width=quality_info[1],
                    height=quality_info[2],
                    filesize=None,
                    format_note=f"M3U8 stream, vd={vd}",
                ))

            if formats:
                break

        return formats

    def _call_tmts_api(self, tvid: str, video_id: str) -> dict[str, Any]:
        """
        调用 tmts API。

        签名算法：sc = md5(timestamp + key + tvid)
        """
        tm = str(int(time.time() * 1000))
        sc = _md5(tm + _SIGN_KEY + tvid)

        params = urllib.parse.urlencode({
            "tvid": tvid,
            "vid": video_id,
            "src": _SRC,
            "sc": sc,
            "t": tm,
        })

        api_url = f"http://cache.m.iqiyi.com/jp/tmts/{tvid}/{video_id}/?{params}"

        try:
            text = self._request_text(api_url, headers=_IQIYI_HEADERS, timeout=15)
            # 响应格式: var tvInfoJs={...}
            json_str = re.sub(r"^var\s+tvInfoJs\s*=\s*", "", text.strip()).rstrip(";")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ExtractionError(f"爱奇艺 API 响应解析失败: {e}") from e
