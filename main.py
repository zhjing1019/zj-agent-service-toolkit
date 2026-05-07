import sys

from db.init_db import init_database
from service.cli import run_cli

# 初始化数据库
init_database()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--index-rag":
        from core.rag import load_knowledge_to_vector_incremental

        rebuild = "--rebuild" in sys.argv
        load_knowledge_to_vector_incremental(rebuild=rebuild)
    else:
        run_cli()