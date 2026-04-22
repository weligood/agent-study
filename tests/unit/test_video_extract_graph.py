"""视频提取 LangGraph：路由与单平台调用（Mock，不发起真实请求）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config import clear_settings_cache
from video_scraper.base import ExtractionError
from video_scraper.extract_graph import clear_video_extract_graph_cache, extract_info_via_graph
from video_scraper.models import VideoInfo


class TestVideoExtractGraph(unittest.TestCase):
    def setUp(self) -> None:
        clear_video_extract_graph_cache()
        clear_settings_cache()

    @patch("video_scraper.extract_graph.get_extractor")
    def test_routes_to_single_extractor(self, mock_get: MagicMock) -> None:
        fake = VideoInfo(
            id="BV1test0001",
            title="单元测试视频",
            url="https://www.bilibili.com/video/BV1test0001",
            platform="bilibili",
            formats=[],
        )
        mock_ext = MagicMock()
        mock_ext.extract.return_value = fake
        mock_get.return_value = mock_ext

        out = extract_info_via_graph("https://www.bilibili.com/video/BV1test0001")
        self.assertEqual(out.title, "单元测试视频")
        mock_ext.extract.assert_called_once()

    def test_unknown_url_raises(self) -> None:
        with self.assertRaises(ExtractionError) as ctx:
            extract_info_via_graph("https://example.com/not-a-video")
        self.assertIn("不支持", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
