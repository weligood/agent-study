"""
领域模型：枚举、DTO、查询结果契约。

供 Agent、LangGraph、API 共用；避免在业务包中散落无类型 dict。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OfferAccessType = Literal["subscription", "rent", "buy", "free", "unknown"]


class ResultStatus(str, Enum):
    """查询结果总体状态。"""

    SUCCESS = "success"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    PARTIAL = "partial"


class AvailabilityStatus(str, Enum):
    """平台可用性粗粒度状态。"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PaymentType(str, Enum):
    """付费类型（粗分类）。"""

    FREE = "free"
    SUBSCRIPTION = "subscription"
    RENTAL = "rental"
    PURCHASE = "purchase"
    AD_SUPPORTED = "ad_supported"
    UNKNOWN = "unknown"


class StreamingOffer(BaseModel):
    """统一的平台可看性/购买入口模型（可排序、过滤、解释）。"""

    model_config = ConfigDict(extra="ignore")

    provider: str = Field(..., description="平台或服务商标识")
    region: str | None = Field(default=None, description="地区/分区，未知为 null")
    access_type: OfferAccessType = Field(
        default="unknown",
        description="访问方式：订阅/租/买/免费/未知",
    )
    quality: str | None = Field(default=None, description="画质档位，若未知为 null")
    language: list[str] = Field(default_factory=list, description="音轨语言")
    subtitle: list[str] = Field(default_factory=list, description="字幕语言")
    deeplink: str | None = Field(default=None, description="官方落地页或深链")
    official: bool = Field(default=True, description="是否视为官方入口")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="该条 offer 的可信度 0~1",
    )


class PlatformInfo(BaseModel):
    """单个正版播放平台条目。"""

    platform_name: str = Field(..., description="平台名称")
    availability_status: AvailabilityStatus = Field(
        default=AvailabilityStatus.UNKNOWN,
        description="是否可播/可查",
    )
    membership_required: bool | None = Field(
        default=None,
        description="是否需要会员（未知则为 null）",
    )
    payment_type: PaymentType = Field(
        default=PaymentType.UNKNOWN,
        description="付费模式",
    )
    offline_download_supported: bool | None = Field(
        default=None,
        description="官方是否支持离线缓存/合法下载（未知为 null）",
    )
    official_url: str | None = Field(
        default=None,
        description="官方落地页或片库页（须为官方域名）",
    )
    logo_url: str | None = Field(
        default=None,
        description="平台 Logo URL",
    )
    notes: str | None = Field(default=None, description="补充说明")


class CandidateTitle(BaseModel):
    """同名/近似名消歧候选项。"""

    model_config = ConfigDict(extra="ignore")

    standard_title: str
    release_year: int | None = None
    region: str | None = None
    brief_note: str | None = None
    score: float | None = Field(
        default=None,
        description="解析器给出的同名条目匹配分，可选",
    )
    work_id: str | None = Field(
        default=None,
        description="内部作品标识（canonical），便于多轮对话消歧",
    )


class VideoInfoBrief(BaseModel):
    """视频爬取结果精简信息（嵌入 Agent 输出 JSON）。"""

    model_config = ConfigDict(extra="ignore")

    video_id: str | None = None
    title: str | None = None
    platform: str | None = None
    url: str | None = None
    duration: int | None = None
    duration_display: str | None = None
    uploader: str | None = None
    thumbnail: str | None = None
    view_count: int | None = None
    available_qualities: list[dict[str, Any]] = Field(default_factory=list)


class DownloadResultBrief(BaseModel):
    """视频下载结果精简信息。"""

    model_config = ConfigDict(extra="ignore")

    success: bool = False
    file_path: str | None = None
    file_size: int | None = None
    quality: str | None = None
    message: str | None = None


class QueryResponseMeta(BaseModel):
    """与单次 HTTP 响应对齐的观测摘要（不参与业务推理，仅供客户端与日志关联）。"""

    model_config = ConfigDict(extra="ignore")

    request_id: str | None = None
    trace_id: str | None = None
    run_id: str | None = None
    intent: str | None = None
    execution_mode: str | None = None
    use_agent: bool | None = None
    total_ms: float | None = None


class TVAvailabilityResult(BaseModel):
    """
    Agent 最终应汇总为此结构。

    与业务需求字段对齐；未获取到的字段使用 null 或空列表。
    """

    model_config = ConfigDict(extra="ignore")

    query_title: str = Field(..., description="用户原始输入")
    canonical_work_id: str | None = Field(
        default=None,
        description="规范化后的作品 id，后续片单/历史/推荐应围绕此字段",
    )
    standard_title: str | None = Field(default=None, description="标准剧名")
    alternative_titles: list[str] = Field(default_factory=list)
    release_year: int | None = None
    region: str | None = None
    seasons: int | None = None
    episodes: int | None = None
    candidate_titles: list[CandidateTitle] = Field(
        default_factory=list,
        description="存在歧义时的候选剧集",
    )
    platforms: list[PlatformInfo] = Field(default_factory=list)
    streaming_offers: list[StreamingOffer] = Field(
        default_factory=list,
        description="结构化平台 offer，便于排序与解释",
    )
    similar_titles: list[CandidateTitle] = Field(
        default_factory=list,
        description="推荐的相似剧集",
    )
    geo_restrictions: str | None = Field(
        default=None,
        description="地区限制说明（不给出绕过方法）",
    )
    result_status: ResultStatus = Field(default=ResultStatus.NOT_FOUND)
    confidence: str | None = Field(
        default=None,
        description="置信度或来源可靠性文字说明",
    )
    disclaimer: str = Field(
        default="信息来源于工具查询结果，可能随时间变化，仅供参考。",
        description="准确性提示",
    )
    video_info: VideoInfoBrief | None = Field(
        default=None,
        description="视频爬取结果（仅当查询涉及视频 URL 时）",
    )
    download_result: DownloadResultBrief | None = Field(
        default=None,
        description="视频下载结果（仅当执行了下载时）",
    )
    pipeline_node_trace: list[str] = Field(
        default_factory=list,
        description="LangGraph 节点级轨迹（pipeline 模式），便于与 trace 层对齐展示",
    )
    response_meta: QueryResponseMeta | None = Field(
        default=None,
        description="请求级 trace / 编排摘要，由服务层注入",
    )

    def model_dump_api(self) -> dict[str, Any]:
        """供未来 FastAPI 等直接返回的 dict（枚举转值）。"""
        return self.model_dump(mode="json")


__all__ = [
    "OfferAccessType",
    "ResultStatus",
    "AvailabilityStatus",
    "PaymentType",
    "StreamingOffer",
    "PlatformInfo",
    "CandidateTitle",
    "VideoInfoBrief",
    "DownloadResultBrief",
    "QueryResponseMeta",
    "TVAvailabilityResult",
]
