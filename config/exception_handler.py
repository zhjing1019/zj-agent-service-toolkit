from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse

def register_exception_handler(app: FastAPI):
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"code":500, "msg":"服务器内部异常", "detail":str(exc)}
        )