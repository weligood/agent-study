"""
哔哩哔哩 (Bilibili) 视频提取器。

参考项目：
- yt-dlp/yt-dlp: yt_dlp/extractor/bilibili.py（Extractor 架构与 DASH 格式处理）
- Bilibili_video_download: API 调用方式与签名算法

支持的 URL 格式：
- https://www.bilibili.com/video/BVxxxxxxxxxx
- https://www.bilibili.com/video/avxxxxxxxx
- https://b23.tv/xxxxxxx（短链接）
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any

from video_scraper.base import BaseExtractor, ExtractionError, _SSL_CTX
from video_scraper.models import VideoFormat, VideoInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# B站 API 签名所需的混淆密钥（参考 yt-dlp / Bilibili_video_download）
# ---------------------------------------------------------------------------
_ENTROPY = "rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg"
_APPKEY, _SEC = "".join(chr(ord(i) + 2) for i in _ENTROPY[::-1]).split(":")

# 清晰度映射
_QUALITY_MAP: dict[int, tuple[str, int, int]] = {
    # qn: (标签, 宽度, 高度)
    127: ("8K 超高清", 7680, 4320),
    126: ("杜比视界", 3840, 2160),
    125: ("HDR 真彩", 3840, 2160),
    120: ("4K 超清", 3840, 2160),
    116: ("1080P60 高帧率", 1920, 1080),
    112: ("1080P 高码率", 1920, 1080),
    80: ("1080P 高清", 1920, 1080),
    74: ("720P60 高帧率", 1280, 720),
    64: ("720P 高清", 1280, 720),
    32: ("480P 清晰", 854, 480),
    16: ("360P 流畅", 640, 360),
    6: ("240P 极速", 426, 240),
}

# 请求头
_BILIBILI_HEADERS = {
    "Referer": "https://www.bilibili.com",
    "Origin": "https://www.bilibili.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _sign_params(params: dict[str, str]) -> str:
    """对请求参数进行 MD5 签名（appkey + sec）。"""
    params["appkey"] = _APPKEY
    query = urllib.parse.urlencode(sorted(params.items()))
    sign = hashlib.md5((query + _SEC).encode()).hexdigest()
    return f"{query}&sign={sign}"


class BilibiliExtractor(BaseExtractor):
    """哔哩哔哩视频提取器。"""

    _VALID_URL = (
        r"https?://(?:www\.)?bilibili\.com/video/"
        r"(?P<id>(?:BV[\w]+|av\d+))(?:/?\?.*)?$"
        r"|https?://b23\.tv/(?P<short_id>[\w]+)"
    )

    def _real_extract(self, url: str) -> VideoInfo:
        """从 B 站视频 URL 提取视频信息。"""
        # 处理短链接
        if "b23.tv" in url:
            url = self._resolve_short_url(url)

        m = re.match(self._VALID_URL, url)
        if not m:
            raise ExtractionError(f"无法解析 B 站 URL: {url}")

        video_id = m.group("id")
        if not video_id:
            raise ExtractionError(f"无法从 URL 提取视频 ID: {url}")

        # 判断 BV 号还是 av 号
        if video_id.startswith("av"):
            aid = video_id[2:]
            bvid = None
        else:
            aid = None
            bvid = video_id

        # Step 1: 获取视频基础信息
        view_info = self._get_view_info(aid=aid, bvid=bvid)

        # Step 2: 获取视频流地址
        actual_aid = str(view_info["aid"])
        cid = str(view_info["cid"])
        formats = self._get_formats(actual_aid, cid)

        # Step 3: 构建 VideoInfo
        stat = view_info.get("stat", {})
        owner = view_info.get("owner", {})

        return VideoInfo(
            id=bvid or f"av{actual_aid}",
            title=view_info.get("title", "未知标题"),
            url=f"https://www.bilibili.com/video/{bvid or 'av' + actual_aid}",
            platform="bilibili",
            duration=view_info.get("duration"),
            thumbnail=view_info.get("pic"),
            uploader=owner.get("name"),
            uploader_id=str(owner.get("mid", "")),
            description=view_info.get("desc"),
            view_count=stat.get("view"),
            like_count=stat.get("like"),
            upload_date=None,
            formats=formats,
            extra={
                "aid": actual_aid,
                "cid": cid,
                "coin": stat.get("coin"),
                "favorite": stat.get("favorite"),
                "share": stat.get("share"),
                "danmaku": stat.get("danmaku"),
            },
        )

    def _resolve_short_url(self, url: str) -> str:
        """解析 b23.tv 短链接为完整 URL。"""
        try:
            req = urllib.request.Request(url, headers=_BILIBILI_HEADERS, method="HEAD")
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                return resp.url
        except Exception as e:
            raise ExtractionError(f"解析短链接失败 ({url}): {e}") from e

    def _get_view_info(
        self, *, aid: str | None = None, bvid: str | None = None,
    ) -> dict[str, Any]:
        """
        调用 /x/web-interface/view API 获取视频基础信息。

        返回包含 title, aid, cid, duration, owner, stat 等字段的字典。
        """
        params: dict[str, str] = {}
        if bvid:
            params["bvid"] = bvid
        elif aid:
            params["aid"] = aid
        else:
            raise ExtractionError("需要提供 aid 或 bvid")

        api_url = f"https://api.bilibili.com/x/web-interface/view?{urllib.parse.urlencode(params)}"
        data = self._request_json(api_url, headers=_BILIBILI_HEADERS)

        code = data.get("code", -1)
        if code != 0:
            message = data.get("message", "未知错误")
            raise ExtractionError(f"B站 API 错误 (code={code}): {message}")

        result = data.get("data", {})
        if not result:
            raise ExtractionError("B站 API 未返回视频数据")

        # 取第一个分P的 cid
        pages = result.get("pages", [])
        if pages:
            result["cid"] = pages[0]["cid"]

        return result

    def _get_formats(self, aid: str, cid: str) -> list[VideoFormat]:
        """获取视频流地址列表。优先 DASH 格式，降级到旧版 FLV。"""
        formats = self._get_dash_formats(aid, cid)
        if not formats:
            formats = self._get_legacy_formats(aid, cid)
        return formats

    def _get_dash_formats(self, aid: str, cid: str) -> list[VideoFormat]:
        """
        通过 /x/player/playurl API 获取 DASH 格式视频流。

        fnval=4048 请求 DASH 格式（视频 + 音频分离）。
        """
        params = {
            "avid": aid,
            "cid": cid,
            "qn": "127",
            "type": "",
            "otype": "json",
            "fourk": "1",
            "fnver": "0",
            "fnval": "4048",
        }
        signed = _sign_params(params)
        api_url = f"https://api.bilibili.com/x/player/playurl?{signed}"
        data = self._request_json(api_url, headers=_BILIBILI_HEADERS)

        code = data.get("code", -1)
        if code != 0:
            logger.warning("DASH 格式请求失败 (code=%d): %s", code, data.get("message"))
            return []

        dash = data.get("data", {}).get("dash")
        if not dash:
            return []

        formats: list[VideoFormat] = []
        videos = dash.get("video", [])
        for v in videos:
            qn = v.get("id", 0)
            quality_info = _QUALITY_MAP.get(qn, ("未知", 0, 0))

            base_url = v.get("baseUrl") or v.get("base_url", "")
            if not base_url:
                continue

            formats.append(VideoFormat(
                url=base_url,
                ext="mp4",
                quality=quality_info[0],
                quality_number=qn,
                width=v.get("width") or quality_info[1],
                height=v.get("height") or quality_info[2],
                filesize=v.get("size"),
                format_note=f"DASH video, codec={v.get('codecs', 'unknown')}",
            ))

        return formats

    def _get_legacy_formats(self, aid: str, cid: str) -> list[VideoFormat]:
        """降级方案：通过旧版 API 获取 FLV 格式视频流。"""
        params = {
            "avid": aid,
            "cid": cid,
            "qn": "80",
            "type": "",
            "otype": "json",
        }
        signed = _sign_params(params)
        api_url = f"https://api.bilibili.com/x/player/playurl?{signed}"
        data = self._request_json(api_url, headers=_BILIBILI_HEADERS)

        code = data.get("code", -1)
        if code != 0:
            return []

        durl = data.get("data", {}).get("durl", [])
        quality = data.get("data", {}).get("quality", 0)
        quality_info = _QUALITY_MAP.get(quality, ("未知", 0, 0))

        formats: list[VideoFormat] = []
        for idx, seg in enumerate(durl):
            url = seg.get("url", "")
            if not url:
                continue
            formats.append(VideoFormat(
                url=url,
                ext="flv",
                quality=quality_info[0],
                quality_number=quality,
                width=quality_info[1],
                height=quality_info[2],
                filesize=seg.get("size"),
                format_note=f"Legacy FLV, part {idx + 1}/{len(durl)}",
            ))

        return formats
