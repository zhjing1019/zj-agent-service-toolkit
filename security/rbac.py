"""RBAC：基于 API Key 的角色与权限（管理员 / 开发者 / 业务用户）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet

from fastapi import HTTPException, Request

from config.logger import logger
from config.settings import settings

# 权限点（字符串便于扩展与配置对照）
PERM_ADMIN_CONFIG = "admin.config"  # 清会话、切模型、重建 RAG 索引等
PERM_GRAPH_VISUALIZE = "graph.visualize"
PERM_TASK_EXECUTE = "task.execute"  # 与 agent_id 白名单配合
PERM_TASK_OBSERVE = "task.observe"  # 任务状态、运行列表
PERM_LOGS_READ = "logs.read"
PERM_TEMPLATES_READ = "templates.read"
PERM_TEMPLATES_WRITE = "templates.write"
PERM_ANALYTICS_QUERY = "analytics.query"  # 自然语言问数（NL2SQL）
PERM_ANALYTICS_REINDEX = "analytics.reindex"  # 重建问数向量索引（与生产数据/算力相关）


class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    BUSINESS = "business"


KNOWN_AGENT_IDS: FrozenSet[str] = frozenset({"default", "base_tool"})
# default: LangGraph 多 Agent（/chat、流式、checkpoint）
# base_tool: 旧版 BaseAgent（/api/agent/run、memory）


def normalize_agent_id(raw: str | None) -> str:
    v = (raw or "default").strip().lower()
    if v in ("", "langgraph", "graph"):
        return "default"
    if v in ("base", "tool", "base_tool", "baseagent"):
        return "base_tool"
    return v


@dataclass(frozen=True)
class Principal:
    """当前请求主体：角色 + 可选的业务用户 Agent 白名单（None 表示不限制）。"""

    role: Role
    key_hint: str
    agent_allowlist: frozenset[str] | None
    # 问数行级范围：仅 BUSINESS 且配置了 RBAC_BUSINESS_ANALYTICS_BRANCH_CODES 时非 None
    analytics_branch_allowlist: frozenset[str] | None = None

    def has_permission(self, perm: str) -> bool:
        if self.role == Role.ADMIN:
            return True
        if self.role == Role.DEVELOPER:
            return perm in _DEVELOPER_PERMS
        if self.role == Role.BUSINESS:
            return perm in _BUSINESS_PERMS
        return False

    def can_run_agent(self, agent_id: str) -> bool:
        aid = normalize_agent_id(agent_id)
        if aid not in KNOWN_AGENT_IDS:
            return False
        if self.agent_allowlist is None:
            return True
        return aid in self.agent_allowlist


_DEVELOPER_PERMS = frozenset(
    {
        PERM_GRAPH_VISUALIZE,
        PERM_TASK_EXECUTE,
        PERM_TASK_OBSERVE,
        PERM_LOGS_READ,
        PERM_TEMPLATES_READ,
        PERM_ANALYTICS_QUERY,
        PERM_ANALYTICS_REINDEX,
    }
)

_BUSINESS_PERMS = frozenset(
    {
        PERM_TASK_EXECUTE,
        PERM_TASK_OBSERVE,
        PERM_TEMPLATES_READ,
        PERM_ANALYTICS_QUERY,
    }
)


def _parse_csv_keys(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def _key_table() -> dict[str, tuple[Role, frozenset[str] | None]]:
    """api_key -> (Role, agent_allowlist or None 表示全部 Agent)"""
    tbl: dict[str, tuple[Role, frozenset[str] | None]] = {}
    for k in _parse_csv_keys(settings.RBAC_ADMIN_API_KEYS):
        tbl[k] = (Role.ADMIN, None)
    for k in _parse_csv_keys(settings.RBAC_DEVELOPER_API_KEYS):
        if k in tbl:
            continue
        tbl[k] = (Role.DEVELOPER, None)
    biz_allow = _parse_csv_keys(settings.RBAC_BUSINESS_AGENT_IDS) or frozenset({"default"})
    for k in _parse_csv_keys(settings.RBAC_BUSINESS_API_KEYS):
        if k in tbl:
            continue
        tbl[k] = (Role.BUSINESS, biz_allow)
    return tbl


def _extract_api_key(request: Request) -> str | None:
    h = request.headers.get("X-API-Key")
    if h and h.strip():
        return h.strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    q = request.query_params.get("api_key")
    if q and q.strip():
        return q.strip()
    return None


def resolve_principal(request: Request) -> Principal:
    if not settings.RBAC_ENABLED:
        return Principal(
            role=Role.ADMIN,
            key_hint="(rbac-off)",
            agent_allowlist=None,
            analytics_branch_allowlist=None,
        )

    key = _extract_api_key(request)
    if not key:
        raise HTTPException(
            status_code=401,
            detail="未认证：请在 Header 携带 X-API-Key 或 Authorization: Bearer <key>（SSE 可附加查询参数 api_key）",
        )
    tbl = _key_table()
    row = tbl.get(key)
    if not row:
        logger.warning("RBAC: 拒绝未知 API Key（hint=%s）", key[-4:] if len(key) >= 4 else "****")
        raise HTTPException(status_code=401, detail="无效的 API Key")
    role, allow = row
    hint = key[-4:] if len(key) >= 4 else "****"
    biz_analytics: frozenset[str] | None = None
    if role == Role.BUSINESS and settings.RBAC_BUSINESS_ANALYTICS_BRANCH_CODES:
        parts = [
            x.strip()
            for x in settings.RBAC_BUSINESS_ANALYTICS_BRANCH_CODES.split(",")
            if x.strip()
        ]
        biz_analytics = frozenset(parts) if parts else None
    return Principal(
        role=role,
        key_hint=hint,
        agent_allowlist=allow,
        analytics_branch_allowlist=biz_analytics,
    )


def attach_principal(request: Request) -> None:
    """Router 级依赖：写入 request.state.principal。"""
    request.state.principal = resolve_principal(request)


def get_principal(request: Request) -> Principal:
    p = getattr(request.state, "principal", None)
    if p is None:
        request.state.principal = resolve_principal(request)
        p = request.state.principal
    return p


def require_perm(permission: str):
    def _checker(request: Request) -> None:
        p = get_principal(request)
        if not p.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"权限不足：需要 {permission}（当前角色 {p.role.value}）",
            )

    return _checker


def ensure_agent_allowed(request: Request, agent_id: str | None) -> str:
    """校验并可执行 Agent；返回规范化后的 agent_id。"""
    p = get_principal(request)
    aid = normalize_agent_id(agent_id)
    if aid not in KNOWN_AGENT_IDS:
        raise HTTPException(status_code=400, detail=f"未知的 agent_id：{aid}")
    if not p.can_run_agent(aid):
        raise HTTPException(
            status_code=403,
            detail=f"当前角色不允许执行 Agent「{aid}」，可执行：{sorted(p.agent_allowlist or ())}",
        )
    return aid


def ensure_langgraph_chat(request: Request, agent_id: str | None) -> None:
    """对话类接口仅允许 LangGraph（default）。"""
    aid = ensure_agent_allowed(request, agent_id or "default")
    if aid != "default":
        raise HTTPException(
            status_code=400,
            detail="对话接口仅支持 agent_id=default（LangGraph）；基础工具请使用 POST /api/agent/run",
        )
