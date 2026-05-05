from fastapi import FastAPI, Response
from db.init_db import init_database
from service.api_service import router
from core.graph import agent_graph

app = FastAPI(title="DeepSeek + LangGraph Agent")
app.include_router(router)

@app.get("/api/agent/visualize")
def visualize_graph():
    try:
        # 使用get_graph()获取图结构，然后生成mermaid格式的PNG图片
        img = agent_graph.graph.get_graph().draw_mermaid_png()
        return Response(content=img, media_type="image/png")
    except Exception as e:
        return Response(content=f"可视化失败: {str(e)}", media_type="text/plain", status_code=500)

@app.on_event("startup")
def startup():
    init_database()