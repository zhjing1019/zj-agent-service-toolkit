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


def retrieve_analytics_context(question: str, top_k: int | None = None) -> list[str]:
    k = top_k if top_k is not None else settings.ANALYTICS_TOP_K
    db_dir = os.path.abspath(settings.ANALYTICS_CHROMA_DIR)
    if not os.path.isdir(db_dir) or not os.listdir(db_dir):
        return []
    emb = get_embedding()
    vs = Chroma(persist_directory=db_dir, embedding_function=emb)
    docs = vs.similarity_search(question, k=k)
    return [d.page_content for d in docs]
