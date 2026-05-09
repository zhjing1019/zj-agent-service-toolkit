# 升级成 HTTP 接口服务

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.base_agent import BaseAgent
from sqlalchemy.orm import Session
from core.graph import agent_graph
from core.multi_agent import summary_agent_stream
from db.base import get_db
from db.repository import chat_repo
from core.admin import reset_all_chat_session, switch_llm_model



class AgentChatReq(BaseModel):
    session_id: str | None = None
    task: str

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
    try:
        # 无会话ID自动生成
        if not req.session_id:
            req.session_id = chat_repo.gen_session_id()

        # 读取历史会话
        history = chat_repo.get_history(db, req.session_id)

        # 执行LangGraph工作流
        res = agent_graph.graph.invoke({
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
        })

        agent_reply = res["result"]

        # 保存聊天记录
        chat_repo.save_chat(db, req.session_id, "user", req.task)
        chat_repo.save_chat(db, req.session_id, "agent", agent_reply)

        return {
            "code": 200,
            "session_id": req.session_id,
            "data": agent_reply
        }
    except Exception as e:
        raise e


def _sse_data(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def agent_chat_stream(req: AgentChatReq, db: Session = Depends(get_db)):
    """SSE：图跑到汇总节点前暂停，再以 llm.stream 流式输出最终回复。"""

    async def event_gen():
        try:
            if not (req.task or "").strip():
                yield _sse_data({"event": "error", "message": "task不能为空"})
                return

            session_id = req.session_id or chat_repo.gen_session_id()
            yield _sse_data({"event": "session", "session_id": session_id})

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
            }

            state = await asyncio.to_thread(
                agent_graph.graph_pre_summary.invoke,
                initial,
            )

            if not state.get("is_safe", True):
                yield _sse_data(
                    {"event": "error", "message": "内容未通过安全校验"}
                )
                return

            task_out = state.get("task_output") or ""

            full_parts: list[str] = []
            for piece in summary_agent_stream(req.task, task_out):
                full_parts.append(piece)
                yield _sse_data({"event": "delta", "text": piece})

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