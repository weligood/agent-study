"""工具层单元测试：验证 Web 搜索工具的 JSON envelope 格式。

注意：这些测试需要配置 SEARCH_API_KEY 和 SEARCH_BASE_URL 才能通过。
未配置时工具会返回 ok=False 的结果，测试验证这一行为。
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# 直接运行本文件时，将项目根插入 path，以便导入 `tv_agent`。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tv_agent.tools import (
    search_streaming_platforms,
    search_tv_metadata,
    search_by_actor,
    recommend_similar_tv,
    web_search_tv_info,
)


class TestMetadataToolEnvelope(unittest.TestCase):
    """验证 search_tv_metadata 返回的 JSON 结构正确。"""

    def test_returns_valid_json(self) -> None:
        result = search_tv_metadata.invoke({"query_title": "狂飙", "disambiguation_hint": None})
        payload = json.loads(result)
        self.assertIn("ok", payload)
        self.assertIn("matches", payload)
        self.assertIsInstance(payload["matches"], list)

    def test_has_source_field(self) -> None:
        payload = json.loads(
            search_tv_metadata.invoke({"query_title": "三体", "disambiguation_hint": None})
        )
        self.assertIn("source", payload)


class TestPlatformsToolEnvelope(unittest.TestCase):
    """验证 search_streaming_platforms 返回的 JSON 结构正确。"""

    def test_returns_valid_json(self) -> None:
        result = search_streaming_platforms.invoke({
            "work_id": "web-test",
            "standard_title": "狂飙",
            "release_year": "2023",
        })
        payload = json.loads(result)
        self.assertIn("ok", payload)
        self.assertIn("platforms", payload)
        self.assertIsInstance(payload["platforms"], list)

    def test_platform_has_required_fields(self) -> None:
        payload = json.loads(
            search_streaming_platforms.invoke({
                "work_id": "web-test",
                "standard_title": "狂飙",
                "release_year": "2023",
            })
        )
        if payload.get("ok") and payload.get("platforms"):
            platform = payload["platforms"][0]
            self.assertIn("platform_name", platform)
            self.assertIn("official_url", platform)
            self.assertIn("logo_url", platform)


class TestActorToolEnvelope(unittest.TestCase):
    """验证 search_by_actor 返回的 JSON 结构正确。"""

    def test_returns_valid_json(self) -> None:
        payload = json.loads(
            search_by_actor.invoke({"actor_name": "张译"})
        )
        self.assertIn("ok", payload)
        self.assertIn("related_works", payload)
        self.assertIsInstance(payload["related_works"], list)


class TestSimilarToolEnvelope(unittest.TestCase):
    """验证 recommend_similar_tv 返回的 JSON 结构正确。"""

    def test_returns_valid_json(self) -> None:
        payload = json.loads(
            recommend_similar_tv.invoke({
                "work_id": "web-test",
                "standard_title": "狂飙",
            })
        )
        self.assertIn("ok", payload)
        self.assertIn("similar_works", payload)
        self.assertIsInstance(payload["similar_works"], list)


class TestWebSearchToolEnvelope(unittest.TestCase):
    """验证 web_search_tv_info 返回的 JSON 结构正确。"""

    def test_returns_valid_json(self) -> None:
        payload = json.loads(
            web_search_tv_info.invoke({"search_query": "庆余年 正版平台"})
        )
        self.assertIn("ok", payload)
        self.assertIn("source", payload)


if __name__ == "__main__":
    unittest.main()
