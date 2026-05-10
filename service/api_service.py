# 升级成 HTTP 接口服务

import asyncio
import json
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.base_agent import BaseAgent
from sqlalchemy.orm import Session
from config.logger import logger
from config.settings import settings
from core.graph import agent_graph
from core.multi_agent import summary_agent_stream
from core.task_timeout import (
    AgentExecutionTimeoutError,
    async_iterate_summary_stream,
    invoke_langgraph_with_timeout,
)
from db.base import get_db
from db.repository import chat_repo
from db.task_run_repo import task_run_repo
from core.admin import reset_all_chat_session, switch_llm_model



class AgentChatReq(BaseModel):
    session_id: str | None = None
    task: str
    # 与 LangGraph SqliteSaver 的 thread_id 对齐；不传则每次新任务。仅对 POST /chat 生效。
    checkpoint_thread_id: str | None = None

class TaskResumeReq(BaseModel):
    checkpoint_thread_id: str


def _invoke_cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


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


# 初始化FastAPI路由
router = APIRouter(prefix="/api/agent", tags=["Agent对话"])
# 初始化智能体
agent = BaseAgent()

class TaskRequest(BaseModel):
    task: str

# 运维：清空所有会话历史
@router.post("/admin/reset-session")
def api_reset_session(db: Session = Depends(get_db)):
    return reset_all_chat_session(db)

# 运维：动态切换模型
@router.post("/admin/switch-llm")
def api_switch_llm(provider: str = Query(..., description="支持 deepseek / openai")):
    return switch_llm_model(provider)


@router.post("/admin/index-rag")
def api_index_rag(rebuild: bool = Query(False, description="为 true 时清空 Chroma 目录后全量重建")):
    """扫描 RAG_KNOWLEDGE_DIR（默认 ./knowledge）下 pdf/txt/md 写入向量库与 BM25。"""
    from core.rag import load_knowledge_to_vector_incremental

    load_knowledge_to_vector_incremental(rebuild=rebuild)
    return {"code": 200, "msg": "ok", "data": {"rebuild": rebuild}}

@router.post("/api/agent/run")
def agent_run(request: TaskRequest):
    task = request.task
    if not task:
        raise HTTPException(status_code=400, detail="task不能为空")

    result = agent.run(task)
    return {
        "code": 200,
        "msg": "ok",
        "data": result
    }

# 接口：查看记忆
@router.get("/api/agent/memory")
def agent_memory():
    memory_list = agent.get_memory()
    return {
        "code": 200,
        "msg": "ok",
        "data": memory_list
    }

@router.post("/chat")
def agent_chat(request: Request, req: AgentChatReq, db: Session = Depends(get_db)):
    checkpoint_thread_id = (req.checkpoint_thread_id or "").strip() or str(
        uuid.uuid4()
    )
    try:
        if not req.session_id:
            req.session_id = chat_repo.gen_session_id()

        _assert_new_chat_invoke_allowed(checkpoint_thread_id)

        history = chat_repo.get_history(db, req.session_id)
        initial = {
            "task": req.task,
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
        }

        task_run_repo.upsert_start(
            db, checkpoint_thread_id, req.session_id, req.task or ""
        )
        cfg = _invoke_cfg(checkpoint_thread_id)
        res = invoke_langgraph_with_timeout(
            agent_graph.graph,
            initial,
            cfg,
            settings.AGENT_GRAPH_TIMEOUT_SEC,
        )

        agent_reply = res["result"]
        task_run_repo.mark_completed(db, checkpoint_thread_id, agent_reply)

        chat_repo.save_chat(db, req.session_id, "user", req.task)
        chat_repo.save_chat(db, req.session_id, "agent", agent_reply)

        return {
            "code": 200,
            "session_id": req.session_id,
            "checkpoint_thread_id": checkpoint_thread_id,
            "data": agent_reply,
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
    limit: int = Query(50, ge=1, le=200, description="返回最近若干条会话"),
    db: Session = Depends(get_db),
):
    """会话列表：按最后一条消息时间倒序，含首条用户话预览。"""
    items = chat_repo.list_sessions(db, limit=limit)
    return {"code": 200, "data": items}


@router.get("/chat/history")
def agent_chat_history(
    session_id: str = Query(..., min_length=1, description="会话 ID"),
    db: Session = Depends(get_db),
):
    """拉取某会话全部消息，供前端刷新后恢复多轮界面。"""
    rows = chat_repo.get_history(db, session_id)
    return {"code": 200, "session_id": session_id, "data": rows}


@router.post("/task/resume")
def agent_task_resume(body: TaskResumeReq, db: Session = Depends(get_db)):
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
    checkpoint_thread_id: str = Query(..., min_length=1),
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
    limit: int = Query(30, ge=1, le=200),
    session_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """任务运行记录列表（业务表 agent_task_run），便于与检查点 thread_id 对照。"""
    rows = task_run_repo.list_runs(db, limit=limit, session_id=session_id)
    return {"code": 200, "data": rows}


def _sse_data(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def agent_chat_stream(req: AgentChatReq, db: Session = Depends(get_db)):
    """SSE：图跑到汇总节点前暂停，再以带重试/降级的流式汇总输出最终回复。"""

    async def event_gen():
        try:
            if not (req.task or "").strip():
                yield _sse_data({"event": "error", "message": "task不能为空"})
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
                "task": req.task,
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

            task_out = state.get("task_output") or ""

            full_parts: list[str] = []
            if state.get("skip_summary_llm"):
                msg = task_out.strip() or settings.LLM_FAILURE_HANDOFF_MESSAGE
                full_parts.append(msg)
                yield _sse_data({"event": "delta", "text": msg})
            else:
                try:
                    async for piece in async_iterate_summary_stream(
                        lambda: summary_agent_stream(req.task, task_out, history),
                        deadline,
                    ):
                        full_parts.append(piece)
                        yield _sse_data({"event": "delta", "text": piece})
                except AgentExecutionTimeoutError as e:
                    yield _sse_data({"event": "error", "message": str(e)})
                    return

            agent_reply = "".join(full_parts)
            chat_repo.save_chat(db, session_id, "user", req.task)
            chat_repo.save_chat(db, session_id, "agent", agent_reply)
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