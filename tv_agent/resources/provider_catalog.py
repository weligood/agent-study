"""平台展示名、关键词、Logo、官方搜索落地页（稳定目录，不放在 prompt 或 tool 里散改）。"""

from __future__ import annotations

import urllib.parse

PLATFORM_KEYWORDS: list[tuple[str, str]] = [
    ("iqiyi", "爱奇艺"),
    ("爱奇艺", "爱奇艺"),
    ("v.qq.com", "腾讯视频"),
    ("腾讯视频", "腾讯视频"),
    ("youku", "优酷"),
    ("优酷", "优酷"),
    ("bilibili", "哔哩哔哩"),
    ("哔哩哔哩", "哔哩哔哩"),
    ("B站", "哔哩哔哩"),
    ("mgtv", "芒果TV"),
    ("芒果TV", "芒果TV"),
    ("芒果", "芒果TV"),
    ("netflix", "Netflix"),
    ("cctv", "央视网"),
    ("央视", "央视网"),
    ("mango", "芒果TV"),
]

PLATFORM_LOGOS_MAP: dict[str, str] = {
    "爱奇艺": "https://www.iqiyi.com/favicon.ico",
    "腾讯视频": "https://v.qq.com/favicon.ico",
    "优酷": "https://www.youku.com/favicon.ico",
    "芒果TV": "https://www.mgtv.com/favicon.ico",
    "哔哩哔哩": "https://www.bilibili.com/favicon.ico",
    "Netflix": "https://www.netflix.com/favicon.ico",
    "央视网": "https://tv.cctv.com/favicon.ico",
}


def build_search_url(platform_name: str, title: str) -> str:
    """为平台构建 PC 版搜索链接（使用主域名，避免子域名被屏蔽）。"""
    encoded = urllib.parse.quote(title)
    url_map = {
        "爱奇艺": f"https://www.iqiyi.com/search/{encoded}",
        "腾讯视频": f"https://v.qq.com/x/search/?q={encoded}",
        "优酷": f"https://www.youku.com/search/{encoded}",
        "哔哩哔哩": f"https://www.bilibili.com/search?keyword={encoded}",
        "芒果TV": f"https://www.mgtv.com/so/{encoded}.html",
        "Netflix": f"https://www.netflix.com/search?q={encoded}",
        "央视网": f"https://tv.cctv.com/search/?qtext={encoded}",
    }
    return url_map.get(
        platform_name,
        f"https://www.google.com/search?q={encoded}+{urllib.parse.quote(platform_name)}",
    )
