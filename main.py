"""
命令行入口：读取用户剧名，调用 Agent，打印结构化 JSON。

使用：python main.py
"""

from __future__ import annotations

import json
import logging
import sys

from app.core.logging_config import setup_logging
from config import ROOT_DIR, get_settings
from tv_agent.agent import run_availability_query


def _setup_logging() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)


def main() -> int:
    get_settings()
    _setup_logging()
    log = logging.getLogger("cli")

    print("TV Legal Availability Agent — 输入剧名查询正版平台（输入空行退出）")
    try:
        line = input("剧名> ").strip()
    except EOFError:
        return 0
    if not line:
        print("未输入剧名。")
        return 1

    try:
        result = run_availability_query(line)
    except RuntimeError as e:
        log.error("%s", e)
        print(f"配置错误: {e}", file=sys.stderr)
        env_file = ROOT_DIR / ".env"
        print(
            f"请在本机创建或编辑: {env_file}\n"
            "  1) 可复制 .env.example 为 .env\n"
            "  2) 填写 OPENAI_API_KEY（以及使用兼容网关时的 OPENAI_BASE_URL、MODEL_NAME）\n"
            "  3) 保存后重新运行 python main.py",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130

    print(json.dumps(result.model_dump_api(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
