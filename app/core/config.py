"""
应用配置（pydantic-settings）。

与 FastAPI 推荐方式一致：类型安全、可文档化、自动从环境变量与 .env 加载。
项目根目录 = `Path(__file__).parents[2]`（即 `app/core/config.py` 上溯至仓库根）。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    model_name: str = Field(default="gpt-4o-mini", description="Agent 主对话模型名")
    extractor_model_name: str | None = Field(
        default=None,
        description="结构化抽取专用模型；未设置则与 model_name 相同（可改为更小模型以省成本）",
    )
    openai_max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="OpenAI 兼容客户端对可重试错误的最大重试次数",
    )
    agent_parallel_tool_calls: bool = Field(
        default=True,
        description="是否向 API 声明 parallel_tool_calls（部分自建网关不支持时可关）",
    )
    searxng_base_url: str | None = Field(
        default=None,
        description=(
            "SearXNG 实例根 URL，如 https://searx.example.org（不要尾斜杠）；"
            "可用逗号或分号配置多个实例，联网搜索会按顺序尝试"
        ),
    )
    search_fallback_ddg: bool = Field(
        default=True,
        description="SearXNG 未配置、不可用或无结果时，是否回退到 DuckDuckGo（无 API Key）",
    )
    meilisearch_url: str | None = Field(
        default=None,
        description="Meilisearch 服务根 URL，如 http://127.0.0.1:7700；配置后片库结果前置与联网搜索融合",
    )
    meilisearch_api_key: str | None = Field(
        default=None,
        description="Meilisearch Master Key；本地无鉴权可留空",
    )
    meilisearch_index: str = Field(
        default="tv_titles",
        description="剧名片库索引 UID",
    )
    request_timeout_seconds: float = Field(default=60.0, ge=1.0, le=600.0)
    agent_max_iterations: int = Field(default=12, ge=1, le=64)
    graph_node_max_retries: int = Field(
        default=2,
        ge=1,
        le=5,
        description="LangGraph 各搜索节点遇到可重试类失败时的最大尝试次数",
    )
    tv_query_mode: Literal["pipeline", "agent"] = Field(
        default="pipeline",
        description="pipeline=确定性检索链（推荐：更快、结构化稳定）；agent=LangChain 工具编排（多轮、适合视频 URL/复杂追问）",
    )
    tv_download_enabled: bool = Field(
        default=False,
        description="策略门：为 true 时才允许 prepare_download/confirm_download 真正注册任务与落盘",
    )
    session_ttl_minutes: int = Field(default=30, ge=1, le=1440, description="会话记忆过期时间（分钟）")
    log_level: str = Field(default="INFO")
    # CORS：逗号分隔来源；单个 * 表示全部（仅建议开发环境）
    cors_origins: str = Field(default="*", description="CORS 允许来源，逗号分隔")

    @field_validator(
        "openai_api_key",
        "openai_base_url",
        "extractor_model_name",
        "searxng_base_url",
        "meilisearch_url",
        "meilisearch_api_key",
        mode="before",
    )
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

    def searxng_base_urls(self) -> list[str]:
        """返回去重后的 SearXNG 实例列表，支持逗号或分号分隔。"""
        raw = (self.searxng_base_url or "").strip()
        if not raw:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for part in raw.replace(";", ",").split(","):
            base = part.strip().rstrip("/")
            if base and base not in seen:
                seen.add(base)
                out.append(base)
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例，与原先 `config.get_settings` 语义一致。"""
    return Settings()


def clear_settings_cache() -> None:
    """测试或热重载前可调用，使下次 `get_settings()` 重新读环境。"""
    get_settings.cache_clear()
    try:
        from tv_agent.llm_client import clear_llm_caches

        clear_llm_caches()
    except ImportError:
        pass
    try:
        from tv_agent.graphs.tv_availability import clear_tv_graph_compile_cache

        clear_tv_graph_compile_cache()
    except ImportError:
        pass
    try:
        from video_scraper.extract_graph import clear_video_extract_graph_cache

        clear_video_extract_graph_cache()
    except ImportError:
        pass
