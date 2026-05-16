"""
问数专用向量库：写入独立 Chroma 目录（与主 RAG 的 chroma_db 分离）。
"""
from __future__ import annotations

import os
import shutil

from langchain_community.vectorstores import Chroma

from config.settings import settings
from core.analytics.build_catalog import build_all_documents

# 获取嵌入
def get_embedding():
    """延迟导入，避免部分脚本在未装 torch 时加载整个 core.rag。"""
    from core.rag import embedding

    return embedding

# 重建问数专用向量库
def rebuild_analytics_index(*, wipe: bool = True) -> int:
    """
    重建问数向量索引。
    :param wipe: True 时删除 ANALYTICS_CHROMA_DIR 下旧数据再全量写入。
    :return: 写入的文档条数。
    """
    # 构建所有文档
    docs = build_all_documents()
    # 获取问数专用向量库目录
    db_dir = os.path.abspath(settings.ANALYTICS_CHROMA_DIR)
    # 创建问数专用向量库目录
    os.makedirs(db_dir, exist_ok=True)
    # 如果 wipe 为 True 且问数专用向量库目录存在，则删除问数专用向量库目录
    if wipe and os.path.isdir(db_dir):
        # 删除问数专用向量库目录
        shutil.rmtree(db_dir)
        os.makedirs(db_dir, exist_ok=True)
    if not docs:
        return 0
    emb = get_embedding()
    # 写入问数专用向量库
    Chroma.from_documents(
        documents=docs,
        embedding=emb,
        persist_directory=db_dir,
    )
    return len(docs)
