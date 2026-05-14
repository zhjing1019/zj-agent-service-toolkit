"""
从 SQLite 反射 ma_* 表结构，并合并 YAML 业务词典，生成可写入向量库的 LangChain Document 列表。
"""
from __future__ import annotations

import os
from typing import Any

import yaml
from langchain_core.documents import Document
from sqlalchemy import text

from config.settings import settings
from db.base import engine


def load_business_entries() -> list[dict[str, Any]]:
    path = os.path.abspath(settings.ANALYTICS_BUSINESS_YAML)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("entries") or [])


def reflect_ma_tables() -> list[Document]:
    docs: list[Document] = []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name LIKE :pfx ORDER BY name"
            ),
            {"pfx": f"{settings.ANALYTICS_ALLOWED_TABLE_PREFIX}%"},
        ).fetchall()
        for (tbl,) in rows:
            cols = conn.execute(text(f'PRAGMA table_info("{tbl}")')).fetchall()
            # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
            col_lines = [f"  - {r[1]} ({r[2] or 'ANY'})" for r in cols]
            body = (
                f"数据库表 `{tbl}`（SQLite）。\n"
                f"列定义：\n" + "\n".join(col_lines) + "\n"
                f"用途：医美销售演示域；写 SQL 时请使用英文列名与表名。"
            )
            docs.append(
                Document(
                    page_content=body,
                    metadata={
                        "kind": "table_schema",
                        "table": tbl,
                        "source": "sqlite_pragma",
                    },
                )
            )
    return docs


def load_business_documents() -> list[Document]:
    out: list[Document] = []
    for i, ent in enumerate(load_business_entries()):
        eid = str(ent.get("id") or f"entry_{i}")
        title = str(ent.get("title") or eid)
        content = str(ent.get("content") or "").strip()
        if not content:
            continue
        page = f"【{title}】\n{eid}\n{content}"
        out.append(
            Document(
                page_content=page,
                metadata={
                    "kind": "business_rule",
                    "entry_id": eid,
                    "title": title,
                    "source": settings.ANALYTICS_BUSINESS_YAML,
                },
            )
        )
    return out


def build_all_documents() -> list[Document]:
    """表结构文档 + 业务 YAML 文档。"""
    return reflect_ma_tables() + load_business_documents()
