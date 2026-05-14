"""
编排：检索词典 → LLM 生成 SQL → sql_guard 校验 → 只读执行 → 可选自然语言小结。
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

from config.settings import settings
from db.base import engine
from core.analytics.executor import execute_read_only
from core.analytics.retrieve import retrieve_analytics_context
from core.analytics.sql_guard import validate_analytics_sql
from core.llm import resilient_invoke


def build_compact_schema() -> str:
    """当前库里所有 ma_* 表的一行列清单，供模型对齐列名。"""
    lines: list[str] = []
    pfx = settings.ANALYTICS_ALLOWED_TABLE_PREFIX.replace("%", "")
    with engine.connect() as conn:
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


# 模型常把「徐汇院」写成 name='徐汇院' 导致 0 行；此 SQL 作最后兜底（仍经 sql_guard）
_FALLBACK_XUHUI_MAY_DAILY = """
SELECT s.stat_date, s.order_count, s.revenue
FROM ma_daily_sales_stat s
JOIN ma_branch b ON s.branch_id = b.id
WHERE (b.branch_code = 'SH-XH-01' OR b.name LIKE '%徐汇%')
  AND s.stat_date >= '2026-05-01' AND s.stat_date < '2026-06-01'
ORDER BY s.stat_date
LIMIT 200
""".strip()


_FALLBACK_XUHUI_ORDERS = """
SELECT o.id, o.order_no, o.ordered_at, o.total_amount, o.paid_amount, o.order_status,
       b.name AS branch_name, b.branch_code
FROM ma_order o
JOIN ma_branch b ON o.branch_id = b.id
WHERE (b.branch_code = 'SH-XH-01' OR b.name LIKE '%徐汇%')
ORDER BY o.ordered_at DESC
LIMIT 200
""".strip()

# 某月订单：必须按 ordered_at 限月，避免误走日统计表
_FALLBACK_XUHUI_MAY_ORDERS = """
SELECT o.id, o.order_no, o.ordered_at, o.total_amount, o.paid_amount, o.order_status,
       b.name AS branch_name, b.branch_code
FROM ma_order o
JOIN ma_branch b ON o.branch_id = b.id
WHERE (b.branch_code = 'SH-XH-01' OR b.name LIKE '%徐汇%')
  AND o.ordered_at >= '2026-05-01' AND o.ordered_at < '2026-06-01'
ORDER BY o.ordered_at DESC
LIMIT 200
""".strip()


def _has_xuhui_branch_hint(q: str) -> bool:
    """徐汇旗舰院系：全名常含「臻美·徐汇」；勿把浦东旗舰算进来。"""
    return ("徐汇" in q) or ("旗舰" in q and "浦东" not in q) or (
        "臻美" in q and "徐汇" in q
    )


def _has_may_2026_hint(q: str) -> bool:
    return any(x in q for x in ("5月", "五月", "05月", "2026-05", "五月份"))


def _should_try_xuhui_may_order_list(question: str) -> bool:
    """徐汇系 + 5 月 + 查订单行 → ma_order + 月份区间（优先于日统计模板）。"""
    q = (question or "").strip()
    if not _has_xuhui_branch_hint(q) or not _has_may_2026_hint(q):
        return False
    return any(x in q for x in ("订单", "下单", "销售单", "order")) or (
        "order" in q.lower()
    )


def _should_try_xuhui_orders(question: str) -> bool:
    """徐汇/旗舰院 + 查订单（不要求带月份）。"""
    q = (question or "").strip()
    if _should_try_xuhui_may_order_list(q):
        return False
    branch_hit = _has_xuhui_branch_hint(q)
    order_hit = any(
        x in q for x in ("订单", "下单", "销售单", "order")
    ) or ("order" in q.lower())
    return branch_hit and order_hit


def _should_try_xuhui_may_fallback(question: str) -> bool:
    q = (question or "").strip()
    if _should_try_xuhui_may_order_list(q):
        return False
    if "徐汇" not in q:
        return False
    if not _has_may_2026_hint(q):
        return False
    if not any(x in q for x in ("营收", "收入", "订单", "单量", "order", "revenue", "日营")):
        return False
    return True


def _nl2sql_prompt(question: str, rag_block: str, schema_block: str) -> str:
    return f"""你是 SQLite 报表助手。用户问题如下。
请只输出 **一个 JSON 对象**（不要 Markdown、不要多余解释），格式严格为：
{{"sql":"...","notes":"一句话说明假设"}}

硬性要求：
1. 只能写 **一条** SELECT（可用 WITH 公用表表达式）。
2. 只能查询物理表名以「{settings.ANALYTICS_ALLOWED_TABLE_PREFIX}」开头的表。
3. 列名、表名必须与下方「表结构摘要」一致，不要臆造列。
4. 若用户未指定行数，请自行 LIMIT（建议不超过 {settings.ANALYTICS_ROW_LIMIT}）。
5. 本库为演示数据：用户只说「某月」而未写年份时，**月份按 2026 年** 理解（与种子数据一致）。

【系统约定（必读）】
- 用户说「怎么查」「如何查」时，仍要生成 **可执行且能返回数据行** 的 SELECT，不要生成只含说明字符串、无真实指标的占位查询。
- 用户口头「徐汇院」「徐汇旗舰院」：库中分院名多为「臻美·徐汇旗舰院」，**禁止** `WHERE b.name = '徐汇旗舰院'` 等精确全名（常 0 行）。请用 `b.branch_code = 'SH-XH-01'` 或 `b.name LIKE '%徐汇%'`。
- 问「某月每天日营收、订单量」优先 `ma_daily_sales_stat`（列 `stat_date`, `revenue`, `order_count`），并与 `ma_branch` 按 `branch_id` 关联。
- 问「某分院有哪些订单」用 `ma_order` JOIN `ma_branch`，按 `o.branch_id` 与分院过滤。

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


def _empty_error(
    *,
    err: str,
    sql: str | None,
    snippets: list[str],
) -> dict[str, Any]:
    return {
        "ok": False,
        "sql": sql,
        "validation_error": err,
        "columns": [],
        "rows": [],
        "has_more": False,
        "summary": None,
        "rag_snippets": snippets,
        "used_canonical_template": False,
        "used_empty_result_fallback": False,
    }


def _success_payload(
    *,
    sql_norm: str,
    cols: list[str],
    rows: list[list[Any]],
    has_more: bool,
    summary: str,
    snippets: list[str],
    used_canonical_template: bool,
    used_empty_result_fallback: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "sql": sql_norm,
        "validation_error": None,
        "columns": cols,
        "rows": rows,
        "has_more": has_more,
        "summary": summary,
        "rag_snippets": snippets,
        "used_canonical_template": used_canonical_template,
        "used_empty_result_fallback": used_empty_result_fallback,
    }


def run_nl_query(question: str) -> dict[str, Any]:
    """
    完整问数流水线。
    返回 dict: ok, sql, validation_error, columns, rows, has_more, summary, rag_snippets,
    used_canonical_template（是否命中内置固定模板：徐汇+5月订单、徐汇+5月日统计、徐汇/旗舰院+订单）, used_empty_result_fallback
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
            "used_canonical_template": False,
            "used_empty_result_fallback": False,
        }

    snippets = retrieve_analytics_context(q)
    rag_block = "\n---\n".join(snippets) if snippets else "(当前无向量检索结果，请先运行 python -m core.analytics.reindex)"
    schema_block = build_compact_schema()

    # 高频问法：不依赖大模型写 SQL，直接用已校验模板（避免 name='徐汇院' 等 0 行）
    # 「5 月 + 订单」须走 ma_order，不可先走日统计（否则用户以为查不出订单）
    if _should_try_xuhui_may_order_list(q):
        ok_mo, _msg_mo, sql_mo = validate_analytics_sql(_FALLBACK_XUHUI_MAY_ORDERS)
        if ok_mo and sql_mo:
            try:
                cols_mo, rows_mo, more_mo = execute_read_only(sql_mo)
                if rows_mo:
                    preview_lines = [
                        str(dict(zip(cols_mo, r))) for r in rows_mo[:8]
                    ]
                    preview = "\n".join(preview_lines)
                    summary_raw = resilient_invoke(
                        _summary_prompt(q, sql_mo, preview)
                    )
                    return _success_payload(
                        sql_norm=sql_mo,
                        cols=cols_mo,
                        rows=rows_mo,
                        has_more=more_mo,
                        summary=(summary_raw or "").strip(),
                        snippets=snippets,
                        used_canonical_template=True,
                        used_empty_result_fallback=False,
                    )
            except Exception:
                pass

    if _should_try_xuhui_may_fallback(q):
        ok_c, _msg_c, sql_c = validate_analytics_sql(_FALLBACK_XUHUI_MAY_DAILY)
        if ok_c and sql_c:
            try:
                cols_c, rows_c, more_c = execute_read_only(sql_c)
                if rows_c:
                    preview_lines = [
                        str(dict(zip(cols_c, r))) for r in rows_c[:8]
                    ]
                    preview = "\n".join(preview_lines)
                    summary_raw = resilient_invoke(
                        _summary_prompt(q, sql_c, preview)
                    )
                    return _success_payload(
                        sql_norm=sql_c,
                        cols=cols_c,
                        rows=rows_c,
                        has_more=more_c,
                        summary=(summary_raw or "").strip(),
                        snippets=snippets,
                        used_canonical_template=True,
                        used_empty_result_fallback=False,
                    )
            except Exception:
                pass

    if _should_try_xuhui_orders(q):
        ok_o, _msg_o, sql_o = validate_analytics_sql(_FALLBACK_XUHUI_ORDERS)
        if ok_o and sql_o:
            try:
                cols_o, rows_o, more_o = execute_read_only(sql_o)
                if rows_o:
                    preview_lines = [
                        str(dict(zip(cols_o, r))) for r in rows_o[:8]
                    ]
                    preview = "\n".join(preview_lines)
                    summary_raw = resilient_invoke(
                        _summary_prompt(q, sql_o, preview)
                    )
                    return _success_payload(
                        sql_norm=sql_o,
                        cols=cols_o,
                        rows=rows_o,
                        has_more=more_o,
                        summary=(summary_raw or "").strip(),
                        snippets=snippets,
                        used_canonical_template=True,
                        used_empty_result_fallback=False,
                    )
            except Exception:
                pass

    raw = resilient_invoke(_nl2sql_prompt(q, rag_block, schema_block))
    try:
        payload = _extract_json_object(raw)
    except json.JSONDecodeError as e:
        return _empty_error(
            err=f"模型输出不是合法 JSON: {e}",
            sql=None,
            snippets=snippets,
        )

    sql = (payload.get("sql") or "").strip()
    ok, msg, sql_norm = validate_analytics_sql(sql)
    if not ok or not sql_norm:
        return _empty_error(err=msg, sql=sql or None, snippets=snippets)

    try:
        cols, rows, has_more = execute_read_only(sql_norm)
    except Exception as e:
        return _empty_error(
            err=f"执行失败: {e}",
            sql=sql_norm,
            snippets=snippets,
        )

    used_fallback = False
    if not rows and _should_try_xuhui_may_order_list(q):
        ok_mo, _, sql_mo = validate_analytics_sql(_FALLBACK_XUHUI_MAY_ORDERS)
        if ok_mo and sql_mo:
            try:
                c2, r2, h2 = execute_read_only(sql_mo)
                if r2:
                    cols, rows, has_more, sql_norm = c2, r2, h2, sql_mo
                    used_fallback = True
            except Exception:
                pass
    if not rows and _should_try_xuhui_may_fallback(q):
        ok_fb, msg_fb, sql_fb = validate_analytics_sql(_FALLBACK_XUHUI_MAY_DAILY)
        if ok_fb and sql_fb:
            try:
                c2, r2, h2 = execute_read_only(sql_fb)
                if r2:
                    cols, rows, has_more, sql_norm = c2, r2, h2, sql_fb
                    used_fallback = True
            except Exception:
                pass
    if not rows and _should_try_xuhui_orders(q):
        ok_o, _, sql_o = validate_analytics_sql(_FALLBACK_XUHUI_ORDERS)
        if ok_o and sql_o:
            try:
                c2, r2, h2 = execute_read_only(sql_o)
                if r2:
                    cols, rows, has_more, sql_norm = c2, r2, h2, sql_o
                    used_fallback = True
            except Exception:
                pass

    preview_lines = []
    for r in rows[:8]:
        preview_lines.append(str(dict(zip(cols, r))))
    preview = "\n".join(preview_lines) if preview_lines else "(无行)"
    summary_raw = resilient_invoke(_summary_prompt(q, sql_norm, preview))
    summary = (summary_raw or "").strip()

    return _success_payload(
        sql_norm=sql_norm,
        cols=cols,
        rows=rows,
        has_more=has_more,
        summary=summary,
        snippets=snippets,
        used_canonical_template=False,
        used_empty_result_fallback=used_fallback,
    )
