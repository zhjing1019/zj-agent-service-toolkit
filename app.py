from fastapi import FastAPI
from db.init_db import init_database
from service.api_service import router

app = FastAPI(title="DeepSeek + LangGraph Agent")
app.include_router(router)

@app.on_event("startup")
def startup():
    init_database()