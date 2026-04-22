"""集中配置根 logger 格式，供 CLI 与 uvicorn 共用。"""

from __future__ import annotations

import logging
import sys

from app.core.request_context import get_request_id


class RequestIdFilter(logging.Filter):
    """为每条日志注入 `record.request_id`（无请求上下文时为 `-`）。"""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            record.request_id = get_request_id() or "-"
        except Exception:  # noqa: BLE001
            record.request_id = "-"
        return True


_REQUEST_ID_FILTER = RequestIdFilter()
_LOG_FMT = "%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
_configured = False


def setup_logging(level_name: str = "INFO") -> None:
    global _configured  # noqa: PLW0603
    level = getattr(logging, level_name.upper(), logging.INFO)
    root = logging.getLogger()

    def _ensure_handler(h: logging.Handler) -> None:
        if not any(isinstance(f, RequestIdFilter) for f in h.filters):
            h.addFilter(_REQUEST_ID_FILTER)
        h.setFormatter(logging.Formatter(_LOG_FMT))
        h.setLevel(level)

    if root.handlers:
        for h in root.handlers:
            _ensure_handler(h)
        root.setLevel(level)
        _configured = True
        return

    if _configured:
        root.setLevel(level)
        return

    h = logging.StreamHandler(sys.stdout)
    _ensure_handler(h)
    root.addHandler(h)
    root.setLevel(level)
    _configured = True
