"""地区相关展示/检索用词（非权威地理编码库，仅供检索拼接与展示归一）。"""

from __future__ import annotations

# 常见中文区检索用词 -> 英文/ISO 提示（用于扩展搜索 query，非严格 ISO 映射）
ISO_REGION_HINTS: dict[str, str] = {
    "大陆": "China",
    "内地": "China",
    "中国": "China",
    "港台": "Hong Kong Taiwan",
    "香港": "Hong Kong",
    "台湾": "Taiwan",
    "美国": "United States",
    "韩国": "South Korea",
    "日本": "Japan",
    "泰国": "Thailand",
}
