"""下载类工具受策略门约束。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class TestDownloadVideoPolicy(unittest.TestCase):
    @patch("tv_agent.tools.agent_tools.video_tools.is_download_enabled", return_value=False)
    def test_download_video_blocked_when_disabled(self, _m: object) -> None:
        from tv_agent.tools import download_video

        raw = download_video.invoke({"video_url": "https://example.com/v/1", "quality": "highest"})
        payload = json.loads(raw)
        self.assertFalse(payload.get("success", True))
        self.assertTrue(payload.get("policy_blocked"))


if __name__ == "__main__":
    unittest.main()
