"""
扫描 `tests/evals/*.json` 评测占位文件并汇总用例数。

后续可在此接入：拉取线上/离线结果、与 `cases` 中期望字段比对、输出 junit 或分数。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent / "tests" / "evals"
    if not root.is_dir():
        print("未找到 tests/evals 目录", file=sys.stderr)
        return 1
    total = 0
    for p in sorted(root.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"{p.name}: JSON 无效 — {e}", file=sys.stderr)
            return 1
        cases = data.get("cases") or []
        n = len(cases) if isinstance(cases, list) else 0
        total += n
        desc = (data.get("description") or "").strip()
        print(f"{p.name}: {n} 条 — {desc}")
    print(f"合计: {total} 条（尚未执行断言，仅占位统计）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
