"""Agent 输出解析与结构化路径的单元测试（不调用真实 LLM）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tv_agent.agent import _agent_text_to_result, _try_parse_agent_output
from tv_agent.domain.schemas import ResultStatus


class TestTryParseAgentOutput(unittest.TestCase):
    def test_plain_json_object(self) -> None:
        text = '{"query_title": "测试剧", "result_status": "not_found", "disclaimer": "仅供参考。"}'
        r = _try_parse_agent_output(text)
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.query_title, "测试剧")
        self.assertEqual(r.result_status, ResultStatus.NOT_FOUND)

    def test_fenced_json(self) -> None:
        text = '说明\n```json\n{"query_title": "A", "result_status": "partial", "disclaimer": "d"}\n```'
        r = _try_parse_agent_output(text)
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.query_title, "A")


class TestAgentTextToResultStructuredFallback(unittest.TestCase):
    @patch("tv_agent.agent._extract_result_via_structured_llm")
    def test_uses_fallback_when_no_json(self, mock_extract: MagicMock) -> None:
        from app.core.config import Settings

        cfg = Settings(
            openai_api_key="sk-test",
            model_name="gpt-4o-mini",
        )
        from tv_agent.domain.schemas import TVAvailabilityResult

        mock_extract.return_value = TVAvailabilityResult(
            query_title="狂飙",
            result_status=ResultStatus.SUCCESS,
            confidence="structured",
            disclaimer="信息可能变更，仅供参考。",
        )
        r = _agent_text_to_result(
            cfg,
            agent_input="剧名：狂飙",
            agent_output="这里没有 JSON，只有自然语言结论。",
            fallback_query="狂飙",
        )
        mock_extract.assert_called_once()
        self.assertEqual(r.query_title, "狂飙")
        self.assertEqual(r.confidence, "structured")


if __name__ == "__main__":
    unittest.main()
