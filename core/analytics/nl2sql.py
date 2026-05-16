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

# 构建紧凑的表结构摘要
def build_compact_schema() -> str:
    """当前库里所有 ma_* 表的一行列清单，供模型对齐列名。"""
    lines: list[str] = []
    # 获取允许的表前缀
    pfx = settings.ANALYTICS_ALLOWED_TABLE_PREFIX.replace("%", "")
    # 连接数据库
    with engine.connect() as conn:
        # 获取所有表
        tables = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name LIKE :pfx ORDER BY name"
            ),
            {"pfx": f"{pfx}%"},
        ).fetchall()
        # 获取所有列
        for (tbl,) in tables:
            # 获取所有列
            cols = conn.execute(text(f'PRAGMA table_info("{tbl}")')).fetchall()
            # 获取所有列名
            names = [c[1] for c in cols]
            lines.append(f"{tbl}: " + ", ".join(names))
    return "\n".join(lines) if lines else "(无 ma_* 表，请先 init_database)"

# 提取 JSON 对象
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

# 某月订单：必须按 ordered_at 限月，避免误走日统计表
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

# 判断是否包含徐汇分支提示
def _has_xuhui_branch_hint(q: str) -> bool:
    """徐汇旗舰院系：全名常含「臻美·徐汇」；勿把浦东旗舰算进来。"""
    return ("徐汇" in q) or ("旗舰" in q and "浦东" not in q) or (
        "臻美" in q and "徐汇" in q
    )

# 判断是否包含5月提示
def _has_may_2026_hint(q: str) -> bool:
    return any(x in q for x in ("5月", "五月", "05月", "2026-05", "五月份"))

# 判断是否包含徐汇系 + 5 月 + 查订单行 → ma_order + 月份区间（优先于日统计模板）
def _should_try_xuhui_may_order_list(question: str) -> bool:
    """徐汇系 + 5 月 + 查订单行 → ma_order + 月份区间（优先于日统计模板）。"""
    q = (question or "").strip()
    # 判断是否包含徐汇分支提示和5月提示
    if not _has_xuhui_branch_hint(q) or not _has_may_2026_hint(q):
        return False
    # 判断是否包含订单相关关键词
    return any(x in q for x in ("订单", "下单", "销售单", "order")) or (
        "order" in q.lower()
    )

# 判断是否包含徐汇分支提示和订单相关关键词
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

# 判断是否包含徐汇分支提示和5月提示
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

# 判断是否允许使用徐汇模板
def _xuhui_templates_allowed(allowed_branch_codes: frozenset[str] | None) -> bool:
    """内置徐汇模板硬编码 SH-XH-01；若调用方不允许该院则不走模板。"""
    if not allowed_branch_codes:
        return True
    return "SH-XH-01" in allowed_branch_codes

# 构建数据权限提示块
def _scope_prompt_block(allowed_branch_codes: frozenset[str] | None) -> str:
    if not allowed_branch_codes:
        return ""
    codes = ", ".join(f"'{c}'" for c in sorted(allowed_branch_codes))
    return f"""
【数据权限（必须遵守）】
当前调用方仅允许查看 ma_branch.branch_code 属于以下编码的数据：{codes}。
凡 SQL 涉及订单、日统计、客户、员工、库存等与分院相关的内容时，必须通过 JOIN ma_branch（别名自定）并包含
对 ma_branch.branch_code 的约束，且 IN 列表**只能**使用上述编码（不得查询其它分院）。
"""

# 结果层过滤：仅当结果集中存在 branch_code 列时生效
def _apply_branch_scope_rows(
    cols: list[str],
    rows: list[list[Any]],
    allowed_branch_codes: frozenset[str] | None,
) -> tuple[list[list[Any]], bool, str | None]:
    """
    结果层过滤：仅当结果集中存在 branch_code 列时生效。
    不能替代 SQL 侧权限，作为业务用户白名单的二次收敛。
    """
    if not allowed_branch_codes:
        return rows, False, None
    idx = None
    for i, c in enumerate(cols):
        if str(c).lower() == "branch_code":
            idx = i
            break
    if idx is None:
        return (
            rows,
            False,
            "已配置分院级数据权限，但本查询结果列中无 branch_code，无法在接口层对行做二次过滤；"
            "安全上仍应以 API 身份与提示词约束为准。",
        )
    filtered = [
        r for r in rows if len(r) > idx and str(r[idx]) in allowed_branch_codes
    ]
    return filtered, True, None

# 构建NL2SQL提示块
def _nl2sql_prompt(
    question: str, rag_block: str, schema_block: str, scope_block: str = ""
) -> str:
    return f"""你是 SQLite 报表助手。用户问题如下。
请只输出 **一个 JSON 对象**（不要 Markdown、不要多余解释），格式严格为：
{{"sql":"...","notes":"一句话说明假设"}}

硬性要求：
1. 只能写 **一条** SELECT（可用 WITH 公用表表达式）。
2. 只能查询物理表名以「{settings.ANALYTICS_ALLOWED_TABLE_PREFIX}」开头的表。
3. 列名、表名必须与下方「表结构摘要」一致，不要臆造列。
4. 若用户未指定行数，请自行 LIMIT（建议不超过 {settings.ANALYTICS_ROW_LIMIT}）。
5. 本库为演示数据：用户只说「某月」而未写年份时，**月份按 2026 年** 理解（与种子数据一致）。
{scope_block}
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

# 构建总结提示块
def _summary_prompt(question: str, sql: str, preview: str) -> str:
    return f"""用户问题：{question}
已执行 SQL：{sql}
查询结果预览（前几行文本化）：{preview}

请用 2～5 句中文总结回答用户；数字必须与预览一致，不得编造。
若结果为空，说明无数据并给出可能原因（时间范围、分院条件等）。
"""

# 构建空错误提示块
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
        "data_scope_row_filter_applied": False,
        "data_scope_branch_codes": None,
        "data_scope_warning": None,
    }

# 构建成功提示块
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
    allowed_branch_codes: frozenset[str] | None = None,
) -> dict[str, Any]:
    rows_f, applied, warn = _apply_branch_scope_rows(cols, rows, allowed_branch_codes)
    return {
        "ok": True,
        "sql": sql_norm,
        "validation_error": None,
        "columns": cols,
        "rows": rows_f,
        "has_more": has_more,
        "summary": summary,
        "rag_snippets": snippets,
        "used_canonical_template": used_canonical_template,
        "used_empty_result_fallback": used_empty_result_fallback,
        "data_scope_row_filter_applied": applied,
        "data_scope_branch_codes": sorted(allowed_branch_codes)
        if allowed_branch_codes
        else None,
        "data_scope_warning": warn,
    }

# 完整问数流水线
def run_nl_query(
    question: str, *, allowed_branch_codes: frozenset[str] | None = None
) -> dict[str, Any]:
    """
    完整问数流水线。
    返回 dict: ok, sql, validation_error, columns, rows, has_more, summary, rag_snippets,
    used_canonical_template, used_empty_result_fallback,
    data_scope_row_filter_applied, data_scope_branch_codes, data_scope_warning。

    allowed_branch_codes: 可选分院 branch_code 白名单；非 None 时写入模型提示并在结果含 branch_code 列时过滤行。
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
            "data_scope_row_filter_applied": False,
            "data_scope_branch_codes": None,
            "data_scope_warning": None,
        }
    # 检索向量库
    snippets = retrieve_analytics_context(q)
    # 构建RAG块
    rag_block = "\n---\n".join(snippets) if snippets else "(当前无向量检索结果，请先运行 python -m core.analytics.reindex)"
    # 构建表结构摘要块
    schema_block = build_compact_schema()
    # 构建数据权限提示块
    scope_block = _scope_prompt_block(allowed_branch_codes)

    # 高频问法：不依赖大模型写 SQL，直接用已校验模板（避免 name='徐汇院' 等 0 行）
    if _should_try_xuhui_may_order_list(q) and _xuhui_templates_allowed(
        allowed_branch_codes
    ):
        ok_mo, _msg_mo, sql_mo = validate_analytics_sql(_FALLBACK_XUHUI_MAY_ORDERS)
        if ok_mo and sql_mo:
            try:
                cols_mo, rows_mo, more_mo = execute_read_only(sql_mo)
                rows_vis, _, _ = _apply_branch_scope_rows(
                    cols_mo, rows_mo, allowed_branch_codes
                )
                if rows_vis:
                    preview_lines = [
                        str(dict(zip(cols_mo, r))) for r in rows_vis[:8]
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
                        allowed_branch_codes=allowed_branch_codes,
                    )
            except Exception:
                pass

    if _should_try_xuhui_may_fallback(q) and _xuhui_templates_allowed(
        allowed_branch_codes
    ):
        ok_c, _msg_c, sql_c = validate_analytics_sql(_FALLBACK_XUHUI_MAY_DAILY)
        if ok_c and sql_c:
            try:
                cols_c, rows_c, more_c = execute_read_only(sql_c)
                rows_vis, _, _ = _apply_branch_scope_rows(
                    cols_c, rows_c, allowed_branch_codes
                )
                if rows_vis:
                    preview_lines = [
                        str(dict(zip(cols_c, r))) for r in rows_vis[:8]
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
                        allowed_branch_codes=allowed_branch_codes,
                    )
            except Exception:
                pass

    if _should_try_xuhui_orders(q) and _xuhui_templates_allowed(allowed_branch_codes):
        ok_o, _msg_o, sql_o = validate_analytics_sql(_FALLBACK_XUHUI_ORDERS)
        if ok_o and sql_o:
            try:
                cols_o, rows_o, more_o = execute_read_only(sql_o)
                rows_vis, _, _ = _apply_branch_scope_rows(
                    cols_o, rows_o, allowed_branch_codes
                )
                if rows_vis:
                    preview_lines = [
                        str(dict(zip(cols_o, r))) for r in rows_vis[:8]
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
                        allowed_branch_codes=allowed_branch_codes,
                    )
            except Exception:
                pass

    raw = resilient_invoke(
        _nl2sql_prompt(q, rag_block, schema_block, scope_block)
    )
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
    if not rows and _should_try_xuhui_may_order_list(
        q
    ) and _xuhui_templates_allowed(allowed_branch_codes):
        ok_mo, _, sql_mo = validate_analytics_sql(_FALLBACK_XUHUI_MAY_ORDERS)
        if ok_mo and sql_mo:
            try:
                c2, r2, h2 = execute_read_only(sql_mo)
                r2_vis, _, _ = _apply_branch_scope_rows(c2, r2, allowed_branch_codes)
                if r2_vis:
                    cols, rows, has_more, sql_norm = c2, r2, h2, sql_mo
                    used_fallback = True
            except Exception:
                pass
    if not rows and _should_try_xuhui_may_fallback(
        q
    ) and _xuhui_templates_allowed(allowed_branch_codes):
        ok_fb, msg_fb, sql_fb = validate_analytics_sql(_FALLBACK_XUHUI_MAY_DAILY)
        if ok_fb and sql_fb:
            try:
                c2, r2, h2 = execute_read_only(sql_fb)
                r2_vis, _, _ = _apply_branch_scope_rows(c2, r2, allowed_branch_codes)
                if r2_vis:
                    cols, rows, has_more, sql_norm = c2, r2, h2, sql_fb
                    used_fallback = True
            except Exception:
                pass
    if not rows and _should_try_xuhui_orders(q) and _xuhui_templates_allowed(
        allowed_branch_codes
    ):
        ok_o, _, sql_o = validate_analytics_sql(_FALLBACK_XUHUI_ORDERS)
        if ok_o and sql_o:
            try:
                c2, r2, h2 = execute_read_only(sql_o)
                r2_vis, _, _ = _apply_branch_scope_rows(c2, r2, allowed_branch_codes)
                if r2_vis:
                    cols, rows, has_more, sql_norm = c2, r2, h2, sql_o
                    used_fallback = True
            except Exception:
                pass

    rows_vis, _, _ = _apply_branch_scope_rows(cols, rows, allowed_branch_codes)
    preview_lines = []
    for r in rows_vis[:8]:
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
        allowed_branch_codes=allowed_branch_codes,
    )
