"""
FastAPI 应用工厂：生命周期、中间件、路由注册、静态资源与异常处理。

推荐启动：uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from textwrap import dedent

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import ROOT_DIR, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import setup_logging
from app.middleware.correlation import RequestIdMiddleware

STATIC_DIR = ROOT_DIR / "static"

# OpenAPI /docs 首页说明（Markdown）；与 `app.services.tv_service`、`tv_agent.orchestrator` 行为对齐。
_OPENAPI_DESCRIPTION = dedent(
    """
    ## 电视剧正版可查演示服务

    ### 请求追踪
    - 请求头可传 **X-Request-ID**；未传时服务端生成 UUID。
    - 响应头 **`X-Request-ID`** 与 JSON 错误体中的 **`request_id`** 一致；成功时业务结果含 **`response_meta`**。

    ### 查询如何执行
    - **默认 pipeline**：剧名 → LangGraph（元数据 → 平台 → 相似）；演员 → 确定性联网聚合候选。
    - **Agent**：环境变量 **`TV_QUERY_MODE=agent`**，或输入为 **`http://` / `https://` 视频页 URL** 时，走 LangChain 工具编排（解析/下载等）。

    ### 端点一览
    | 方法 | 路径 | 说明 |
    |------|------|------|
    | POST | `/api/query` | 同步 JSON，`TVAvailabilityResult` |
    | POST | `/api/query/stream` | SSE：`trace.*` → `result.final` |
    | POST | `/api/video/extract` | 视频 URL 解析，不下载 |
    | POST | `/api/video/download/prepare` | 创建待确认下载任务 |
    | POST | `/api/video/download/confirm` | 用户确认后执行下载 |
    | GET | `/api/health` | 存活；有中间件时返回 `request_id` |
    """
).strip()

_OPENAPI_TAGS = [
    {"name": "tv", "description": "剧名/演员正版渠道查询；支持 SSE 流式与 `response_meta` 观测字段。"},
    {"name": "health", "description": "服务健康检查。"},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时初始化日志；可在此扩展 DB 连接池等。"""
    settings = get_settings()
    setup_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    origins = settings.cors_origin_list()
    allow_credentials = origins != ["*"]

    app = FastAPI(
        title="TV Legal Availability Agent",
        description=_OPENAPI_DESCRIPTION,
        version="0.4.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=_OPENAPI_TAGS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(api_router, prefix="/api")
    register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    async def spa_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    # 挂载 /vendor 目录：本地化的第三方库（Vue、Element Plus、vue3-sfc-loader）
    app.mount(
        "/vendor",
        StaticFiles(directory=str(STATIC_DIR / "vendor")),
        name="vendor",
    )

    # 挂载 /src 目录：供浏览器加载 main.js 和 .vue 组件
    app.mount(
        "/src",
        StaticFiles(directory=str(STATIC_DIR / "src")),
        name="src",
    )

    # 挂载 /assets 目录：公共静态资源
    app.mount(
        "/assets",
        StaticFiles(directory=str(STATIC_DIR / "assets")),
        name="assets",
    )

    return app


app = create_app()
