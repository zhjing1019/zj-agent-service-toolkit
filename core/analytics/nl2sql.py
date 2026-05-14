"""
编排：检索词典 → LLM 生成 SQL → sql_guard 校验 → 只读执行 → 可选自然语言小结。
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import create_engine, text

from config.settings import settings
from core.analytics.executor import execute_read_only
from core.analytics.retrieve import retrieve_analytics_context
from core.analytics.sql_guard import validate_analytics_sql
from core.llm import resilient_invoke


def _db_engine():
    return create_engine(
        f"sqlite:///{settings.SQLITE_PATH}",
        connect_args={"check_same_thread": False},
    )


def build_compact_schema() -> str:
    """当前库里所有 ma_* 表的一行列清单，供模型对齐列名。"""
    lines: list[str] = []
    pfx = settings.ANALYTICS_ALLOWED_TABLE_PREFIX.replace("%", "")
    eng = _db_engine()
    with eng.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name LIKE :pfx ORDER BY name"
            ),
            {"pfx": f"{pfx}%"},
        ).fetchall()
        for (tbl,) in tables:
            cols = conn.execute(text(f'PRAGMA table_info("{tbl}")')).fetchall()
            names = [c[1] for c in cols]
            lines.append(f"{tbl}: " + ", ".join(names))
    return "\n".join(lines) if lines else "(无 ma_* 表，请先 init_database)"


def _extract_json_object(text: str) -> dict[str, Any]:
    s = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        s = m.group(1).strip()
    return json.loads(s)


def _nl2sql_prompt(question: str, rag_block: str, schema_block: str) -> str:
    return f"""你是 SQLite 报表助手。用户问题如下。
请只输出 **一个 JSON 对象**（不要 Markdown、不要多余解释），格式严格为：
{{"sql":"...","notes":"一句话说明假设"}}

硬性要求：
1. 只能写 **一条** SELECT（可用 WITH 公用表表达式）。
2. 只能查询物理表名以「{settings.ANALYTICS_ALLOWED_TABLE_PREFIX}」开头的表。
3. 列名、表名必须与下方「表结构摘要」一致，不要臆造列。
4. 若用户未指定行数，请自行 LIMIT（建议不超过 {settings.ANALYTICS_ROW_LIMIT}）。

【业务词典与推理（从向量库检索，可能不完整）】
{rag_block}

【表结构摘要（列名必须完全一致）】
{schema_block}

【用户问题】
{question}
"""


def _summary_prompt(question: str, sql: str, preview: str) -> str:
    return f"""用户问题：{question}
已执行 SQL：{sql}
查询结果预览（前几行文本化）：{preview}

请用 2～5 句中文总结回答用户；数字必须与预览一致，不得编造。
若结果为空，说明无数据并给出可能原因（时间范围、分院条件等）。
"""


def run_nl_query(question: str) -> dict[str, Any]:
    """
    完整问数流水线。
    返回 dict: ok, sql, validation_error, columns, rows, has_more, summary, rag_snippets
    """
    q = (question or "").strip()
    if not q:
        return {
            "ok": False,
            "sql": None,
            "validation_error": "问题为空",
            "columns": [],
            "rows": [],
            "has_more": False,
            "summary": None,
            "rag_snippets": [],
        }

    snippets = retrieve_analytics_context(q)
    rag_block = "\n---\n".join(snippets) if snippets else "(当前无向量检索结果，请先运行 python -m core.analytics.reindex)"
    schema_block = build_compact_schema()

    raw = resilient_invoke(_nl2sql_prompt(q, rag_block, schema_block))
    try:
        payload = _extract_json_object(raw)
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "sql": None,
            "validation_error": f"模型输出不是合法 JSON: {e}",
            "columns": [],
            "rows": [],
            "has_more": False,
            "summary": None,
            "rag_snippets": snippets,
        }

    sql = (payload.get("sql") or "").strip()
    ok, msg, sql_norm = validate_analytics_sql(sql)
    if not ok or not sql_norm:
        return {
            "ok": False,
            "sql": sql or None,
            "validation_error": msg,
            "columns": [],
            "rows": [],
            "has_more": False,
            "summary": None,
            "rag_snippets": snippets,
        }

    try:
        cols, rows, has_more = execute_read_only(sql_norm)
    except Exception as e:
        return {
            "ok": False,
            "sql": sql_norm,
            "validation_error": f"执行失败: {e}",
            "columns": [],
            "rows": [],
            "has_more": False,
            "summary": None,
            "rag_snippets": snippets,
        }

    preview_lines = []
    for r in rows[:8]:
        preview_lines.append(str(dict(zip(cols, r))))
    preview = "\n".join(preview_lines) if preview_lines else "(无行)"
    summary_raw = resilient_invoke(_summary_prompt(q, sql_norm, preview))
    summary = (summary_raw or "").strip()

    return {
        "ok": True,
        "sql": sql_norm,
        "validation_error": None,
        "columns": cols,
        "rows": rows,
        "has_more": has_more,
        "summary": summary,
        "rag_snippets": snippets,
    }
