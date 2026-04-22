"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/health",
    summary="健康检查",
    response_description="服务可用时返回 status=ok；含中间件时附带 request_id",
)
async def health(request: Request) -> dict[str, str]:
    rid = getattr(request.state, "request_id", None)
    out: dict[str, str] = {"status": "ok"}
    if rid:
        out["request_id"] = rid
    return out
