"""剧名别名与轻量归一（可逐步扩充，避免散落在 resolution 各处）。"""

from __future__ import annotations

import re

# 常见别称 -> 规范检索用名（小表；大体量数据应走 Meilisearch / DB）
_SERIES_ALIASES: dict[str, str] = {
    # 示例占位：后续可由数据文件或运营配置加载
}


def normalize_series_alias(title: str) -> str:
    """若命中别名表则替换为规范名；否则返回去空白后的原文。"""
    t = title.strip()
    if not t:
        return t
    key = re.sub(r"\s+", "", t.lower())
    for k, v in _SERIES_ALIASES.items():
        if re.sub(r"\s+", "", k.lower()) == key:
            return v
    return t
