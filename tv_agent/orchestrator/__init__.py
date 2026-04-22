"""
显式决策层：意图 → 执行模式 → 统一执行计划（与 HTTP 入口解耦）。

**调用顺序**：`route_query_intent` → `select_execution_mode` → `build_execution_plan` 得到
`ExecutionPlan`；同步/流式服务再调 `execute_planned_title_query` / `execute_planned_actor_query`
真正跑 pipeline 或 Agent。

**与 policy 的关系**：URL 形态意图依赖 `tv_agent.policy.source_policy.video_url_requires_agent`；
下载门由 `policy.download_policy` 在工具层生效，不在本包重复实现业务分支。
"""

from tv_agent.orchestrator.execution_plan import ExecutionPlan, build_execution_plan
from tv_agent.orchestrator.executor import execute_planned_actor_query, execute_planned_title_query
from tv_agent.orchestrator.intent_router import QueryIntent, route_query_intent
from tv_agent.orchestrator.mode_selector import ExecutionMode, select_execution_mode

__all__ = [
    "ExecutionMode",
    "ExecutionPlan",
    "QueryIntent",
    "build_execution_plan",
    "execute_planned_actor_query",
    "execute_planned_title_query",
    "route_query_intent",
    "select_execution_mode",
]
