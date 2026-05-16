# 升级成 HTTP 接口服务
import asyncio
import json
import mimetypes
import time
import uuid
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from agent.base_agent import BaseAgent
from sqlalchemy.orm import Session
from config.logger import logger
from config.settings import settings
from core.agent_templates import create_template, delete_template, list_templates
from core.graph import agent_graph
from core.multi_agent import summary_agent_stream
from core.task_timeout import (
    AgentExecutionTimeoutError,
    async_iterate_summary_stream,
    invoke_langgraph_with_timeout,
)
from db.base import get_db
from db.log_repo import log_repo
from db.repository import chat_repo
from db.task_run_repo import task_run_repo
from core.admin import reset_all_chat_session, switch_llm_model
from security.rbac import (
    PERM_ADMIN_CONFIG,
    PERM_GRAPH_VISUALIZE,
    PERM_LOGS_READ,
    PERM_TASK_EXECUTE,
    PERM_TASK_OBSERVE,
    PERM_TEMPLATES_READ,
    PERM_TEMPLATES_WRITE,
    Role,
    attach_principal,
    ensure_agent_allowed,
    ensure_langgraph_chat,
    get_principal,
    require_perm,
)


# 请求参数
class AgentChatReq(BaseModel):
    session_id: str | None = None
    task: str = ""
    # 与 LangGraph 对齐的 Agent：仅 default（SSE/多轮对话）；业务用户由 RBAC 白名单约束
    agent_id: str | None = "default"
    # 与 LangGraph SqliteSaver 的 thread_id 对齐；不传则每次新任务。仅对 POST /chat 生效。
    checkpoint_thread_id: str | None = None
    # 先 POST /chat/upload-image 拿到的 image_id（32hex+扩展名），最多 CHAT_MAX_IMAGES_PER_MESSAGE
    image_ids: list[str] = Field(default_factory=list)

    @field_validator("image_ids", mode="before")
    @classmethod
    def _normalize_image_ids(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        lim = max(1, int(settings.CHAT_MAX_IMAGES_PER_MESSAGE))
        out = [str(x).strip() for x in v if str(x).strip()]
        return out[:lim]

# 解析用户上传的图片路径
def _resolve_user_image_paths(image_ids: list[str] | None) -> list[str]:
    from service.chat_upload import resolve_upload_image_paths

    return resolve_upload_image_paths(list(image_ids or []))

# 获取有效的任务
def _effective_chat_task(task: str, paths: list[str]) -> str:
    t = (task or "").strip()
    if t:
        return t
    if paths:
        return "请结合我上传的图片回答，并检索知识库中与图片或问题相关的内容。"
    return ""

# 获取公共知识库的引用图片
def _public_knowledge_refs(refs: list) -> list[dict]:
    out: list[dict] = []
    for r in refs:
        if not isinstance(r, dict):
            continue
        rel = r.get("rel")
        if not rel:
            continue
        score = r.get("score", 0)
        try:
            score_f = float(score)
        except (TypeError, ValueError):
            score_f = 0.0
        url = f"/api/agent/knowledge-image?rel={quote(str(rel), safe='')}"
        out.append(
            {
                "rel": str(rel),
                "score": score_f,
                "caption": r.get("caption") or "",
                "url": url,
            }
        )
    return out

# 任务恢复请求参数
class TaskResumeReq(BaseModel):
    checkpoint_thread_id: str

# 获取配置
def _invoke_cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}

# 确保新的聊天调用被允许
def _assert_new_chat_invoke_allowed(thread_id: str) -> None:
    """禁止在「已结束」或「停在断点」的 thread 上再次整图 /chat，避免状态串台。"""
    snap = agent_graph.graph.get_state(_invoke_cfg(thread_id))
    vals = snap.values or {}
    if not vals:
        return
    nxt = tuple(snap.next) if snap.next is not None else ()
    if not nxt and vals.get("result"):
        raise HTTPException(
            status_code=400,
            detail="该 checkpoint_thread_id 已完成，请省略或更换后再调用 /chat",
        )
    if nxt:
        raise HTTPException(
            status_code=400,
            detail="任务未跑完，请使用 POST /api/agent/task/resume 断点续跑",
        )


# 初始化FastAPI路由（全链路挂载 RBAC 主体解析）
router = APIRouter(
    prefix="/api/agent",
    tags=["Agent对话"],
    dependencies=[Depends(attach_principal)],
)
# 初始化智能体
agent = BaseAgent()

class TaskRequest(BaseModel):
    task: str
    agent_id: str | None = "base_tool"


class AgentTemplateCreateReq(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    agent_id: str = "default"


# 运维：清空所有会话历史
@router.post("/admin/reset-session")
def api_reset_session(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_ADMIN_CONFIG)),
):
    return reset_all_chat_session(db)

# 运维：动态切换模型
@router.post("/admin/switch-llm")
def api_switch_llm(
    request: Request,
    provider: str = Query(..., description="支持 deepseek / openai"),
    _: None = Depends(require_perm(PERM_ADMIN_CONFIG)),
):
    return switch_llm_model(provider)


@router.post("/admin/index-rag")
def api_index_rag(
    request: Request,
    rebuild: bool = Query(False, description="为 true 时清空 Chroma 目录后全量重建"),
    _: None = Depends(require_perm(PERM_ADMIN_CONFIG)),
):
    """扫描 RAG_KNOWLEDGE_DIR（默认 ./knowledge）下 pdf/txt/md 写入向量库与 BM25，并重建图片 CLIP 索引。"""
    from core.rag import load_knowledge_to_vector_incremental

    load_knowledge_to_vector_incremental(rebuild=rebuild)
    return {"code": 200, "msg": "ok", "data": {"rebuild": rebuild}}

@router.post("/run")
def agent_run(
    request: Request,
    request_body: TaskRequest,
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    task = request_body.task
    if not task:
        raise HTTPException(status_code=400, detail="task不能为空")
    ensure_agent_allowed(request, request_body.agent_id or "base_tool")

    result = agent.run(task)
    return {
        "code": 200,
        "msg": "ok",
        "data": result
    }

# 接口：查看记忆
@router.get("/memory")
def agent_memory(
    request: Request,
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    ensure_agent_allowed(request, "base_tool")
    memory_list = agent.get_memory()
    return {
        "code": 200,
        "msg": "ok",
        "data": memory_list
    }


@router.post("/chat/upload-image")
async def chat_upload_image_route(
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
    file: UploadFile = File(...),
):
    """上传聊天附图，返回 image_id，随 /chat 或 /chat/stream 的 image_ids 提交。"""
    from service.chat_upload import save_chat_upload

    raw = await file.read()
    try:
        image_id = save_chat_upload(raw, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"code": 200, "data": {"image_id": image_id}}


@router.get("/chat-upload")
def chat_upload_serve(
    image_id: str = Query(..., min_length=8, max_length=80),
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    from service.chat_upload import path_for_uploaded_image

    p = path_for_uploaded_image(image_id)
    if p is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    mt = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return FileResponse(p, media_type=mt)


@router.get("/knowledge-image")
def knowledge_image_serve(
    rel: str = Query(..., min_length=1, max_length=2048),
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    """只读提供 RAG_KNOWLEDGE_DIR 下的图片（rel 为相对知识库目录的路径）。"""
    root = Path(settings.RAG_KNOWLEDGE_DIR).resolve()
    decoded = unquote(rel).lstrip("/").replace("\\", "/")
    if ".." in decoded or decoded.startswith("/"):
        raise HTTPException(status_code=400, detail="非法路径")
    target = (root / decoded).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="非法路径")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    mt = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return FileResponse(target, media_type=mt)

# 接口：聊天
@router.post("/chat")
# 在头部添加注释，说明该接口是用于聊天的
# 说明该接口是用于聊天的，用于与LangGraph进行交互，生成回复
# 参数：
# request: Request
# req: AgentChatReq
# db: Session
# _: None = Depends(require_perm(PERM_TASK_EXECUTE))
# 返回：dict
# 说明：返回的dict中包含session_id、checkpoint_thread_id、data、referenced_images
# 其中data是LangGraph生成的回复，referenced_images是LangGraph生成的引用图片
def agent_chat(
    # fastAPI Request对象，用于获取请求的参数
    request: Request,
    # AgentChatReq对象，用于获取请求的参数
    req: AgentChatReq,
    # 数据库Session对象，用于获取数据库的连接
    db: Session = Depends(get_db),
    # 权限依赖，用于获取权限
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    # 确保LangGraph的聊天权限
    ensure_langgraph_chat(request, req.agent_id)
    # 获取checkpoint_thread_id
    checkpoint_thread_id = (req.checkpoint_thread_id or "").strip() or str(
        uuid.uuid4()
    )
    try:
        # 如果session_id为空，则生成一个session_id
        if not req.session_id:
            req.session_id = chat_repo.gen_session_id()

        # 确保新的聊天调用被允许
        _assert_new_chat_invoke_allowed(checkpoint_thread_id)

        # 调用_resolve_user_image_paths方法获取用户上传的图片路径
        paths = _resolve_user_image_paths(req.image_ids)
        # 调用_effective_chat_task方法获取有效的任务
        eff_task = _effective_chat_task(req.task, paths)
        # 如果任务为空，则抛出HTTP异常
        if not eff_task:
            raise HTTPException(status_code=400, detail="task与图片不能同时为空")

        # 调用chat_repo.get_history方法获取历史记录
        history = chat_repo.get_history(db, req.session_id)
        # 初始化LangGraph的初始状态 
        initial = {
            "task": eff_task,
            "is_safe": False,
            "need_tool": False,
            "tool_name": "",
            "tool_params": [],
            "result": "",
            "history": history,
            "rag_context": "",
            "resolved_retrieval_query": "",
            "sub_tasks": [],
            "agent_type": "",
            "task_output": "",
            "final_summary": "",
            "skip_summary_llm": False,
            "user_image_paths": paths,
            "rag_referenced_images": [],
        }

        # 调用task_run_repo.upsert_start方法更新任务状态
        task_run_repo.upsert_start(
            db, checkpoint_thread_id, req.session_id, eff_task[:2000]
        )
        # 调用_invoke_cfg方法获取配置
        cfg = _invoke_cfg(checkpoint_thread_id)
        # 调用invoke_langgraph_with_timeout方法执行LangGraph
        res = invoke_langgraph_with_timeout(
            agent_graph.graph,
            initial,
            cfg,
            settings.AGENT_GRAPH_TIMEOUT_SEC,
        )
        # 获取LangGraph的回复
        agent_reply = res["result"]
        # 调用task_run_repo.mark_completed方法更新任务状态
        task_run_repo.mark_completed(db, checkpoint_thread_id, agent_reply)

        # 获取LangGraph的引用图片   
        refs_raw = res.get("rag_referenced_images") or []
        # 调用_public_knowledge_refs方法获取公共知识库的引用图片
        pub_refs = _public_knowledge_refs(refs_raw if isinstance(refs_raw, list) else [])
        # 获取用户上传的图片
        user_att = (
            json.dumps({"upload_image_ids": req.image_ids}, ensure_ascii=False)
            if req.image_ids
            else None
        )
        # 调用chat_repo.save_chat方法保存用户消息
        chat_repo.save_chat(db, req.session_id, "user", eff_task, user_att)
        # 调用chat_repo.save_chat方法保存LangGraph的回复
        agent_att = (
            json.dumps({"referenced_images": pub_refs}, ensure_ascii=False)
            if pub_refs
            else None
        )
        chat_repo.save_chat(db, req.session_id, "agent", agent_reply, agent_att)

        return {
            "code": 200,
            "session_id": req.session_id,
            "checkpoint_thread_id": checkpoint_thread_id,
            "data": agent_reply,
            "referenced_images": pub_refs,
        }
    except HTTPException:
        raise
    except AgentExecutionTimeoutError as e:
        task_run_repo.mark_failed(db, checkpoint_thread_id, str(e))
        raise HTTPException(status_code=504, detail=str(e)) from e
    except Exception as e:
        task_run_repo.mark_failed(db, checkpoint_thread_id, str(e))
        raise e


@router.get("/sessions")
def agent_session_list(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="返回最近若干条会话"),
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_TASK_OBSERVE)),
):
    """会话列表：按最后一条消息时间倒序，含首条用户话预览。"""
    items = chat_repo.list_sessions(db, limit=limit)
    return {"code": 200, "data": items}


@router.get("/chat/history")
def agent_chat_history(
    request: Request,
    session_id: str = Query(..., min_length=1, description="会话 ID"),
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_TASK_OBSERVE)),
):
    """拉取某会话全部消息，供前端刷新后恢复多轮界面。"""
    rows = chat_repo.get_history(db, session_id)
    return {"code": 200, "session_id": session_id, "data": rows}


@router.post("/task/resume")
def agent_task_resume(
    request: Request,
    body: TaskResumeReq,
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    ensure_agent_allowed(request, "default")
    """从 LangGraph 检查点继续执行完整图（invoke(None)）。适用于进程中断、人工暂停后续跑。"""
    tid = body.checkpoint_thread_id.strip()
    if not tid:
        raise HTTPException(status_code=400, detail="checkpoint_thread_id 不能为空")
    cfg = _invoke_cfg(tid)
    snap = agent_graph.graph.get_state(cfg)
    vals = snap.values or {}
    nxt = tuple(snap.next) if snap.next is not None else ()
    if not vals:
        raise HTTPException(
            status_code=404,
            detail="未找到该 checkpoint_thread_id 的检查点，请先使用 POST /chat 且传入相同 id",
        )
    if not nxt:
        return {
            "code": 200,
            "msg": "already_finished",
            "checkpoint_thread_id": tid,
            "data": dict(vals),
        }
    task_run_repo.upsert_start(db, tid, None, "[resume]")
    try:
        res = invoke_langgraph_with_timeout(
            agent_graph.graph,
            None,
            cfg,
            settings.AGENT_GRAPH_TIMEOUT_SEC,
        )
        out = res.get("result", "")
        task_run_repo.mark_completed(db, tid, str(out))
        return {
            "code": 200,
            "msg": "ok",
            "checkpoint_thread_id": tid,
            "data": res,
        }
    except AgentExecutionTimeoutError as e:
        task_run_repo.mark_failed(db, tid, str(e))
        raise HTTPException(status_code=504, detail=str(e)) from e
    except Exception as e:
        task_run_repo.mark_failed(db, tid, str(e))
        raise


@router.get("/task/status")
def agent_task_status(
    request: Request,
    checkpoint_thread_id: str = Query(..., min_length=1),
    _: None = Depends(require_perm(PERM_TASK_OBSERVE)),
):
    """查看某 checkpoint_thread_id 在完整图中的下一待执行节点与状态键。"""
    cfg = _invoke_cfg(checkpoint_thread_id)
    snap = agent_graph.graph.get_state(cfg)
    vals = snap.values or {}
    nxt = list(snap.next) if snap.next is not None else []
    return {
        "code": 200,
        "checkpoint_thread_id": checkpoint_thread_id,
        "data": {
            "next_nodes": nxt,
            "has_result": bool(vals.get("result")),
            "state_keys": list(vals.keys()),
        },
    }


@router.get("/task/runs")
def agent_task_runs_list(
    request: Request,
    limit: int = Query(30, ge=1, le=200),
    session_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_TASK_OBSERVE)),
):
    """任务运行记录列表（业务表 agent_task_run），便于与检查点 thread_id 对照。"""
    rows = task_run_repo.list_runs(db, limit=limit, session_id=session_id)
    return {"code": 200, "data": rows}


@router.get("/templates")
def list_agent_templates(
    request: Request,
    _: None = Depends(require_perm(PERM_TEMPLATES_READ)),
):
    rows = list_templates()
    p = get_principal(request)
    if p.role == Role.BUSINESS and p.agent_allowlist is not None:
        rows = [r for r in rows if r.get("agent_id") in p.agent_allowlist]
    return {"code": 200, "data": rows}


@router.post("/templates")
def create_agent_template(
    body: AgentTemplateCreateReq,
    _: None = Depends(require_perm(PERM_TEMPLATES_WRITE)),
):
    try:
        row = create_template(body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"code": 200, "data": row}


@router.delete("/templates/{template_id}")
def remove_agent_template(
    template_id: str,
    _: None = Depends(require_perm(PERM_TEMPLATES_WRITE)),
):
    try:
        ok = delete_template(template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"code": 200, "msg": "ok"}


@router.get("/logs/api")
def list_api_logs_route(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_LOGS_READ)),
):
    rows = log_repo.list_api_logs(db, limit=limit, offset=offset)
    return {"code": 200, "data": rows}


@router.get("/logs/errors")
def list_error_logs_route(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_LOGS_READ)),
):
    rows = log_repo.list_error_logs(db, limit=limit, offset=offset)
    return {"code": 200, "data": rows}


@router.get("/visualize")
def visualize_graph(_: None = Depends(require_perm(PERM_GRAPH_VISUALIZE))):
    try:
        img = agent_graph.graph.get_graph().draw_mermaid_png()
        return Response(content=img, media_type="image/png")
    except Exception as e:
        return Response(
            content=f"可视化失败: {str(e)}", media_type="text/plain", status_code=500
        )


def _sse_data(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def agent_chat_stream(
    request: Request,
    req: AgentChatReq,
    db: Session = Depends(get_db),
    _: None = Depends(require_perm(PERM_TASK_EXECUTE)),
):
    """SSE：图跑到汇总节点前暂停，再以带重试/降级的流式汇总输出最终回复。"""
    ensure_langgraph_chat(request, req.agent_id)

    async def event_gen():
        try:
            paths = _resolve_user_image_paths(req.image_ids)
            eff_task = _effective_chat_task(req.task, paths)
            if not eff_task:
                yield _sse_data(
                    {"event": "error", "message": "task与图片不能同时为空"}
                )
                return

            session_id = req.session_id or chat_repo.gen_session_id()
            yield _sse_data({"event": "session", "session_id": session_id})

            deadline = (
                time.monotonic() + settings.AGENT_GRAPH_TIMEOUT_SEC
                if settings.AGENT_GRAPH_TIMEOUT_SEC > 0
                else None
            )

            history = chat_repo.get_history(db, session_id)
            initial = {
                "task": eff_task,
                "is_safe": False,
                "need_tool": False,
                "tool_name": "",
                "tool_params": [],
                "result": "",
                "history": history,
                "rag_context": "",
                "resolved_retrieval_query": "",
                "sub_tasks": [],
                "agent_type": "",
                "task_output": "",
                "final_summary": "",
                "skip_summary_llm": False,
                "user_image_paths": paths,
                "rag_referenced_images": [],
            }

            try:
                if deadline is not None:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        yield _sse_data(
                            {
                                "event": "error",
                                "message": f"【告警】任务总时限 {settings.AGENT_GRAPH_TIMEOUT_SEC:.0f}s 已用尽。",
                            }
                        )
                        return
                    state = await asyncio.wait_for(
                        asyncio.to_thread(
                            agent_graph.graph_pre_summary.invoke,
                            initial,
                        ),
                        timeout=max(0.01, left),
                    )
                else:
                    state = await asyncio.to_thread(
                        agent_graph.graph_pre_summary.invoke,
                        initial,
                    )
            except asyncio.TimeoutError:
                logger.warning(
                    "【告警】SSE LangGraph 前置阶段超时：limit=%.0fs",
                    settings.AGENT_GRAPH_TIMEOUT_SEC,
                )
                yield _sse_data(
                    {
                        "event": "error",
                        "message": f"【告警】Agent 图执行已超过 {settings.AGENT_GRAPH_TIMEOUT_SEC:.0f} 秒，已终止等待。",
                    }
                )
                return

            if not state.get("is_safe", True):
                yield _sse_data(
                    {"event": "error", "message": "内容未通过安全校验"}
                )
                return

            refs_raw = state.get("rag_referenced_images") or []
            pub_refs = _public_knowledge_refs(
                refs_raw if isinstance(refs_raw, list) else []
            )
            if pub_refs:
                yield _sse_data(
                    {"event": "refs", "referenced_images": pub_refs}
                )

            task_out = state.get("task_output") or ""

            full_parts: list[str] = []
            if state.get("skip_summary_llm"):
                msg = task_out.strip() or settings.LLM_FAILURE_HANDOFF_MESSAGE
                full_parts.append(msg)
                yield _sse_data({"event": "delta", "text": msg})
            else:
                try:
                    async for piece in async_iterate_summary_stream(
                        lambda: summary_agent_stream(eff_task, task_out, history),
                        deadline,
                    ):
                        full_parts.append(piece)
                        yield _sse_data({"event": "delta", "text": piece})
                except AgentExecutionTimeoutError as e:
                    yield _sse_data({"event": "error", "message": str(e)})
                    return

            agent_reply = "".join(full_parts)
            user_att = (
                json.dumps({"upload_image_ids": req.image_ids}, ensure_ascii=False)
                if req.image_ids
                else None
            )
            chat_repo.save_chat(db, session_id, "user", eff_task, user_att)
            agent_att = (
                json.dumps({"referenced_images": pub_refs}, ensure_ascii=False)
                if pub_refs
                else None
            )
            chat_repo.save_chat(db, session_id, "agent", agent_reply, agent_att)
            yield _sse_data({"event": "done"})
        except Exception as e:
            yield _sse_data({"event": "error", "message": str(e)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )