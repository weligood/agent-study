"""
命令行入口：读取用户剧名，按配置调用确定性流水线或 Agent，打印结构化 JSON。

使用：python main.py
"""

from __future__ import annotations

import json
import logging
import sys

from app.core.logging_config import setup_logging
from config import ROOT_DIR, get_settings
from tv_agent.agent import run_availability_query
from tv_agent.pipeline import query_looks_like_video_url, run_availability_pipeline


def _setup_logging() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)


def main() -> int:
    settings = get_settings()
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

    use_pipeline = settings.tv_query_mode == "pipeline" and not query_looks_like_video_url(line)

    try:
        if use_pipeline:
            result = run_availability_pipeline(line)
        else:
            if not settings.openai_api_key:
                raise RuntimeError("缺少 OPENAI_API_KEY，无法在 agent 模式下初始化对话模型。")
            result = run_availability_query(line)
    except RuntimeError as e:
        log.error("%s", e)
        print(f"配置错误: {e}", file=sys.stderr)
        env_file = ROOT_DIR / ".env"
        print(
            f"请在本机创建或编辑: {env_file}\n"
            "  1) 可复制 .env.example 为 .env\n"
            "  2) pipeline 模式仅需搜索 API；agent / 视频 URL 需填写 OPENAI_API_KEY（及可选 OPENAI_BASE_URL、MODEL_NAME）\n"
            "  3) 可选 TV_QUERY_MODE=pipeline（默认）或 agent\n"
            "  4) 保存后重新运行 python main.py",
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
