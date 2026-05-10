from fastapi import FastAPI
from db.init_db import init_database
from service.api_service import router
from config.exception_handler import register_exception_handler
from config.limiter import register_limiter

app = FastAPI(title="DeepSeek + LangGraph Agent")
app.include_router(router)

# 注册限流、全局异常
register_limiter(app)
register_exception_handler(app)


@app.on_event("startup")
def startup():
    init_database()
