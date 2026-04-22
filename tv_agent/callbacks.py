"""
LangChain 回调处理器：将 Agent 推理步骤推送到 asyncio.Queue 供 SSE 端点消费。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class StreamingStepHandler(BaseCallbackHandler):
    """将 Agent 执行过程中的关键步骤写入 asyncio.Queue。"""

    def __init__(self, queue: asyncio.Queue[dict[str, Any] | None]) -> None:
        super().__init__()
        self._queue = queue
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _put(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", time.time())
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        else:
            try:
                self._queue.put_nowait(event)
            except Exception:  # noqa: BLE001
                logger.debug("无法推送事件: %s", event)

    # ---- LLM 回调 ----
    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self._put({"type": "thinking", "message": "AI 正在思考..."})

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self._put({"type": "thinking", "message": "思考完成，正在整理..."})

    # ---- 工具回调 ----
    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> None:
        tool_name = serialized.get("name", "unknown")
        display = {
            "search_tv_metadata": "正在查询剧集元数据...",
            "search_streaming_platforms": "正在查询正版播放平台...",
            "search_by_actor": "正在查询演员作品...",
            "recommend_similar_tv": "正在寻找相似推荐...",
            "web_search_tv_info": "正在从互联网搜索真实信息...",
        }.get(tool_name, f"正在调用工具: {tool_name}...")
        self._put({"type": "tool_call", "tool": tool_name, "message": display})

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        self._put({"type": "tool_result", "message": "工具返回结果，正在分析..."})

    # ---- Agent 动作回调 ----
    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        tool_name = getattr(action, "tool", "unknown")
        self._put({"type": "agent_action", "tool": tool_name, "message": f"决定调用: {tool_name}"})

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        self._put({"type": "agent_finish", "message": "推理完成，输出结果..."})

    # ---- 错误回调 ----
    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._put({"type": "error", "message": f"模型调用出错: {error!s}"})

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._put({"type": "error", "message": f"工具调用出错: {error!s}"})
