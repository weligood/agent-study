"""
向 Meilisearch 索引 `tv_titles`（可通过环境变量 MEILISEARCH_INDEX 覆盖）写入示例剧名文档。

用法（需已启动 Meilisearch，默认 http://127.0.0.1:7700）：
  set MEILISEARCH_URL=http://127.0.0.1:7700
  set MEILISEARCH_API_KEY=   （无鉴权可空）
  python scripts/meili_seed_tv_titles.py

文档字段与 `tv_agent/search/meili_fusion.py` 读取逻辑一致：title, year, region, aliases, notes, url, id。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE = [
    {
        "id": "demo-001",
        "title": "漫长的季节",
        "aliases": "The Long Season",
        "year": 2023,
        "region": "中国大陆",
        "notes": "示例片库条目，可自行替换为正式数据",
        "url": "https://movie.douban.com/subject/35267224/",
    },
    {
        "id": "demo-002",
        "title": "狂飙",
        "aliases": "",
        "year": 2023,
        "region": "中国大陆",
        "notes": "示例",
        "url": "https://movie.douban.com/subject/35465009/",
    },
]


def main() -> int:
    try:
        from meilisearch import Client
    except ImportError:
        print("请先: pip install meilisearch", file=sys.stderr)
        return 1

    url = (os.environ.get("MEILISEARCH_URL") or "http://127.0.0.1:7700").rstrip("/")
    key = os.environ.get("MEILISEARCH_API_KEY") or ""
    index_uid = os.environ.get("MEILISEARCH_INDEX") or "tv_titles"

    client = Client(url, key)
    try:
        client.delete_index(index_uid)
    except Exception:
        pass
    task = client.create_index(index_uid, {"primaryKey": "id"})
    client.wait_for_task(task.task_uid)
    idx = client.index(index_uid)
    idx.update_searchable_attributes(["title", "aliases", "notes", "region"])
    idx.update_filterable_attributes(["year", "region"])
    t = idx.add_documents(SAMPLE)
    client.wait_for_task(t.task_uid)
    print(f"已写入 {len(SAMPLE)} 条示例到 {url} / indexes / {index_uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
