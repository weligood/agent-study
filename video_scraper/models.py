"""
视频信息数据模型：标准化所有提取器的输出格式。

参考 yt-dlp 的 info_dict 结构设计。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VideoFormat(BaseModel):
    """单个视频格式/清晰度选项。"""

    url: str = Field(..., description="视频流直链")
    ext: str = Field(default="mp4", description="文件扩展名")
    quality: str = Field(default="unknown", description="清晰度标签，如 1080p、720p")
    quality_number: int = Field(default=0, description="清晰度数值，用于排序（越大越清晰）")
    width: int | None = Field(default=None, description="视频宽度")
    height: int | None = Field(default=None, description="视频高度")
    filesize: int | None = Field(default=None, description="文件大小（字节）")
    format_note: str | None = Field(default=None, description="格式备注")


class VideoInfo(BaseModel):
    """提取器返回的标准化视频信息。"""

    id: str = Field(..., description="视频在平台上的唯一标识")
    title: str = Field(..., description="视频标题")
    url: str = Field(..., description="视频页面 URL")
    platform: str = Field(..., description="来源平台名称，如 bilibili")
    duration: int | None = Field(default=None, description="视频时长（秒）")
    thumbnail: str | None = Field(default=None, description="封面图 URL")
    uploader: str | None = Field(default=None, description="上传者/UP主名称")
    uploader_id: str | None = Field(default=None, description="上传者 ID")
    description: str | None = Field(default=None, description="视频简介")
    view_count: int | None = Field(default=None, description="播放量")
    like_count: int | None = Field(default=None, description="点赞数")
    upload_date: str | None = Field(default=None, description="上传日期 YYYY-MM-DD")
    formats: list[VideoFormat] = Field(default_factory=list, description="可用的视频格式列表")
    subtitles: dict[str, str] | None = Field(default=None, description="字幕 {语言: URL}")
    extra: dict | None = Field(default=None, description="平台特有的额外信息")

    def best_format(self) -> VideoFormat | None:
        """返回最高清晰度的格式。"""
        if not self.formats:
            return None
        return max(self.formats, key=lambda f: f.quality_number)

    def select_format(self, quality: str = "highest") -> VideoFormat | None:
        """根据清晰度标签选择格式；'highest' 取最高，'lowest' 取最低。"""
        if not self.formats:
            return None
        if quality == "highest":
            return self.best_format()
        if quality == "lowest":
            return min(self.formats, key=lambda f: f.quality_number)
        # 精确匹配
        for f in self.formats:
            if f.quality == quality:
                return f
        # 未匹配到则返回最高清晰度
        return self.best_format()


class DownloadResult(BaseModel):
    """下载结果。"""

    success: bool = Field(..., description="是否下载成功")
    file_path: str | None = Field(default=None, description="下载文件的本地路径")
    file_size: int | None = Field(default=None, description="文件大小（字节）")
    duration_seconds: float | None = Field(default=None, description="下载耗时（秒）")
    quality: str | None = Field(default=None, description="下载的清晰度")
    message: str = Field(default="", description="状态消息")
