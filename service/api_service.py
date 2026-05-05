# 升级成 HTTP 接口服务

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.base_agent import BaseAgent

# 初始化FastAPI路由
router = APIRouter()
# 初始化智能体
agent = BaseAgent()

class TaskRequest(BaseModel):
    task: str

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