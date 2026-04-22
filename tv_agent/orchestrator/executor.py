"""
由 `ExecutionPlan` 驱动的一次查询执行（同步）。

供 `app.services.tv_service` 在线程池中调用，避免在多处重复 if plan.use_agent 分支。
"""

from __future__ import annotations

from typing import Any

from tv_agent.agent import run_actor_search_query, run_availability_query
from tv_agent.domain.schemas import TVAvailabilityResult
from tv_agent.orchestrator.execution_plan import ExecutionPlan
from tv_agent.pipeline import run_actor_pipeline, run_availability_pipeline
from tv_agent.preferences import UserQueryPreferences, apply_preferences


def execute_planned_title_query(
    plan: ExecutionPlan,
    title: str,
    *,
    hint: str | None,
    memory: Any,
    preferences: UserQueryPreferences | None,
    callbacks: list[Any] | None = None,
) -> TVAvailabilityResult:
    if plan.use_agent:
        return apply_preferences(
            run_availability_query(
                title,
                disambiguation_hint=hint,
                memory=memory,
                callbacks=callbacks,
            ),
            preferences,
        )
    return run_availability_pipeline(
        title,
        disambiguation_hint=hint,
        preferences=preferences,
    )


def execute_planned_actor_query(
    plan: ExecutionPlan,
    actor: str,
    *,
    hint: str | None,
    memory: Any,
    preferences: UserQueryPreferences | None,
    callbacks: list[Any] | None = None,
) -> TVAvailabilityResult:
    if plan.use_agent:
        return apply_preferences(
            run_actor_search_query(
                actor,
                disambiguation_hint=hint,
                memory=memory,
                callbacks=callbacks,
            ),
            preferences,
        )
    return run_actor_pipeline(
        actor,
        disambiguation_hint=hint,
        preferences=preferences,
    )
