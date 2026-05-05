# 编写项目入口 main.py
from service.local_service import LocalService

if __name__ == "__main__":
    # 启动本地服务
    servece = LocalService()
    servece.chat()
