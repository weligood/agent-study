"""Request-Id 中间件：响应头与 request.state 注入。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.main import app


class TestRequestIdMiddleware(unittest.TestCase):
    def test_echo_client_request_id(self) -> None:
        client = TestClient(app)
        r = client.get("/docs", headers={"X-Request-ID": "unit-test-rid-001"})
        self.assertEqual(r.headers.get("X-Request-ID"), "unit-test-rid-001")

    def test_generates_when_missing(self) -> None:
        client = TestClient(app)
        r = client.get("/docs")
        rid = r.headers.get("X-Request-ID")
        self.assertIsNotNone(rid)
        self.assertGreater(len(rid), 8)


if __name__ == "__main__":
    unittest.main()
