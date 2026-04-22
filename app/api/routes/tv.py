"""电视剧正版渠道查询端点。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.tv import TvQueryRequest
from app.services.tv_service import query_tv_availability, query_by_actor, stream_tv_query
from tv_agent.schemas import TVAvailabilityResult

router = APIRouter()


@router.post(
    "/query",
    response_model=TVAvailabilityResult,
    summary="查询正版播放渠道",
    description="调用 LangChain Agent，返回结构化剧名、平台与合规字段。支持按剧名或演员查询。",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "缺少 OPENAI_API_KEY 等配置，无法调用模型",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "参数错误：剧名和演员不能同时为空",
        },
    },
)
async def post_tv_query(body: TvQueryRequest) -> TVAvailabilityResult:
    # 参数校验
    if body.query_type == "title":
        if not body.title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="按剧名查询时，title 不能为空",
            )
        try:
            return await query_tv_availability(body.title, body.hint, body.session_id)
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e
    else:  # actor
        if not body.actor:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="按演员查询时，actor 不能为空",
            )
        try:
            return await query_by_actor(body.actor, body.hint, body.session_id)
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e


@router.post(
    "/query/stream",
    summary="流式查询正版播放渠道（SSE）",
    description="使用 Server-Sent Events 实时返回 Agent 推理步骤和最终结果。",
)
async def post_tv_query_stream(body: TvQueryRequest):
    # 参数校验
    if body.query_type == "title":
        if not body.title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="按剧名查询时，title 不能为空",
            )
        query = body.title
    else:
        if not body.actor:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="按演员查询时，actor 不能为空",
            )
        query = body.actor

    return StreamingResponse(
        stream_tv_query(body.query_type, query, body.hint, body.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
