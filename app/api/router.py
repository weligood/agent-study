"""
聚合 API 路由：统一挂载在 `/api` 前缀下。

OpenAPI 分组与顶层说明见 `app.main` 中 `openapi_tags`、`_OPENAPI_DESCRIPTION`。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health, tv

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(tv.router, tags=["tv"])
