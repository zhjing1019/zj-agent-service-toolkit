from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from db.base import get_db
from db.log_repo import log_repo

def register_exception_handler(app: FastAPI):
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # 异常入库
        db = next(get_db())
        log_repo.save_error_log(db, exc)

        return JSONResponse(
            status_code=500,
            content={"code":500, "msg":"服务器内部异常", "detail":str(exc)}
        )