"""视频页解析与受控下载相关 @tool 实现。"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from tv_agent.download.pending_store import get_pending_download_store
from tv_agent.policy.download_policy import download_policy_message, is_download_enabled

logger = logging.getLogger(__name__)


def tool_extract_video_json(video_url: str, *, log_tag: str) -> str:
    logger.info("%s: url=%r", log_tag, video_url)
    try:
        from video_scraper import extract_info as _extract_info

        info = _extract_info(video_url)
        result = {
            "ok": True,
            "platform": info.platform,
            "video_id": info.id,
            "title": info.title,
            "url": info.url,
            "duration": info.duration,
            "duration_display": f"{info.duration // 60}分{info.duration % 60}秒" if info.duration else None,
            "thumbnail": info.thumbnail,
            "uploader": info.uploader,
            "uploader_id": info.uploader_id,
            "description": (info.description or "")[:200],
            "view_count": info.view_count,
            "like_count": info.like_count,
            "upload_date": info.upload_date,
            "available_qualities": [
                {"quality": f.quality, "width": f.width, "height": f.height, "format": f.ext}
                for f in info.formats if f.url
            ],
            "total_formats": len(info.formats),
            "extra": info.extra,
            "message": f"成功提取 '{info.title}' 的视频信息，共 {len(info.formats)} 个可用格式。",
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("%s 失败: %s", log_tag, e)
        return json.dumps({
            "ok": False,
            "message": f"视频信息提取失败: {e!s}",
            "video_url": video_url,
        }, ensure_ascii=False)


@tool
def extract_video_page(video_url: str) -> str:
    """
    从视频官方页面 URL 提取结构化元数据（标题、时长、清晰度列表等），不下载文件。

    支持：优酷、哔哩哔哩、腾讯视频、爱奇艺。
    """
    return tool_extract_video_json(video_url, log_tag="extract_video_page")


@tool
def extract_video_info(video_url: str) -> str:
    """[兼容] 同 extract_video_page。"""
    return tool_extract_video_json(video_url, log_tag="extract_video_info")


@tool
def prepare_download(video_url: str, quality: str = "highest") -> str:
    """
    下载前置评估：提取元数据、生成 task_id、说明风险；不会写入视频文件。

    真正下载须再调用 `confirm_download(task_id)`（用户确认后执行）。
    """
    logger.info("prepare_download: url=%r quality=%r", video_url, quality)
    if not is_download_enabled():
        return json.dumps(
            {
                "ok": False,
                "policy_blocked": True,
                "task_id": None,
                "message": download_policy_message(),
            },
            ensure_ascii=False,
        )
    try:
        from video_scraper import extract_info as _extract_info

        info = _extract_info(video_url)
        preview = {
            "platform": info.platform,
            "title": info.title,
            "video_id": info.id,
            "duration": info.duration,
            "format_count": len(info.formats),
        }
        task_id = get_pending_download_store().put(video_url, quality, preview)
        official = str(info.platform or "").lower() in (
            "youku", "bilibili", "b站", "qq", "qiyi", "iqiyi", "爱奇艺", "腾讯视频", "优酷",
        )
        return json.dumps(
            {
                "ok": True,
                "task_id": task_id,
                "platform": info.platform,
                "title": info.title,
                "official_portal": official,
                "download_eligible": len(info.formats) > 0,
                "risk_notes": (
                    "下载受版权与平台服务条款约束；仅适用于您有权获取的内容。"
                    "须调用 confirm_download(task_id) 才会写入本地文件。"
                ),
                "requires_user_confirm": True,
                "expires_in_seconds": 1800,
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("prepare_download 失败: %s", e)
        return json.dumps(
            {"ok": False, "task_id": None, "message": f"prepare_download 失败: {e!s}"},
            ensure_ascii=False,
        )


@tool
def confirm_download(task_id: str) -> str:
    """在用户确认后执行真实下载（依赖 prepare_download 返回的 task_id）。"""
    logger.info("confirm_download: task_id=%r", task_id)
    if not is_download_enabled():
        return json.dumps(
            {
                "ok": False,
                "success": False,
                "policy_blocked": True,
                "message": download_policy_message(),
            },
            ensure_ascii=False,
        )
    pending = get_pending_download_store().pop(task_id.strip())
    if pending is None:
        return json.dumps(
            {"ok": False, "success": False, "message": "无效或已过期的 task_id，请重新 prepare_download"},
            ensure_ascii=False,
        )
    try:
        from video_scraper import extract_info as _extract_info
        from video_scraper.downloader import download_video as _download

        info = _extract_info(pending.video_url)
        result = _download(info, quality=pending.quality)
        return json.dumps({"ok": True, **result.model_dump()}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("confirm_download 失败: %s", e)
        return json.dumps(
            {"ok": False, "success": False, "message": f"下载失败: {e!s}"},
            ensure_ascii=False,
        )


@tool
def download_video(video_url: str, quality: str = "highest") -> str:
    """
    下载指定 URL 的视频文件到本地，可选清晰度。

    先提取视频信息，再执行下载。默认选择最高清晰度。
    """
    logger.info("download_video: url=%r quality=%r", video_url, quality)
    if not is_download_enabled():
        return json.dumps(
            {
                "success": False,
                "policy_blocked": True,
                "message": download_policy_message(),
                "video_url": video_url,
            },
            ensure_ascii=False,
        )
    try:
        from video_scraper import extract_info as _extract_info
        from video_scraper.downloader import download_video as _download

        info = _extract_info(video_url)
        result = _download(info, quality=quality)
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("download_video 失败: %s", e)
        return json.dumps({
            "success": False,
            "message": f"视频下载失败: {e!s}",
            "video_url": video_url,
        }, ensure_ascii=False)
