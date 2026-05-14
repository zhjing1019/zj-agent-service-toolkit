"""
问数专用向量库：写入独立 Chroma 目录（与主 RAG 的 chroma_db 分离）。
"""
from __future__ import annotations

import os
import shutil

from langchain_community.vectorstores import Chroma

from config.settings import settings
from core.analytics.build_catalog import build_all_documents


def get_embedding():
    """延迟导入，避免部分脚本在未装 torch 时加载整个 core.rag。"""
    from core.rag import embedding

    return embedding


def rebuild_analytics_index(*, wipe: bool = True) -> int:
    """
    重建问数向量索引。
    :param wipe: True 时删除 ANALYTICS_CHROMA_DIR 下旧数据再全量写入。
    :return: 写入的文档条数。
    """
    docs = build_all_documents()
    db_dir = os.path.abspath(settings.ANALYTICS_CHROMA_DIR)
    os.makedirs(db_dir, exist_ok=True)
    if wipe and os.path.isdir(db_dir):
        shutil.rmtree(db_dir)
        os.makedirs(db_dir, exist_ok=True)
    if not docs:
        return 0
    emb = get_embedding()
    Chroma.from_documents(
        documents=docs,
        embedding=emb,
        persist_directory=db_dir,
    )
    return len(docs)
