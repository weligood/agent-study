"""
电视剧正版查询领域包：LangChain Agent、工具、Prompt、领域模型。

与 FastAPI 应用包 `app` 解耦，便于单独测试与复用（CLI、Worker、库模式）。
"""

from tv_agent.agent import build_executor, parse_agent_output_to_result, run_availability_query
from tv_agent.schemas import TVAvailabilityResult

__all__ = [
    "TVAvailabilityResult",
    "build_executor",
    "parse_agent_output_to_result",
    "run_availability_query",
]
__version__ = "0.4.0"
