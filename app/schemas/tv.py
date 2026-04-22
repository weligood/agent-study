"""电视剧查询 API 入参模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TvQueryRequest(BaseModel):
    """POST /api/query 请求体。"""

    query_type: str = Field(
        default="title",
        description="查询类型：title(剧名) 或 actor(演员)"
    )
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="电视剧名称"
    )
    actor: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="演员名称"
    )
    hint: str | None = Field(
        default=None,
        max_length=128,
        description="消歧提示：年份或 work_id",
    )
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description="会话 ID，用于多轮对话记忆",
    )

    @field_validator("query_type")
    @classmethod
    def validate_query_type(cls, v: str) -> str:
        if v not in ("title", "actor"):
            raise ValueError("query_type 必须是 'title' 或 'actor'")
        return v

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None

    @field_validator("actor")
    @classmethod
    def strip_actor(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None

    @field_validator("hint", mode="before")
    @classmethod
    def empty_hint_none(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip() if isinstance(v, str) else v
