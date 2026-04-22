"""集中注册 API 异常响应，统一附带 `request_id` 便于排障。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _with_request_id(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    rid = getattr(request.state, "request_id", None)
    if rid:
        return {**body, "request_id": rid}
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        body = _with_request_id(request, {"detail": exc.errors()})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        body = _with_request_id(request, {"detail": exc.detail})
        headers = dict(exc.headers) if exc.headers else None
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=headers,
        )
