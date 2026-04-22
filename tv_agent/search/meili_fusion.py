"""
Meilisearch 剧名片库：将命中结果转为 `organic_results` 条目，与联网搜索融合。

推荐索引 settings（在 Meilisearch 中创建 `tv_titles` 等）：
- `primaryKey`: `id`（字符串）
- 可检索字段：`title`, `aliases`, `year`, `region`, `notes`
- 可选：`url`（豆瓣/官网等）

文档示例：{"id": "show-001", "title": "漫长的季节", "aliases": "The Long Season", "year": 2023, "region": "中国大陆", "notes": "自制片库", "url": "https://..."}
"""

from __future__ import annotations

import logging
from typing import Any

from config import Settings

logger = logging.getLogger(__name__)


def meili_hits_as_organic(cfg: Settings, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """
    在已配置 `meilisearch_url` 时，从本地索引检索并返回 organic 形态列表（可能为空）。
    """
    base = (cfg.meilisearch_url or "").rstrip("/")
    if not base:
        return []
    try:
        from meilisearch import Client
    except ImportError:
        logger.warning("Meilisearch：未安装 meilisearch SDK，请 pip install meilisearch")
        return []

    key = cfg.meilisearch_api_key or ""
    try:
        client = Client(base, key)
        idx = client.index(cfg.meilisearch_index)
        res = idx.search(
            query,
            {
                "limit": max(1, min(limit, 20)),
                "attributesToRetrieve": ["*"],
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Meilisearch 查询失败: %s", e)
        return []

    hits = res.get("hits") or []
    organic: list[dict[str, Any]] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        title = str(h.get("title") or h.get("name") or "").strip()
        if not title:
            continue
        parts: list[str] = []
        if h.get("year") is not None:
            parts.append(f"年份: {h['year']}")
        if h.get("region"):
            parts.append(f"地区: {h['region']}")
        if h.get("aliases"):
            parts.append(f"别名: {h['aliases']}")
        if h.get("notes"):
            parts.append(str(h["notes"]))
        snippet = " | ".join(parts) if parts else "（本地片库）"
        link = str(h.get("url") or "").strip() or f"meilisearch://{h.get('id', title)}"
        organic.append(
            {
                "title": f"[片库] {title}",
                "snippet": snippet,
                "link": link,
                "displayed_link": link,
            }
        )
    return organic


def merge_meili_prepend(
    cfg: Settings,
    query: str,
    web_payload: dict[str, Any] | None,
    *,
    num_results: int,
) -> dict[str, Any] | None:
    """
    将 Meilisearch 命中置于 `organic_results` 最前，再拼接联网结果；去重 link。
    """
    meili_rows = meili_hits_as_organic(cfg, query, limit=min(5, num_results))
    if not meili_rows:
        return web_payload
    if web_payload is None:
        return {
            "organic_results": meili_rows,
            "knowledge_graph": {"description": "前若干条来自本地 Meilisearch 片库索引。"},
        }
    org = list(web_payload.get("organic_results") or [])
    seen: set[str] = {str(r.get("link") or "") for r in meili_rows}
    rest = [r for r in org if str(r.get("link") or "") not in seen]
    merged = meili_rows + rest
    cap = max(num_results + len(meili_rows), 25)
    out = {**web_payload, "organic_results": merged[:cap]}
    return out


def meili_only_payload(cfg: Settings, query: str, *, limit: int) -> dict[str, Any] | None:
    rows = meili_hits_as_organic(cfg, query, limit=limit)
    if not rows:
        return None
    return {
        "organic_results": rows,
        "knowledge_graph": {"description": "结果仅来自本地 Meilisearch 片库。"},
    }
