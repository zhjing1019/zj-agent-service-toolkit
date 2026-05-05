import logging
import os
from datetime import datetime
from config.settings import settings

# 日志文件夹
log_dir = "logs"
if not os.path.exists(log_dir):
    os.mkdir(log_dir)

# 日志文件名
log_file = os.path.join(log_dir, f"agent_{datetime.now().strftime('%Y%m%d')}.log")

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 全局日志实例
logger = logging.getLogger("agent-service-toolkit")