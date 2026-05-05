# 升级成 HTTP 接口服务

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from agent.base_agent import BaseAgent
import shutil
from core.rag import load_knowledge_to_vector_incremental

# 初始化FastAPI路由
router = APIRouter()
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