"""编排层：意图与执行模式（无网络）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.config import Settings, clear_settings_cache
from tv_agent.orchestrator import (
    ExecutionMode,
    QueryIntent,
    build_execution_plan,
    route_query_intent,
)


class TestOrchestrator(unittest.TestCase):
    def tearDown(self) -> None:
        clear_settings_cache()

    def test_title_plain_is_graph(self) -> None:
        cfg = Settings(openai_api_key="x", tv_query_mode="pipeline")
        p = build_execution_plan("title", "狂飙", settings=cfg)
        self.assertEqual(p.intent, QueryIntent.TITLE_AVAILABILITY)
        self.assertFalse(p.use_agent)
        self.assertEqual(p.execution_mode, ExecutionMode.GRAPH_PIPELINE)

    def test_url_forces_agent_even_pipeline_mode(self) -> None:
        cfg = Settings(openai_api_key="x", tv_query_mode="pipeline")
        p = build_execution_plan("title", "https://www.bilibili.com/video/BV1", settings=cfg)
        self.assertEqual(p.intent, QueryIntent.VIDEO_PAGE)
        self.assertTrue(p.use_agent)

    def test_route_actor(self) -> None:
        self.assertEqual(route_query_intent("actor", "张译"), QueryIntent.ACTOR_WORKS)


if __name__ == "__main__":
    unittest.main()
