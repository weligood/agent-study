"""确定性流水线单元测试（Mock 搜索层，不依赖网络）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.config import clear_settings_cache
from tv_agent.graphs.tv_availability import clear_tv_graph_compile_cache

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tv_agent.pipeline import query_looks_like_video_url, run_availability_pipeline
from tv_agent.domain.schemas import ResultStatus


class TestQueryLooksLikeVideoUrl(unittest.TestCase):
    def test_http(self) -> None:
        self.assertTrue(query_looks_like_video_url("https://www.bilibili.com/video/BV1"))

    def test_plain_title(self) -> None:
        self.assertFalse(query_looks_like_video_url("  狂飙  "))


class TestAvailabilityPipeline(unittest.TestCase):
    def setUp(self) -> None:
        clear_tv_graph_compile_cache()
        clear_settings_cache()

    @patch("tv_agent.graphs.tv_availability._search_similar_web")
    @patch("tv_agent.graphs.tv_availability._search_platforms")
    @patch("tv_agent.graphs.tv_availability._search_metadata")
    def test_success_path(
        self,
        mock_meta: MagicMock,
        mock_plat: MagicMock,
        mock_sim: MagicMock,
    ) -> None:
        mock_meta.return_value = {
            "ok": True,
            "matches": [
                {
                    "id": "web-x-2023",
                    "standard_title": "示例剧",
                    "alternative_titles": [],
                    "release_year": 2023,
                    "region": "中国大陆",
                    "seasons": 1,
                    "episodes": 24,
                }
            ],
            "disambiguation_required": False,
        }
        mock_plat.return_value = {
            "ok": True,
            "platforms": [
                {
                    "platform_name": "爱奇艺",
                    "availability_status": "available",
                    "membership_required": True,
                    "payment_type": "subscription",
                    "offline_download_supported": False,
                    "official_url": "https://www.iqiyi.com/",
                    "logo_url": "",
                    "notes": "测试",
                }
            ],
            "geo_restrictions": "地域限制说明",
        }
        mock_sim.return_value = {
            "ok": True,
            "similar_works": [
                {
                    "standard_title": "另一部剧",
                    "release_year": 2022,
                    "region": "中国大陆",
                    "work_id": "web-y",
                    "brief_note": None,
                }
            ],
        }

        r = run_availability_pipeline("示例剧")
        self.assertEqual(r.result_status, ResultStatus.SUCCESS)
        self.assertEqual(r.standard_title, "示例剧")
        self.assertEqual(len(r.platforms), 1)
        self.assertEqual(r.platforms[0].platform_name, "爱奇艺")
        self.assertEqual(len(r.similar_titles), 1)

    @patch("tv_agent.graphs.tv_availability._search_metadata")
    def test_meta_not_ok(self, mock_meta: MagicMock) -> None:
        mock_meta.return_value = {"ok": False, "message": "API 不可用", "matches": []}
        r = run_availability_pipeline("任意")
        self.assertEqual(r.result_status, ResultStatus.NOT_FOUND)

    @patch("tv_agent.graphs.tv_availability._search_metadata")
    def test_ambiguous_multiple_matches(self, mock_meta: MagicMock) -> None:
        mock_meta.return_value = {
            "ok": True,
            "disambiguation_required": False,
            "matches": [
                {"id": "a", "standard_title": "同名一", "release_year": 2020},
                {"id": "b", "standard_title": "同名二", "release_year": 2021},
            ],
        }
        r = run_availability_pipeline("同名")
        self.assertEqual(r.result_status, ResultStatus.AMBIGUOUS)
        self.assertEqual(len(r.candidate_titles), 2)


if __name__ == "__main__":
    unittest.main()
