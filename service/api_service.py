# 升级成 HTTP 接口服务

from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Depends
from pydantic import BaseModel
from agent.base_agent import BaseAgent
import shutil
from core.rag import load_knowledge_to_vector_incremental
from config.limiter import limiter
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.graph import agent_graph
from db.base import get_db
from db.repository import chat_repo
from db.log_repo import log_repo
from config.limiter import limiter


class AgentChatReq(BaseModel):
    session_id: str | None = None
    task: str

# 初始化FastAPI路由
router = APIRouter(prefix="/api/agent", tags=["Agent对话"])
# 初始化智能体
agent = BaseAgent()

class TaskRequest(BaseModel):
    task: str

@router.post("/upload/knowledge")
async def upload_knowledge_file(file: UploadFile = File(...)):
    """上传 txt/md/pdf 知识库文件，自动增量入库"""
    know_dir = settings.RAG_KNOWLEDGE_DIR
    os.makedirs(know_dir, exist_ok=True)

    # 保存文件到知识库目录
    save_path = os.path.join(know_dir, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 增量向量化入库
    load_knowledge_to_vector_incremental()
    return {"code": 200, "msg": "文件上传并入库成功", "filename": file.filename}

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
@limiter.limit("20/minute")
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
            "rag_context": ""
        })

        agent_reply = res["result"]

        # 保存聊天记录
        chat_repo.save_chat(db, req.session_id, "user", req.task)
        chat_repo.save_chat(db, req.session_id, "agent", agent_reply)

        # 保存接口访问日志
        client_ip = request.client.host
        log_repo.save_api_log(db, req.session_id, req.task, agent_reply, "success", client_ip)

        return {
            "code": 200,
            "session_id": req.session_id,
            "data": agent_reply
        }
    except Exception as e:
        client_ip = request.client.host
        log_repo.save_api_log(db, req.session_id or "", req.task, str(e), "fail", client_ip)
        raise e