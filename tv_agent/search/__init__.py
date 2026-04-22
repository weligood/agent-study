"""联网搜索：SearXNG 为主、DuckDuckGo 回退，统一为 organic_results + knowledge_graph 结构。"""

from tv_agent.search.backends import run_unified_web_search

__all__ = ["run_unified_web_search"]
