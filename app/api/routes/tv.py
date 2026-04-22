"""电视剧正版渠道查询端点。"""

from __future__ import annotations

import json
from typing import Annotated, Literal

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_request_id
from app.schemas.tv import (
    TvQueryRequest,
    VideoDownloadConfirmRequest,
    VideoDownloadPrepareRequest,
    VideoExtractRequest,
)
from app.services.tv_service import query_tv_availability, query_by_actor, stream_tv_query
from config import get_settings
from tv_agent.domain.schemas import TVAvailabilityResult
from tv_agent.tools.agent_tools.video_tools import confirm_download, prepare_download, tool_extract_video_json

router = APIRouter()


def _parse_tool_json(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"ok": False, "message": raw}
    return parsed if isinstance(parsed, dict) else {"ok": False, "message": str(parsed)}


def _video_extract_payload(video_url: str) -> dict:
    payload = _parse_tool_json(tool_extract_video_json(video_url, log_tag="api_extract_video"))
    if payload.get("ok"):
        payload = {
            "ok": True,
            "video_info": {
                "video_id": payload.get("video_id"),
                "title": payload.get("title"),
                "platform": payload.get("platform"),
                "url": payload.get("url") or video_url,
                "duration": payload.get("duration"),
                "duration_display": payload.get("duration_display"),
                "uploader": payload.get("uploader"),
                "thumbnail": payload.get("thumbnail"),
                "view_count": payload.get("view_count"),
                "available_qualities": payload.get("available_qualities") or [],
            },
            "message": payload.get("message"),
        }
    payload["download_enabled"] = get_settings().tv_download_enabled
    return payload


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


@router.post(
    "/video/extract",
    summary="解析视频页面",
    description="直接解析官方视频 URL，返回标题、平台、时长和可用清晰度；不下载文件。",
)
async def post_video_extract(body: VideoExtractRequest) -> dict:
    return await anyio.to_thread.run_sync(lambda: _video_extract_payload(body.video_url))


@router.post(
    "/video/download/prepare",
    summary="准备下载任务",
    description="提取视频信息并创建待确认任务；真正写入文件前必须调用 confirm。",
)
async def post_video_download_prepare(body: VideoDownloadPrepareRequest) -> dict:
    raw = await anyio.to_thread.run_sync(
        lambda: prepare_download.invoke({"video_url": body.video_url, "quality": body.quality})
    )
    payload = _parse_tool_json(raw)
    payload["download_enabled"] = get_settings().tv_download_enabled
    return payload


@router.post(
    "/video/download/confirm",
    summary="确认下载任务",
    description="用户确认后执行下载；依赖 prepare 接口返回的 task_id。",
)
async def post_video_download_confirm(body: VideoDownloadConfirmRequest) -> dict:
    raw = await anyio.to_thread.run_sync(lambda: confirm_download.invoke({"task_id": body.task_id}))
    payload = _parse_tool_json(raw)
    payload["download_enabled"] = get_settings().tv_download_enabled
    return payload
