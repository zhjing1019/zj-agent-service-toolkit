from db.init_db import init_database
from service.cli import run_cli

# 初始化数据库
init_database()

if __name__ == "__main__":
    run_cli()