"""
进程内会话记忆存储：为多轮对话提供 LangChain Memory 实例。

生产环境建议替换为 Redis / 数据库持久化方案。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from langchain_classic.memory import ConversationBufferWindowMemory

from config import get_settings

logger = logging.getLogger(__name__)


def _get_session_ttl() -> float:
    """从配置读取会话过期时间（秒）。"""
    try:
        return get_settings().session_ttl_minutes * 60
    except Exception:  # noqa: BLE001
        return 30 * 60  # 默认 30 分钟


class _SessionEntry:
    __slots__ = ("memory", "last_access")

    def __init__(self, memory: ConversationBufferWindowMemory) -> None:
        self.memory = memory
        self.last_access = time.time()

    def touch(self) -> None:
        self.last_access = time.time()


class SessionStore:
    """线程安全的进程内会话存储。"""

    def __init__(self, window_k: int = 10, ttl: float | None = None) -> None:
        self._store: dict[str, _SessionEntry] = {}
        self._lock = threading.Lock()
        self._window_k = window_k
        self._ttl = ttl or _get_session_ttl()

    def get_or_create(self, session_id: str) -> ConversationBufferWindowMemory:
        """获取或创建指定会话的 Memory 实例。"""
        with self._lock:
            self._cleanup_expired()
            entry = self._store.get(session_id)
            if entry is None:
                mem = ConversationBufferWindowMemory(
                    k=self._window_k,
                    memory_key="chat_history",
                    return_messages=True,
                )
                entry = _SessionEntry(mem)
                self._store[session_id] = entry
                logger.info("创建新会话: %s", session_id)
            entry.touch()
            return entry.memory

    def clear(self, session_id: str) -> None:
        """清除指定会话记忆。"""
        with self._lock:
            entry = self._store.pop(session_id, None)
            if entry:
                logger.info("清除会话: %s", session_id)

    def _cleanup_expired(self) -> None:
        """清理过期会话。"""
        now = time.time()
        expired = [
            sid for sid, entry in self._store.items()
            if now - entry.last_access > self._ttl
        ]
        for sid in expired:
            del self._store[sid]
            logger.info("会话过期已清理: %s", sid)


# 全局单例
session_store = SessionStore()


def get_or_create_memory(session_id: str | None) -> ConversationBufferWindowMemory | None:
    """根据 session_id 获取 Memory；无 session_id 则返回 None（无记忆模式）。"""
    if not session_id:
        return None
    return session_store.get_or_create(session_id)


def clear_memory(session_id: str) -> None:
    """清空指定会话。"""
    session_store.clear(session_id)
