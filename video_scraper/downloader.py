"""
视频下载器：支持分段下载、进度回调、防盗链请求头设置。

参考 yt-dlp downloader 和 Bilibili_video_download 的下载逻辑。
"""

from __future__ import annotations

import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from video_scraper.models import DownloadResult, VideoFormat, VideoInfo

logger = logging.getLogger(__name__)

# SSL 容错（企业网络代理）
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 默认下载目录
_DEFAULT_DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads"

# 下载请求头（防盗链）
_PLATFORM_HEADERS: dict[str, dict[str, str]] = {
    "youku": {
        "Referer": "https://v.youku.com",
        "Origin": "https://v.youku.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Connection": "keep-alive",
    },
    "tencent": {
        "Referer": "https://v.qq.com",
        "Origin": "https://v.qq.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Connection": "keep-alive",
    },
    "iqiyi": {
        "Referer": "https://www.iqiyi.com",
        "Origin": "https://www.iqiyi.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Connection": "keep-alive",
    },
    "bilibili": {
        "Referer": "https://www.bilibili.com",
        "Origin": "https://www.bilibili.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Range": "bytes=0-",
    },
}

# 进度回调类型：(已下载字节, 总字节, 速度bytes/s)
ProgressCallback = Callable[[int, int, float], None]


def _sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符。"""
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = name.strip(". ")
    return name[:200] if name else "untitled"


def _format_size(bytes_count: float) -> str:
    """格式化字节数为可读字符串。"""
    if bytes_count < 1024:
        return f"{bytes_count:.0f}B"
    kb = bytes_count / 1024
    if kb < 1024:
        return f"{kb:.1f}KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.1f}MB"
    gb = mb / 1024
    return f"{gb:.2f}GB"


def download_video(
    info: VideoInfo,
    quality: str = "highest",
    output_dir: str | Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> DownloadResult:
    """
    下载视频到本地。

    :param info: 视频信息（含格式列表）
    :param quality: 清晰度选择：'highest', 'lowest', 或具体标签如 '1080P 高清'
    :param output_dir: 输出目录，默认为项目 downloads/
    :param progress_callback: 进度回调函数
    :return: DownloadResult
    """
    # 选择格式
    fmt = info.select_format(quality)
    if not fmt:
        return DownloadResult(
            success=False,
            message="没有可用的视频格式",
        )

    if not fmt.url:
        return DownloadResult(
            success=False,
            quality=fmt.quality,
            message=f"清晰度 {fmt.quality} 的直链为空（可能需要登录或会员）",
        )

    # 准备输出目录
    download_dir = Path(output_dir) if output_dir else _DEFAULT_DOWNLOAD_DIR
    download_dir.mkdir(parents=True, exist_ok=True)

    # 构建文件名
    safe_title = _sanitize_filename(info.title)
    filename = f"{safe_title}_{info.id}_{fmt.quality}.{fmt.ext}"
    file_path = download_dir / filename

    # 获取平台特有的请求头
    headers = _PLATFORM_HEADERS.get(info.platform, {}).copy()

    logger.info(
        "开始下载: %s -> %s (清晰度: %s)",
        info.title, file_path, fmt.quality,
    )

    start_time = time.time()

    try:
        downloaded_size = _download_file(
            url=fmt.url,
            output_path=file_path,
            headers=headers,
            progress_callback=progress_callback,
        )

        elapsed = time.time() - start_time
        actual_size = file_path.stat().st_size if file_path.exists() else downloaded_size

        logger.info(
            "下载完成: %s (%s, 耗时 %.1f 秒)",
            info.title, _format_size(actual_size), elapsed,
        )

        return DownloadResult(
            success=True,
            file_path=str(file_path),
            file_size=actual_size,
            duration_seconds=round(elapsed, 2),
            quality=fmt.quality,
            message=f"下载完成: {_format_size(actual_size)}, 耗时 {elapsed:.1f} 秒",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.exception("下载失败: %s", e)
        # 清理不完整的文件
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        return DownloadResult(
            success=False,
            duration_seconds=round(elapsed, 2),
            quality=fmt.quality,
            message=f"下载失败: {e}",
        )


def _download_file(
    url: str,
    output_path: Path,
    headers: dict[str, str],
    progress_callback: ProgressCallback | None = None,
    chunk_size: int = 8192,
) -> int:
    """
    底层文件下载：带进度的分块下载。

    :return: 已下载字节数
    """
    opener = urllib.request.build_opener()
    header_list = [(k, v) for k, v in headers.items()]
    opener.addheaders = header_list
    urllib.request.install_opener(opener)

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        start_time = time.time()

        with open(output_path, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                if progress_callback and total_size > 0:
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    progress_callback(downloaded, total_size, speed)

    return downloaded
