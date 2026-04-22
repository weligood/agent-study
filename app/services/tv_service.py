"""
电视剧正版查询服务：在 worker 线程中执行同步流水线或 LangChain Agent，避免阻塞事件循环。

## 端到端逻辑（从 HTTP 到结果）

1. **HTTP**：`app/api/routes/tv` 校验 `TvQueryRequest`，经 `Depends(get_request_id)` 取 `request_id`（由
   `RequestIdMiddleware` 与请求头 `X-Request-ID` 对齐）。
2. **编排**：`build_execution_plan(query_type, text)` 产出 `ExecutionPlan`：
   - `intent_router`：剧名 / 演员 / 视频 URL / 推荐用语等粗意图；
   - `mode_selector`：`tv_query_mode=agent` 或 **HTTP(S) URL** → `AGENT_TOOL_CALLING`，否则剧名走
     **LangGraph**、演员走 **单步确定性检索**。
3. **执行**：`execute_planned_*_query(plan, …)`：
   - `use_agent` 为真 → `run_*_query`（LangChain Agent + `tv_agent.tools.agent_tools`）；
   - 否则 → `run_*_pipeline`（剧名：`graphs.tv_availability`；演员：联网聚合候选）。
4. **偏好**：`apply_preferences` 仅在 Agent 路径对结果做过滤/排序；pipeline 路径在 pipeline 内已应用。
5. **观测**：同步接口在返回前写入 `TVAvailabilityResult.response_meta`；SSE 在 `trace.start` 附
   `orchestration`/`correlation`，结束前附 `RequestMetrics`，`result.final` 再合并 `response_meta`。

异常与 422 由 `app.core.exception_handlers` 统一在 JSON 中附带 `request_id`。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Literal, cast

import anyio

from config import get_settings
from tv_agent.callbacks import StreamingStepHandler
from tv_agent.memory import get_or_create_memory
from tv_agent.orchestrator import (
    build_execution_plan,
    execute_planned_actor_query,
    execute_planned_title_query,
)
from tv_agent.preferences import UserQueryPreferences
from tv_agent.domain.schemas import QueryResponseMeta, TVAvailabilityResult
from tv_agent.trace.events import TraceEvent, sse_packet
from tv_agent.trace.metrics import RequestMetrics

logger = logging.getLogger(__name__)


def _correlation_payload(
    *,
    trace_id: str,
    run_id: str,
    request_id: str | None,
    session_id: str | None,
) -> dict[str, str]:
    d: dict[str, str] = {"trace_id": trace_id, "run_id": run_id}
    if request_id:
        d["request_id"] = request_id
    if session_id:
        d["session_id"] = session_id
    return d


async def query_tv_availability(
    title: str,
    hint: str | None = None,
    session_id: str | None = None,
    *,
    preferences: UserQueryPreferences | None = None,
    request_id: str | None = None,
) -> TVAvailabilityResult:
    """异步包装：由 orchestrator 决定 pipeline / agent。"""
    settings = get_settings()
    memory = get_or_create_memory(session_id)
    plan = build_execution_plan("title", title, settings=settings)

    def _run() -> TVAvailabilityResult:
        return execute_planned_title_query(
            plan,
            title,
            hint=hint,
            memory=memory,
            preferences=preferences,
            callbacks=None,
        )

    try:
        out = await anyio.to_thread.run_sync(_run)
        meta = QueryResponseMeta(
            request_id=request_id,
            intent=str(plan.intent.value),
            execution_mode=str(plan.execution_mode.value),
            use_agent=plan.use_agent,
        )
        return out.model_copy(update={"response_meta": meta})
    except Exception:
        logger.exception(
            "剧名查询失败 title=%r request_id=%r session_id=%r",
            title,
            request_id,
            session_id,
        )
        raise


async def query_by_actor(
    actor: str,
    hint: str | None = None,
    session_id: str | None = None,
    *,
    preferences: UserQueryPreferences | None = None,
    request_id: str | None = None,
) -> TVAvailabilityResult:
    """异步包装：由 orchestrator 决定 pipeline / agent。"""
    settings = get_settings()
    memory = get_or_create_memory(session_id)
    plan = build_execution_plan("actor", actor, settings=settings)

    def _run() -> TVAvailabilityResult:
        return execute_planned_actor_query(
            plan,
            actor,
            hint=hint,
            memory=memory,
            preferences=preferences,
            callbacks=None,
        )

    try:
        out = await anyio.to_thread.run_sync(_run)
        meta = QueryResponseMeta(
            request_id=request_id,
            intent=str(plan.intent.value),
            execution_mode=str(plan.execution_mode.value),
            use_agent=plan.use_agent,
        )
        return out.model_copy(update={"response_meta": meta})
    except Exception:
        logger.exception(
            "演员查询失败 actor=%r request_id=%r session_id=%r",
            actor,
            request_id,
            session_id,
        )
        raise


async def stream_tv_query(
    query_type: str,
    query: str,
    hint: str | None = None,
    session_id: str | None = None,
    *,
    preferences: UserQueryPreferences | None = None,
    request_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE 流式查询：yield SSE 格式字符串。

    标准事件名：trace.start / trace.step / trace.tool_call / trace.tool_result /
    trace.warning / result.final / error（兼容旧客户端可继续解析 data 内字段）。
    """
    t0 = time.perf_counter()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    trace_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    corr = _correlation_payload(
        trace_id=trace_id,
        run_id=run_id,
        request_id=request_id,
        session_id=session_id,
    )
    handler = StreamingStepHandler(
        queue,
        trace_id=trace_id,
        run_id=run_id,
        request_id=request_id,
        session_id=session_id,
    )
    handler.set_loop(asyncio.get_event_loop())
    memory = get_or_create_memory(session_id)
    settings = get_settings()
    qt = cast(Literal["title", "actor"], query_type if query_type in ("title", "actor") else "title")
    plan = build_execution_plan(qt, query, settings=settings)
    use_agent = plan.use_agent

    orch = plan.to_trace_payload()
    yield sse_packet(
        "trace.start",
        TraceEvent(
            trace_id=trace_id,
            run_id=run_id,
            event_type="trace.start",
            source="system",
            phase="query",
            message="开始处理查询",
            payload={
                "query_type": query_type,
                "query": query,
                "hint": hint,
                "preferences": preferences.model_dump(mode="json") if preferences else None,
                "orchestration": orch,
                "correlation": corr,
            },
        ).model_dump(mode="json"),
    )

    async def _run_query() -> TVAvailabilityResult:
        if qt == "actor":
            return await anyio.to_thread.run_sync(
                lambda: execute_planned_actor_query(
                    plan,
                    query,
                    hint=hint,
                    memory=memory,
                    preferences=preferences,
                    callbacks=[handler] if use_agent else None,
                ),
            )
        return await anyio.to_thread.run_sync(
            lambda: execute_planned_title_query(
                plan,
                query,
                hint=hint,
                memory=memory,
                preferences=preferences,
                callbacks=[handler] if use_agent else None,
            ),
        )

    if not use_agent:
        yield sse_packet(
            "trace.step",
            TraceEvent(
                trace_id=trace_id,
                run_id=run_id,
                event_type="trace.step",
                source="pipeline_graph",
                phase="pipeline",
                message="使用确定性检索链（无大模型编排），正在查询…",
                payload={"orchestration": orch, "correlation": corr},
            ).model_dump(mode="json"),
        )

    agent_task = asyncio.create_task(_run_query())

    try:
        while not agent_task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if event is None:
                continue
            ev_name = event.get("event")
            payload = event.get("payload")
            if ev_name and payload is not None:
                pl = payload if isinstance(payload, dict) else {"data": payload}
                if isinstance(pl, dict) and "correlation" not in pl:
                    pl = {**pl, "correlation": corr}
                yield sse_packet(ev_name, pl)
            else:
                yield sse_packet(
                    "trace.step",
                    TraceEvent(
                        trace_id=trace_id,
                        run_id=run_id,
                        event_type="trace.step",
                        source="agent",
                        phase="agent",
                        message=str((event or {}).get("message", "")),
                        payload={
                            **{k: v for k, v in (event or {}).items() if k not in ("event", "payload")},
                            "correlation": corr,
                        },
                    ).model_dump(mode="json"),
                )

        while not queue.empty():
            event = queue.get_nowait()
            if event is None:
                continue
            ev_name = event.get("event")
            payload = event.get("payload")
            if ev_name and payload is not None:
                pl = payload if isinstance(payload, dict) else {"data": payload}
                if isinstance(pl, dict) and "correlation" not in pl:
                    pl = {**pl, "correlation": corr}
                yield sse_packet(ev_name, pl)

        result = await agent_task
        if not use_agent and result.pipeline_node_trace:
            yield sse_packet(
                "trace.step",
                TraceEvent(
                    trace_id=trace_id,
                    run_id=run_id,
                    event_type="trace.step",
                    source="pipeline_graph",
                    phase="graph",
                    message=f"LangGraph 节点轨迹（{len(result.pipeline_node_trace)} 条）",
                    payload={
                        "nodes": result.pipeline_node_trace,
                        "orchestration": orch,
                        "correlation": corr,
                    },
                ).model_dump(mode="json"),
            )

        total_ms = (time.perf_counter() - t0) * 1000.0
        metrics = RequestMetrics(
            total_ms=round(total_ms, 2),
            intent=str(plan.intent.value),
            execution_mode=str(plan.execution_mode.value),
            success=True,
        )
        yield sse_packet(
            "trace.step",
            TraceEvent(
                trace_id=trace_id,
                run_id=run_id,
                event_type="trace.step",
                source="system",
                phase="metrics",
                message="请求级指标摘要",
                payload={
                    "metrics": metrics.model_dump(mode="json"),
                    "correlation": corr,
                    "orchestration": orch,
                },
            ).model_dump(mode="json"),
        )
        meta = QueryResponseMeta(
            request_id=request_id,
            trace_id=trace_id,
            run_id=run_id,
            intent=str(plan.intent.value),
            execution_mode=str(plan.execution_mode.value),
            use_agent=plan.use_agent,
            total_ms=metrics.total_ms,
        )
        yield sse_packet(
            "result.final",
            result.model_copy(update={"response_meta": meta}).model_dump(mode="json"),
        )

    except Exception as e:  # noqa: BLE001
        logger.exception("SSE 流式查询出错: %s", e)
        total_ms = (time.perf_counter() - t0) * 1000.0
        yield sse_packet(
            "error",
            {
                "message": str(e),
                "trace_id": trace_id,
                "run_id": run_id,
                "request_id": request_id,
                "session_id": session_id,
                "metrics": RequestMetrics(
                    total_ms=round(total_ms, 2),
                    intent=str(plan.intent.value),
                    execution_mode=str(plan.execution_mode.value),
                    success=False,
                ).model_dump(mode="json"),
            },
        )
