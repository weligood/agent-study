"""
FastAPI 应用工厂：生命周期、中间件、路由注册、静态资源与异常处理。

推荐启动：uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import ROOT_DIR, get_settings
from app.core.logging_config import setup_logging

STATIC_DIR = ROOT_DIR / "static"


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
        description="电视剧正版平台查询（合规演示）",
        version="0.3.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

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

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    return app


app = create_app()
