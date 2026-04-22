"""
LangGraph 等业务图编排（与 AgentExecutor 解耦）。

- `tv_availability`：剧名 → 元数据 → 平台 → 相似 → 汇总
- `state`：图运行时状态 TypedDict（与领域结果模型分离）
"""

from tv_agent.graphs.state import (
    ActorSearchState,
    TVAvailabilityGraphState,
    VideoExtractGraphState,
)
from tv_agent.graphs.tv_availability import run_tv_availability_graph

__all__ = [
    "ActorSearchState",
    "TVAvailabilityGraphState",
    "VideoExtractGraphState",
    "run_tv_availability_graph",
]
