"""LangGraph SqliteSaver 单例：为完整工作流图提供检查点持久化（断点续跑）。"""
from __future__ import annotations

import atexit
import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from config.settings import settings

_conn: sqlite3.Connection | None = None
_saver: SqliteSaver | None = None


def get_graph_checkpointer() -> SqliteSaver:
    """返回进程内单例 SqliteSaver；连接在进程退出时关闭。"""
    global _conn, _saver
    if _saver is not None:
        return _saver

    path = settings.LANGGRAPH_CHECKPOINT_SQLITE_PATH
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    _conn = sqlite3.connect(path, check_same_thread=False)
    _saver = SqliteSaver(_conn)

    def _close() -> None:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass

    atexit.register(_close)
    return _saver
