"""
命令行：重建问数向量索引（表结构 + knowledge/analytics_business.yaml）。

用法（在项目根目录）：
  python -m core.analytics.reindex
"""
from __future__ import annotations

from db.init_db import init_database
from core.analytics.vector_index import rebuild_analytics_index


def main() -> None:
    init_database()
    n = rebuild_analytics_index(wipe=True)
    print(f"✅ 问数向量索引已重建，共写入 {n} 条文档（表结构 + 业务词典）")


if __name__ == "__main__":
    main()
