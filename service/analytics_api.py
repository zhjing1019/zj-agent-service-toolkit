"""
AI 问数 HTTP 接口：自然语言 → 检索词典向量 → 生成 SQL → 校验 → 执行 → 小结。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.analytics.nl2sql import run_nl_query
from core.analytics.vector_index import rebuild_analytics_index

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class NlQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用自然语言描述要查的数据")


class NlQueryResponse(BaseModel):
    ok: bool
    sql: str | None = None
    validation_error: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    has_more: bool = False
    summary: str | None = None
    rag_snippets: list[str] = Field(default_factory=list)
    used_empty_result_fallback: bool = Field(
        default=False,
        description="模型 SQL 返回 0 行时是否已用内置徐汇+5月日统计 SQL 兜底",
    )
    used_canonical_template: bool = Field(
        default=False,
        description="是否命中徐汇+5月+营收/订单 固定模板（未走大模型写 SQL）",
    )


@router.post("/nl-query", response_model=NlQueryResponse)
def post_nl_query(body: NlQueryRequest) -> NlQueryResponse:
    """需要配置好 LLM API Key；首次使用请先 POST /reindex-analytics。"""
    out = run_nl_query(body.question)
    return NlQueryResponse(**out)


@router.post("/reindex-analytics")
def post_reindex_analytics() -> dict:
    """重建问数专用向量库（表结构 + analytics_business.yaml）。"""
    from db.init_db import init_database

    init_database()
    n = rebuild_analytics_index(wipe=True)
    return {"ok": True, "documents": n}
