from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    # 服务
    SERVICE_NAME = os.getenv("SERVICE_NAME")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # DeepSeek
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # DB
    SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/agent.db")

    # 安全
    SAFE_MODE = os.getenv("SAFE_MODE", "True") == "True"

    # 工具配置
    DEFAULT_FILE_NAME = os.getenv("DEFAULT_FILE_NAME", "output.txt")
    MAX_MEMORY = int(os.getenv("MAX_MEMORY", 10))

    # RAG 知识库
    RAG_KNOWLEDGE_DIR = os.getenv("RAG_KNOWLEDGE_DIR", "./knowledge")
    CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    # 嵌入模型下载：国内/弱网可设镜像与超时（见 .env 示例）
    HF_ENDPOINT = os.getenv("HF_ENDPOINT", "").strip().rstrip("/")
    HF_HUB_DOWNLOAD_TIMEOUT = int(os.getenv("HF_HUB_DOWNLOAD_TIMEOUT", "300"))
    HUGGINGFACE_HUB_CACHE = os.getenv("HUGGINGFACE_HUB_CACHE", "").strip()

    # RAG 高级参数
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", 3))
    RAG_MAX_CONTEXT_LEN = int(os.getenv("RAG_MAX_CONTEXT_LEN", 2000))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 512))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 60))

    # RAG 指代消解：检索前用 LLM 将「它」等改写为独立问句（仅 RAG 检索节点使用）
    RAG_COREFERENCE_ENABLE = os.getenv("RAG_COREFERENCE_ENABLE", "true").lower() in ("true", "1", "yes")
    RAG_COREFERENCE_MAX_MESSAGES = int(os.getenv("RAG_COREFERENCE_MAX_MESSAGES", "12"))

    # 多模型配置
    DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # 混合检索 BM25 + 向量（.env 里用 true/false 字符串，勿写 Python 的 true/True 到错误位置）
    HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", os.getenv("RAG_TOP_K", "3")))
    BM25_TOP_K = int(os.getenv("BM25_TOP_K", os.getenv("RAG_TOP_K", "3")))
    RERANK_ENABLE = os.getenv("RERANK_ENABLE", "false").lower() in ("true", "1", "yes")

settings = Settings()