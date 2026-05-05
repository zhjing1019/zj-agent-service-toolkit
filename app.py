from fastapi import FastAPI, Depends
from pydantic import BaseModel
from core.graph import agent_graph
from db.init_db import init_database
from db.repository import chat_repo
from db.base import get_db, Session

app = FastAPI(title="LangGraph Agent SQLite 会话版")

@app.on_event("startup")
def startup():
    init_database()

class AgentTaskReq(BaseModel):
    session_id: str | None = None
    task: str

@app.post("/api/agent/chat")
def agent_chat(req: AgentTaskReq, db: Session = Depends(get_db)):
    # 没有会话ID就新建
    if not req.session_id:
        req.session_id = chat_repo.gen_session_id()

    # 读取历史
    history = chat_repo.get_history(db, req.session_id)

    # 执行工作流
    res = agent_graph.graph.invoke({
        "task": req.task,
        "is_safe": False,
        "tool_name": "",
        "tool_params": [],
        "result": "",
        "history": history
    })

    # 保存对话
    chat_repo.save_chat(db, req.session_id, "user", req.task)
    chat_repo.save_chat(db, req.session_id, "agent", res["result"])

    return {
        "code": 200,
        "session_id": req.session_id,
        "data": res["result"]
    }