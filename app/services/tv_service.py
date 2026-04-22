"""
电视剧正版查询服务：在 worker 线程中执行同步 LangChain Agent，避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

import anyio

from tv_agent.agent import run_availability_query, run_actor_search_query
from tv_agent.callbacks import StreamingStepHandler
from tv_agent.memory import get_or_create_memory
from tv_agent.schemas import TVAvailabilityResult

logger = logging.getLogger(__name__)


async def query_tv_availability(
    title: str,
    hint: str | None = None,
    session_id: str | None = None,
) -> TVAvailabilityResult:
    """异步包装：内部在线程池调用 `run_availability_query`。"""
    memory = get_or_create_memory(session_id)
    return await anyio.to_thread.run_sync(
        lambda: run_availability_query(title, disambiguation_hint=hint, memory=memory),
    )


async def query_by_actor(
    actor: str,
    hint: str | None = None,
    session_id: str | None = None,
) -> TVAvailabilityResult:
    """异步包装：按演员查询电视剧。"""
    memory = get_or_create_memory(session_id)
    return await anyio.to_thread.run_sync(
        lambda: run_actor_search_query(actor, disambiguation_hint=hint, memory=memory),
    )


async def stream_tv_query(
    query_type: str,
    query: str,
    hint: str | None = None,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE 流式查询：yield SSE 格式的事件字符串。

    事件类型：
    - event: step    -> 推理步骤
    - event: result  -> 最终结果 JSON
    - event: error   -> 错误信息
    """
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    handler = StreamingStepHandler(queue)
    handler.set_loop(asyncio.get_event_loop())
    memory = get_or_create_memory(session_id)

    # 发送初始事件
    yield _sse_event("step", {"type": "start", "message": "开始处理查询..."})

    # 在线程池中执行 Agent
    async def _run_agent() -> TVAvailabilityResult:
        if query_type == "actor":
            return await anyio.to_thread.run_sync(
                lambda: run_actor_search_query(
                    query,
                    disambiguation_hint=hint,
                    memory=memory,
                    callbacks=[handler],
                ),
            )
        else:
            return await anyio.to_thread.run_sync(
                lambda: run_availability_query(
                    query,
                    disambiguation_hint=hint,
                    memory=memory,
                    callbacks=[handler],
                ),
            )

    # 启动 Agent 任务
    agent_task = asyncio.create_task(_run_agent())

    # 持续读取步骤事件
    try:
        while not agent_task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                if event is not None:
                    yield _sse_event("step", event)
            except asyncio.TimeoutError:
                continue

        # Agent 完成后，清空队列中剩余事件
        while not queue.empty():
            event = queue.get_nowait()
            if event is not None:
                yield _sse_event("step", event)

        # 获取最终结果
        result = await agent_task
        yield _sse_event("result", result.model_dump(mode="json"))

    except Exception as e:  # noqa: BLE001
        logger.exception("SSE 流式查询出错: %s", e)
        yield _sse_event("error", {"message": str(e)})


def _sse_event(event_type: str, data: Any) -> str:
    """将事件格式化为 SSE 文本。"""
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_str}\n\n"
