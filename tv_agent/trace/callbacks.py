"""
LangChain 回调：将 Agent 执行过程封装为标准 TraceEvent，供 SSE 端点发送。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from tv_agent.trace.events import TraceEvent

logger = logging.getLogger(__name__)


class StreamingStepHandler(BaseCallbackHandler):
    """将关键步骤写入 asyncio.Queue；负载为 {event, payload}，payload 为 TraceEvent 或错误体。"""

    def __init__(
        self,
        queue: asyncio.Queue[dict[str, Any] | None],
        *,
        trace_id: str | None = None,
        run_id: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        super().__init__()
        self._queue = queue
        self._loop: asyncio.AbstractEventLoop | None = None
        self.trace_id = trace_id or str(uuid.uuid4())
        self.run_id = run_id or str(uuid.uuid4())
        self._request_id = request_id
        self._session_id = session_id

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _put(self, item: dict[str, Any]) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
        else:
            try:
                self._queue.put_nowait(item)
            except Exception:  # noqa: BLE001
                logger.debug("无法推送事件: %s", item)

    def _emit_trace(self, sse_name: str, **kwargs: Any) -> None:
        payload = dict(kwargs.pop("payload", None) or {})
        if self._request_id:
            payload.setdefault("request_id", self._request_id)
        if self._session_id:
            payload.setdefault("session_id", self._session_id)
        te = TraceEvent(
            trace_id=self.trace_id,
            run_id=self.run_id,
            event_type=sse_name,
            source="agent",
            payload=payload,
            **kwargs,
        )
        self._put({"event": sse_name, "payload": te.model_dump(mode="json")})

    # ---- LLM 回调 ----
    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self._emit_trace(
            "trace.step",
            phase="llm",
            message="模型推理中…",
            payload={"stage": "llm_start"},
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self._emit_trace(
            "trace.step",
            phase="llm",
            message="模型输出完成，整理中…",
            payload={"stage": "llm_end"},
        )

    # ---- 工具回调 ----
    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> None:
        tool_name = serialized.get("name", "unknown")
        display = {
            "search_titles": "正在检索剧集元数据…",
            "resolve_title": "正在解析规范化标题与 canonical id…",
            "fetch_availability": "正在查询正版播放平台…",
            "fetch_similar_titles": "正在获取相似剧集推荐…",
            "search_by_actor": "正在查询演员作品…",
            "web_search_tv_info": "正在补充联网搜索…",
            "extract_video_page": "正在解析视频页元数据…",
            "prepare_download": "正在评估下载任务（未写入文件）…",
            "confirm_download": "正在执行已确认的下载…",
            "search_tv_metadata": "正在查询剧集元数据…",
            "search_streaming_platforms": "正在查询正版播放平台…",
            "recommend_similar_tv": "正在寻找相似推荐…",
            "extract_video_info": "正在提取视频信息…",
            "download_video": "正在下载视频…",
        }.get(tool_name, f"正在调用工具: {tool_name}…")
        self._emit_trace(
            "trace.tool_call",
            phase="tool",
            tool=tool_name,
            message=display,
            payload={"input_preview": (input_str or "")[:800]},
        )

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        preview = (output or "")[:400]
        self._emit_trace(
            "trace.tool_result",
            phase="tool",
            message="工具已返回，正在解析…",
            payload={"output_preview": preview},
        )

    # ---- Agent 动作回调 ----
    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        tool_name = getattr(action, "tool", "unknown")
        self._emit_trace(
            "trace.step",
            phase="agent",
            tool=tool_name,
            message=f"Agent 决定调用: {tool_name}",
            payload={},
        )

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        self._emit_trace(
            "trace.step",
            phase="agent",
            message="Agent 推理完成，准备输出结构化结果…",
            payload={"stage": "agent_finish"},
        )

    # ---- 错误回调 ----
    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        err_body: dict[str, Any] = {
            "message": f"模型调用出错: {error!s}",
            "trace_id": self.trace_id,
            "run_id": self.run_id,
        }
        if self._request_id:
            err_body["request_id"] = self._request_id
        if self._session_id:
            err_body["session_id"] = self._session_id
        self._put({"event": "error", "payload": err_body})

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._emit_trace(
            "trace.warning",
            phase="tool",
            message=f"工具调用出错: {error!s}",
            payload={"error": str(error)},
        )


__all__ = ["StreamingStepHandler"]
