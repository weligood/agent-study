"""HTTPException 响应体携带 request_id（与中间件、register_exception_handlers 一致）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.exception_handlers import register_exception_handlers
from app.middleware.correlation import RequestIdMiddleware


class TestHttpExceptionRequestId(unittest.TestCase):
    def test_http_exception_json_includes_request_id(self) -> None:
        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)
        register_exception_handlers(app)

        @app.get("/boom")
        def _boom() -> None:
            raise HTTPException(status_code=402, detail="payment required")

        client = TestClient(app)
        r = client.get("/boom")
        self.assertEqual(r.status_code, 402)
        body = r.json()
        self.assertEqual(body.get("detail"), "payment required")
        self.assertTrue(body.get("request_id"))
        self.assertEqual(r.headers.get("X-Request-ID"), body.get("request_id"))


if __name__ == "__main__":
    unittest.main()
