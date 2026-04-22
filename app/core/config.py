"""
应用配置（pydantic-settings）。

与 FastAPI 推荐方式一致：类型安全、可文档化、自动从环境变量与 .env 加载。
项目根目录 = `Path(__file__).parents[2]`（即 `app/core/config.py` 上溯至仓库根）。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# agent-study/
ROOT_DIR: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """全局设置；字段名小写，对应环境变量为大写 SNAKE_CASE。"""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str | None = Field(default=None, description="OpenAI 兼容 API Key")
    openai_base_url: str | None = Field(default=None, description="自定义网关 Base URL")
    model_name: str = Field(default="gpt-4o-mini", description="对话模型名")
    search_api_key: str | None = Field(default=None)
    search_base_url: str | None = Field(default=None)
    request_timeout_seconds: float = Field(default=60.0, ge=1.0, le=600.0)
    agent_max_iterations: int = Field(default=12, ge=1, le=64)
    session_ttl_minutes: int = Field(default=30, ge=1, le=1440, description="会话记忆过期时间（分钟）")
    log_level: str = Field(default="INFO")
    # CORS：逗号分隔来源；单个 * 表示全部（仅建议开发环境）
    cors_origins: str = Field(default="*", description="CORS 允许来源，逗号分隔")

    @field_validator("openai_api_key", "openai_base_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [p.strip() for p in raw.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例，与原先 `config.get_settings` 语义一致。"""
    return Settings()


def clear_settings_cache() -> None:
    """测试或热重载前可调用，使下次 `get_settings()` 重新读环境。"""
    get_settings.cache_clear()
