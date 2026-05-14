"""
查看问数向量库（chroma_analytics）里是否已有索引、有多少条、按 kind 分布及样例。

用法（项目根目录）：
  python -m core.analytics.inspect_index
  python -m core.analytics.inspect_index --query 徐汇院日营收
"""
from __future__ import annotations

import argparse
import os
from collections import Counter

from config.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="检查问数 Chroma 索引")
    parser.add_argument(
        "--query",
        type=str,
        default="",
        help="可选：给定一句话做相似检索，看召回的前 5 条摘要",
    )
    args = parser.parse_args()

    db_dir = os.path.abspath(settings.ANALYTICS_CHROMA_DIR)
    print(f"ANALYTICS_CHROMA_DIR = {db_dir}")
    if not os.path.isdir(db_dir) or not os.listdir(db_dir):
        print("❌ 目录不存在或为空：请先运行 python -m core.analytics.reindex")
        return

    from core.analytics.vector_index import get_embedding
    from langchain_community.vectorstores import Chroma

    emb = get_embedding()
    vs = Chroma(persist_directory=db_dir, embedding_function=emb)
    coll = vs._collection
    total = coll.count()
    print(f"✅ 向量库文档条数（约等于建索引时的块数）: {total}")

    batch = coll.get(limit=min(500, max(total, 1)), include=["metadatas", "documents"])
    metas = batch.get("metadatas") or []
    docs = batch.get("documents") or []
    kinds = Counter((m or {}).get("kind", "?") for m in metas)
    print("按 metadata.kind 分布（本批最多 500 条）:")
    for k, c in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k}: {c}")

    tables = {m.get("table") for m in metas if (m or {}).get("kind") == "table_schema" and m.get("table")}
    if tables:
        print(f"\n本批中出现的表名（table_schema）共 {len(tables)} 个，例如:")
        for t in sorted(tables)[:15]:
            print(f"  - {t}")
        if len(tables) > 15:
            print(f"  ... 另有 {len(tables) - 15} 个")

    print("\n--- 随机样例 2 条（前 400 字）---")
    for i, text in enumerate(docs[:2]):
        meta = metas[i] if i < len(metas) else {}
        print(f"\n[样例 {i+1}] metadata={meta}\n{text[:400]}...")

    q = (args.query or "").strip()
    if q:
        print(f"\n--- 相似检索 query={q!r}（top 5）---")
        hits = vs.similarity_search(q, k=5)
        for i, d in enumerate(hits):
            head = (d.page_content or "")[:300].replace("\n", " ")
            print(f"  {i+1}. kind={(d.metadata or {}).get('kind')} table={(d.metadata or {}).get('table')} | {head}...")


if __name__ == "__main__":
    main()
