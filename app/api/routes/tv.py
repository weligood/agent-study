"""电视剧正版渠道查询端点。"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_request_id
from app.schemas.tv import TvQueryRequest
from app.services.tv_service import query_tv_availability, query_by_actor, stream_tv_query
from tv_agent.domain.schemas import TVAvailabilityResult

router = APIRouter()


def _resolve_query_string(body: TvQueryRequest) -> tuple[str, Literal["title", "actor"]]:
    """校验并返回查询文本与类型，避免 stream / 非 stream 重复分支。"""
    if body.query_type == "title":
        if not body.title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="按剧名查询时，title 不能为空",
            )
        return body.title, "title"
    if not body.actor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="按演员查询时，actor 不能为空",
        )
    return body.actor, "actor"


@router.post(
    "/query",
    response_model=TVAvailabilityResult,
    summary="查询正版播放渠道",
    description=(
        "返回结构化剧名、平台与合规字段；根据配置走 LangGraph 确定性链或 LangChain Agent。"
        "响应体含 `response_meta`（请求 ID、编排意图等）便于观测。"
    ),
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "缺少 OPENAI_API_KEY 等配置，无法调用模型",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "参数错误：剧名和演员不能同时为空",
        },
    },
)
async def post_tv_query(
    body: TvQueryRequest,
    request_id: Annotated[str | None, Depends(get_request_id)],
) -> TVAvailabilityResult:
    rid = request_id
    text, qtype = _resolve_query_string(body)
    try:
        if qtype == "title":
            return await query_tv_availability(
                text,
                body.hint,
                body.session_id,
                preferences=body.preferences,
                request_id=rid,
            )
        return await query_by_actor(
            text,
            body.hint,
            body.session_id,
            preferences=body.preferences,
            request_id=rid,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e


@router.post(
    "/query/stream",
    summary="流式查询正版播放渠道（SSE）",
    description="使用 Server-Sent Events 实时返回推理步骤与最终结果；响应头含 X-Request-ID。",
)
async def post_tv_query_stream(
    body: TvQueryRequest,
    request_id: Annotated[str | None, Depends(get_request_id)],
):
    query, qtype = _resolve_query_string(body)
    rid = request_id
    return StreamingResponse(
        stream_tv_query(
            qtype,
            query,
            body.hint,
            body.session_id,
            preferences=body.preferences,
            request_id=rid,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            **({"X-Request-ID": rid} if rid else {}),
        },
    )
