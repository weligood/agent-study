"""
下载任务暂存：prepare_download 写入，confirm_download 弹出后执行。

进程内 + TTL，适合单机演示；生产可换 Redis。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingDownload:
    task_id: str
    video_url: str
    quality: str
    created_at: float = field(default_factory=time.time)
    preview: dict[str, Any] = field(default_factory=dict)


class PendingDownloadStore:
    def __init__(self, *, ttl_seconds: float = 1800.0) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._tasks: dict[str, PendingDownload] = {}

    def _purge_locked(self) -> None:
        now = time.time()
        dead = [k for k, v in self._tasks.items() if now - v.created_at > self._ttl]
        for k in dead:
            del self._tasks[k]

    def put(self, video_url: str, quality: str, preview: dict[str, Any]) -> str:
        tid = str(uuid.uuid4())
        with self._lock:
            self._purge_locked()
            self._tasks[tid] = PendingDownload(
                task_id=tid,
                video_url=video_url,
                quality=quality,
                preview=dict(preview),
            )
        return tid

    def pop(self, task_id: str) -> PendingDownload | None:
        with self._lock:
            self._purge_locked()
            return self._tasks.pop(task_id, None)


_store: PendingDownloadStore | None = None


def get_pending_download_store() -> PendingDownloadStore:
    global _store
    if _store is None:
        _store = PendingDownloadStore()
    return _store
