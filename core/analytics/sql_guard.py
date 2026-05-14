"""
大模型生成 SQL 之后的「硬校验」：单语句、只读、仅允许 ma_* 物理表（CTE/子查询别名除外）。
使用 sqlglot 解析 SQLite 方言。
"""
from __future__ import annotations

from sqlglot import exp, parse

from config.settings import settings


def _collect_cte_names(node: exp.Expression) -> set[str]:
    names: set[str] = set()
    for w in node.find_all(exp.With):
        for e in w.expressions:
            if isinstance(e, exp.CTE):
                al = e.alias
                if isinstance(al, str):
                    names.add(al.strip('"').strip("`"))
                elif isinstance(al, exp.Identifier):
                    names.add(al.this)
                elif al is not None:
                    names.add(str(al).strip('"').strip("`"))
    return names


def _collect_subquery_aliases(node: exp.Expression) -> set[str]:
    aliases: set[str] = set()
    for sq in node.find_all(exp.Subquery):
        al = sq.args.get("alias")
        if isinstance(al, exp.TableAlias):
            if al.this:
                aliases.add(al.this.name)
        elif isinstance(al, exp.Identifier):
            aliases.add(al.this)
    return aliases


def validate_analytics_sql(sql: str) -> tuple[bool, str, str | None]:
    """
    :return: (是否通过, 说明信息, 去掉末尾分号后的 SQL)
    """
    raw = (sql or "").strip()
    if not raw:
        return False, "SQL 为空", None
    normalized = raw.rstrip().rstrip(";").strip()

    try:
        trees = parse(normalized, read="sqlite")
    except Exception as e:
        return False, f"SQL 解析失败: {e}", None

    stmts = [t for t in trees if t and not isinstance(t, exp.Semicolon)]
    if len(stmts) != 1:
        return False, "只支持且必须恰好一条 SQL", None

    tree = stmts[0]

    for cls in (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
    ):
        if tree.find(cls):
            return False, f"禁止的语句类型: {cls.__name__}", None

    cte_names = _collect_cte_names(tree)
    sub_aliases = _collect_subquery_aliases(tree)
    prefix = settings.ANALYTICS_ALLOWED_TABLE_PREFIX.lower()

    for t in tree.find_all(exp.Table):
        name = (t.name or "").strip('"').strip("`")
        if not name:
            continue
        if name in cte_names or name in sub_aliases:
            continue
        if name.lower().startswith(prefix):
            continue
        return (
            False,
            f"仅允许访问物理表名以「{settings.ANALYTICS_ALLOWED_TABLE_PREFIX}」开头；"
            f"非法表/别名: {name}",
            None,
        )

    if isinstance(tree, exp.Select):
        ok_root = True
    elif isinstance(tree, exp.Union):
        ok_root = True
    elif isinstance(tree, exp.With):
        inner = tree.this
        ok_root = isinstance(inner, (exp.Select, exp.Union))
    else:
        ok_root = False
    if not ok_root:
        return False, "仅支持 SELECT 或 WITH … SELECT / UNION", None

    return True, "校验通过", normalized
