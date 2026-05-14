"""
从问数 Chroma 中检索与问题相关的词典/表结构片段。
"""
from __future__ import annotations

import os

from langchain_community.vectorstores import Chroma

from config.settings import settings


def get_embedding():
    from core.rag import embedding

    return embedding


# 中文问数常见词：与主问句拼接成第二次检索，减轻「长问句语义漂移」导致召不回业务块的问题
_RETRIEVAL_QUERY_BOOST = (
    " 徐汇 浦东 旗舰院 分院 branch_code 日营收 营收 revenue 订单 order_count "
    "ma_daily_sales_stat ma_branch stat_date 按月 5月"
)


def retrieve_analytics_context(question: str, top_k: int | None = None) -> list[str]:
    k = top_k if top_k is not None else settings.ANALYTICS_TOP_K
    db_dir = os.path.abspath(settings.ANALYTICS_CHROMA_DIR)
    if not os.path.isdir(db_dir) or not os.listdir(db_dir):
        return []
    emb = get_embedding()
    vs = Chroma(persist_directory=db_dir, embedding_function=emb)
    # 两次检索合并去重：第一次用原问题，第二次用「原问题 + 领域关键词」提高召回业务 YAML
    n1 = max(k, 6)
    n2 = max(6, k // 2 + 4)
    docs1 = vs.similarity_search(question, k=n1)
    docs2 = vs.similarity_search(question.strip() + _RETRIEVAL_QUERY_BOOST, k=n2)
    seen: set[str] = set()
    out: list[str] = []
    for d in docs1 + docs2:
        key = d.page_content[:400]
        if key in seen:
            continue
        seen.add(key)
        out.append(d.page_content)
        if len(out) >= k:
            break
    return out
