"""校验失败时响应体携带 request_id（与中间件一致）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.main import app


class TestValidationRequestId(unittest.TestCase):
    def test_query_invalid_type_returns_request_id(self) -> None:
        client = TestClient(app)
        r = client.post("/api/query", json={"query_type": "not_a_valid_type", "title": "x"})
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertIn("detail", body)
        self.assertIn("request_id", body)
        self.assertTrue(body["request_id"])


if __name__ == "__main__":
    unittest.main()
