"""API 层可复用依赖（请求上下文等）。"""

from __future__ import annotations

from fastapi import Request


def get_request_id(request: Request) -> str | None:
    """由 `RequestIdMiddleware` 写入的 `X-Request-ID` / 生成值；无中间件时为 None。"""
    return getattr(request.state, "request_id", None)
