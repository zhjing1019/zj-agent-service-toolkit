"""
AI 问数 HTTP 接口：自然语言 → 检索词典向量 → 生成 SQL → 校验 → 执行 → 小结。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from core.analytics.nl2sql import run_nl_query
from core.analytics.vector_index import rebuild_analytics_index
from security.rbac import (
    PERM_ANALYTICS_QUERY,
    PERM_ANALYTICS_REINDEX,
    attach_principal,
    get_principal,
    require_perm,
)
# 问数API路由
router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
    dependencies=[Depends(attach_principal)],
)

# 问数请求参数
class NlQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用自然语言描述要查的数据")

# 问数响应参数
class NlQueryResponse(BaseModel):
    ok: bool
    sql: str | None = None
    validation_error: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    has_more: bool = False
    summary: str | None = None
    rag_snippets: list[str] = Field(default_factory=list)
    # 是否命中徐汇+5月+营收/订单 固定模板（未走大模型写 SQL）
    used_empty_result_fallback: bool = Field(
        default=False,
        description="模型 SQL 返回 0 行时是否已用内置徐汇+5月日统计 SQL 兜底",
    )
    # 是否命中徐汇+5月+营收/订单 固定模板（未走大模型写 SQL）
    used_canonical_template: bool = Field(
        default=False,
        description="是否命中徐汇+5月+营收/订单 固定模板（未走大模型写 SQL）",
    )
    # 是否在结果行上按 branch_code 做了二次过滤（业务用户白名单）
    data_scope_row_filter_applied: bool = Field(
        default=False,
        description="是否在结果行上按 branch_code 做了二次过滤（业务用户白名单）",
    )
    # 当前主体允许的分院 branch_code 列表；未配置则为 null
    data_scope_branch_codes: list[str] | None = Field(
        default=None,
        description="当前主体允许的分院 branch_code 列表；未配置则为 null",
    )
    # 数据范围提示（例如结果无 branch_code 列无法过滤）
    data_scope_warning: str | None = Field(
        default=None,
        description="数据范围提示（例如结果无 branch_code 列无法过滤）",
    )

# 问数接口
@router.post("/nl-query", response_model=NlQueryResponse)
def post_nl_query(
    request: Request,
    body: NlQueryRequest,
    _: None = Depends(require_perm(PERM_ANALYTICS_QUERY)),
) -> NlQueryResponse:
    """需要配置好 LLM API Key；首次使用请先 POST /reindex-analytics。RBAC 开启时需带 API Key。"""
    principal = get_principal(request)
    out = run_nl_query(
        body.question,
        allowed_branch_codes=principal.analytics_branch_allowlist,
    )
    return NlQueryResponse(**out)

# 重建问数专用向量库
@router.post("/reindex-analytics")
def post_reindex_analytics(
    _: None = Depends(require_perm(PERM_ANALYTICS_REINDEX)),
) -> dict:
    """重建问数专用向量库（表结构 + analytics_business.yaml）。"""
    # 初始化数据库
    from db.init_db import init_database
    # 初始化数据库
    init_database()
    # 重建问数专用向量库
    n = rebuild_analytics_index(wipe=True)
    # 返回结果
    return {"ok": True, "documents": n}
