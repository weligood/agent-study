"""SearXNG JSON 解析单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tv_agent.search.searxng_parse import parse_searxng_response


class TestParseSearxngResponse(unittest.TestCase):
    def test_results_and_infobox(self) -> None:
        data = {
            "results": [
                {
                    "title": "某剧 豆瓣",
                    "url": "https://movie.douban.com/subject/1/",
                    "content": "2023年首播 共12集",
                    "engine": "duckduckgo",
                }
            ],
            "answers": [{"answer": "这是一部悬疑剧。"}],
            "infoboxes": [
                {
                    "infobox": "某剧",
                    "content": "简介段落",
                    "attributes": [
                        {"label": "First aired", "value": "2023-04-22"},
                        {"label": "Episodes", "value": "12"},
                    ],
                    "urls": [{"title": "豆瓣", "url": "https://movie.douban.com/subject/1/"}],
                }
            ],
            "number_of_results": 99,
        }
        organic, kg = parse_searxng_response(data, num_results=5)
        self.assertEqual(len(organic), 1)
        self.assertIn("引擎", organic[0]["snippet"])
        self.assertEqual(kg.get("title"), "某剧")
        self.assertEqual(kg.get("首播"), "2023-04-22")
        self.assertEqual(kg.get("集数"), "12")
        self.assertIn("description", kg)


if __name__ == "__main__":
    unittest.main()
