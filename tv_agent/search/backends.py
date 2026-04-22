"""
联网搜索后端：以自托管 SearXNG 为主，归一为 `organic_results` + `knowledge_graph`，供 `tv_agent.tools` 消费。

- SearXNG — https://github.com/searxng/searxng ，`GET /search?format=json`
- DuckDuckGo（duckduckgo-search）— 无 Key，作未配置 SearXNG 或 SearXNG 无结果时的回退
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import Settings, get_settings
from tv_agent.search.meili_fusion import merge_meili_prepend, meili_only_payload
from tv_agent.search.searxng_parse import parse_searxng_response

logger = logging.getLogger(__name__)


def _strip_internal_keys(payload: dict[str, Any]) -> dict[str, Any]:
    """去掉 `_search_backend` 等内部字段，避免进入 Agent/日志的对外 JSON。"""
    return {k: v for k, v in payload.items() if not str(k).startswith("_")}


def _http_json_get(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(body)
            return parsed if isinstance(parsed, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("HTTP JSON GET 失败: %s — %s", url[:120], e)
        return None


def _duckduckgo_backend(cfg: Settings, query: str, num_results: int) -> dict[str, Any] | None:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.warning("duckduckgo 后端：未安装 duckduckgo-search，请 pip install duckduckgo-search")
        return None
    try:
        with DDGS(timeout=cfg.request_timeout_seconds) as ddgs:
            rows = list(
                ddgs.text(
                    query,
                    region="cn-zh",
                    max_results=max(1, min(num_results, 25)),
                )
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("DuckDuckGo 搜索失败: %s", e)
        return None
    organic: list[dict[str, Any]] = []
    for r in rows:
        href = r.get("href") or ""
        organic.append(
            {
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "link": href,
                "displayed_link": href,
            }
        )
    return _strip_internal_keys(
        {
            "organic_results": organic,
            "knowledge_graph": {},
            "_search_backend": "duckduckgo",
        }
    )


def _searxng_backend(cfg: Settings, query: str, num_results: int) -> dict[str, Any] | None:
    base = (cfg.searxng_base_url or "").rstrip("/")
    if not base:
        return None
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "language": "zh",
            "categories": "general",
        }
    )
    url = f"{base}/search?{params}"
    data = _http_json_get(
        url,
        {
            "Accept": "application/json",
            "User-Agent": "tv-agent-study/1.0 (+https://github.com/)",
        },
        cfg.request_timeout_seconds,
    )
    if data is None:
        return None
    organic, kg = parse_searxng_response(data, num_results=num_results)
    return _strip_internal_keys(
        {
            "organic_results": organic,
            "knowledge_graph": kg,
            "_search_backend": "searxng",
        }
    )


def _apply_meili_fusion(
    cfg: Settings,
    query: str,
    web_payload: dict[str, Any] | None,
    *,
    num_results: int,
) -> dict[str, Any] | None:
    """若配置了 Meilisearch，将片库命中前置合并到 organic_results。"""
    if not (cfg.meilisearch_url or "").strip():
        return web_payload
    merged = merge_meili_prepend(cfg, query, web_payload, num_results=num_results)
    if merged is not None:
        return merged
    return web_payload


def run_unified_web_search(
    query: str,
    *,
    num_results: int = 8,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """
    联网搜索：优先 SearXNG（`SEARXNG_BASE_URL`）；无结果或未配置时按 `SEARCH_FALLBACK_DDG` 使用 DuckDuckGo。

    返回形态：`organic_results` + `knowledge_graph`（与既有 tools 解析兼容）。
    """
    cfg = settings or get_settings()
    out: dict[str, Any] | None = None

    if (cfg.searxng_base_url or "").strip():
        out = _searxng_backend(cfg, query, num_results)
        if out and len(out.get("organic_results") or []) > 0:
            return _apply_meili_fusion(cfg, query, out, num_results=num_results)

    if cfg.search_fallback_ddg:
        logger.info("SearXNG 未配置、请求失败或无网页结果，使用 DuckDuckGo 回退")
        out = _duckduckgo_backend(cfg, query, num_results)
        fused = _apply_meili_fusion(cfg, query, out, num_results=num_results)
        if fused and len(fused.get("organic_results") or []) > 0:
            return fused

    mo = meili_only_payload(cfg, query, limit=min(5, num_results))
    if mo:
        return _apply_meili_fusion(cfg, query, mo, num_results=num_results)
    return None
