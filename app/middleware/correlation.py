"""为每个请求注入 `request.state.request_id`，并回写响应头便于客户端与日志关联。"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import reset_request_id, set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    - 若请求头带 `X-Request-ID` / `X-Request-Id`，则原样采用（经 strip 与非空校验）。
    - 否则生成 UUID。
    - 响应头写入 `X-Request-ID`，与追踪里的 request_id 对齐。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        raw = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        rid = (raw or "").strip() or str(uuid.uuid4())
        request.state.request_id = rid
        token = set_request_id(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            reset_request_id(token)
