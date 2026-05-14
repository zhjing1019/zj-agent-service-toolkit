"""
通过校验的 SQL：外包 LIMIT，只读执行，返回列名与行（JSON 友好）。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Tuple

from sqlalchemy import text

from config.settings import settings
from db.base import engine


def _cell(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def execute_read_only(sql: str, *, row_limit: int | None = None) -> Tuple[list[str], list[list[Any]], bool]:
    lim = row_limit if row_limit is not None else settings.ANALYTICS_ROW_LIMIT
    wrapped = f'SELECT * FROM ({sql}) AS "_analytics_sub" LIMIT {lim + 1}'
    with engine.connect() as conn:
        result = conn.execute(text(wrapped))
        cols = list(result.keys())
        rows_raw = result.fetchall()
    has_more = len(rows_raw) > lim
    rows_cut = rows_raw[:lim]
    rows = [[_cell(c) for c in row] for row in rows_cut]
    return cols, rows, has_more
