"""
ASGI 入口（兼容旧命令）：`uvicorn api:app`

推荐显式使用：`uvicorn app.main:app`
"""

from app.main import app

__all__ = ["app"]
