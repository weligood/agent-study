"""联网搜索统一后端单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config import Settings, clear_settings_cache
from tv_agent.search.backends import run_unified_web_search


class TestRunUnifiedWebSearch(unittest.TestCase):
    def tearDown(self) -> None:
        clear_settings_cache()

    @patch("tv_agent.search.backends._duckduckgo_backend")
    @patch("tv_agent.search.backends._searxng_backend")
    def test_searxng_empty_falls_back_to_ddg(
        self,
        mock_sx: MagicMock,
        mock_ddg: MagicMock,
    ) -> None:
        mock_sx.return_value = {"organic_results": [], "knowledge_graph": {}}
        mock_ddg.return_value = {"organic_results": [{"title": "t"}], "knowledge_graph": {}}
        cfg = Settings(
            openai_api_key="x",
            searxng_base_url="https://searx.example.org",
            search_fallback_ddg=True,
        )
        out = run_unified_web_search("query", num_results=3, settings=cfg)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(len(out["organic_results"]), 1)
        mock_ddg.assert_called_once()


if __name__ == "__main__":
    unittest.main()
