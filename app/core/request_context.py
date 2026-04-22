"""请求级上下文（供日志与诊断；由中间件写入）。"""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_request_id(value: str | None) -> Token[str | None]:
    return _request_id_ctx.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_ctx.reset(token)
