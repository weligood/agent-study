"""内容可信度与推理边界（护栏占位，可与 eval / guardrails 对齐）。"""

from __future__ import annotations

from config import Settings, get_settings


def agent_may_infer_availability(settings: Settings | None = None) -> bool:
    """
    是否允许 Agent 在工具结果不足时「自行推断」平台可用性。

    当前与 `tv_query_mode=agent` 一致：启用 Agent 即允许模型组织语言总结；
    后续可拆成独立 feature flag。
    """
    return (settings or get_settings()).tv_query_mode == "agent"
