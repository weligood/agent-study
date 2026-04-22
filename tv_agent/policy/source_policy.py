"""来源与入口形态策略：何时必须走 Agent、哪些 URL 仅解析等。"""

from __future__ import annotations


def video_url_requires_agent(text: str) -> bool:
    """视频页 / 通用 HTTP(S) 输入需要工具链（解析、可选下载），不走纯 pipeline。"""
    s = text.strip().lower()
    return s.startswith("http://") or s.startswith("https://")


def url_parse_only(url: str) -> bool:
    """
    预留：未来可标记「仅允许元数据抽取、禁止下载」的域名或方案。

    当前默认 False：是否可下载由 `download_policy` 与工具内逻辑共同约束。
    """
    _ = url
    return False
