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
    # LangGraph 检查点（与业务库分离；用于完整图 invoke 断点续跑）
    LANGGRAPH_CHECKPOINT_SQLITE_PATH = os.getenv(
        "LANGGRAPH_CHECKPOINT_SQLITE_PATH",
        "./data/langgraph_checkpoints.sqlite",
    )

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

    # 知识库图片：CLIP 索引与检索（与文本 RAG 共用 RAG_KNOWLEDGE_DIR）
    IMAGE_RAG_ENABLE = os.getenv("IMAGE_RAG_ENABLE", "true").lower() in ("true", "1", "yes")
    IMAGE_RAG_INDEX_DIR = os.getenv("IMAGE_RAG_INDEX_DIR", "./data")
    IMAGE_RAG_CLIP_MODEL = os.getenv("IMAGE_RAG_CLIP_MODEL", "clip-ViT-B-32")
    IMAGE_RAG_TOP_K = int(os.getenv("IMAGE_RAG_TOP_K", "3"))
    IMAGE_RAG_EXTENSIONS = os.getenv(
        "IMAGE_RAG_EXTENSIONS", ".png,.jpg,.jpeg,.webp,.gif,.bmp"
    )
    IMAGE_RAG_MAX_CONTEXT_CHARS = int(os.getenv("IMAGE_RAG_MAX_CONTEXT_CHARS", "1200"))
    # 索引时可选：需 pip install transformers（体积较大）；也可用「图片同目录 .caption.txt」侧写描述
    IMAGE_RAG_BLIP_CAPTION = os.getenv("IMAGE_RAG_BLIP_CAPTION", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    IMAGE_RAG_BLIP_MODEL = os.getenv(
        "IMAGE_RAG_BLIP_MODEL", "Salesforce/blip-image-captioning-base"
    )
    IMAGE_RAG_BLIP_MAX_LENGTH = int(os.getenv("IMAGE_RAG_BLIP_MAX_LENGTH", "48"))
    # 用户上传图与文本问句的 CLIP 融合权重（和为 1 时由归一化保证）
    IMAGE_RAG_TEXT_WEIGHT = float(os.getenv("IMAGE_RAG_TEXT_WEIGHT", "0.65"))
    IMAGE_RAG_USER_IMAGE_WEIGHT = float(os.getenv("IMAGE_RAG_USER_IMAGE_WEIGHT", "0.35"))

    # AI 问数（NL2SQL + 词典向量库 + SQL 校验）：Chroma 与主 RAG 分目录，避免互相覆盖
    ANALYTICS_CHROMA_DIR = os.getenv("ANALYTICS_CHROMA_DIR", "./chroma_analytics")
    ANALYTICS_TOP_K = int(os.getenv("ANALYTICS_TOP_K", "8"))
    ANALYTICS_ROW_LIMIT = int(os.getenv("ANALYTICS_ROW_LIMIT", "200"))
    ANALYTICS_ALLOWED_TABLE_PREFIX = os.getenv("ANALYTICS_ALLOWED_TABLE_PREFIX", "ma_")
    # 业务词典 YAML（表别名、指标口径、推理映射）；不存在时仅用库表结构建索引
    ANALYTICS_BUSINESS_YAML = os.getenv(
        "ANALYTICS_BUSINESS_YAML", "./knowledge/analytics_business.yaml"
    )

    # 聊天附图上传（POST /chat/upload-image）
    CHAT_UPLOAD_DIR = os.getenv("CHAT_UPLOAD_DIR", "./data/chat_uploads")
    CHAT_UPLOAD_MAX_BYTES = int(os.getenv("CHAT_UPLOAD_MAX_BYTES", str(4 * 1024 * 1024)))
    CHAT_MAX_IMAGES_PER_MESSAGE = int(os.getenv("CHAT_MAX_IMAGES_PER_MESSAGE", "4"))

    # LLM 重试与降级（备用模型 / 人工接管提示）
    LLM_RETRY_MAX = int(os.getenv("LLM_RETRY_MAX", "3"))
    LLM_RETRY_BACKOFF_SEC = float(os.getenv("LLM_RETRY_BACKOFF_SEC", "0.6"))
    LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "").strip()
    LLM_FAILURE_DEGRADE_PREFIX = os.getenv("LLM_FAILURE_DEGRADE_PREFIX", "【系统降级】")
    LLM_FAILURE_HANDOFF_MESSAGE = os.getenv(
        "LLM_FAILURE_HANDOFF_MESSAGE",
        "【系统降级】大模型多次调用仍失败（网络超时/额度或服务异常）。请稍后重试或联系人工处理。",
    )

    # 工具重试：核心工具多轮，其它工具少轮；失败后降级提示
    TOOL_RETRY_CORE = int(os.getenv("TOOL_RETRY_CORE", "3"))
    TOOL_RETRY_OTHER = int(os.getenv("TOOL_RETRY_OTHER", "1"))
    _TOOL_CORE_NAMES_RAW = os.getenv(
        "TOOL_CORE_NAMES",
        "add,subtract,multiply,divide,get_now_time,get_now_date",
    )
    TOOL_CORE_NAMES_SET = frozenset(
        n.strip() for n in _TOOL_CORE_NAMES_RAW.split(",") if n.strip()
    )
    TOOL_FAILURE_HANDOFF_MESSAGE = os.getenv(
        "TOOL_FAILURE_HANDOFF_MESSAGE",
        "【系统降级】工具多次执行仍失败。请检查参数或联系人工处理。",
    )

    # RBAC（API Key → 角色；关闭 RBAC_ENABLED 时不校验，等价管理员）
    RBAC_ENABLED = os.getenv("RBAC_ENABLED", "false").lower() in ("true", "1", "yes")
    RBAC_ADMIN_API_KEYS = os.getenv("RBAC_ADMIN_API_KEYS", "")
    RBAC_DEVELOPER_API_KEYS = os.getenv("RBAC_DEVELOPER_API_KEYS", "")
    RBAC_BUSINESS_API_KEYS = os.getenv("RBAC_BUSINESS_API_KEYS", "")
    RBAC_BUSINESS_AGENT_IDS = os.getenv("RBAC_BUSINESS_AGENT_IDS", "default")
    # 业务用户问数：可选分院编码白名单（逗号分隔，如 SH-XH-01,SH-PD-02）。空=不限制（与管理员/开发者一致）
    RBAC_BUSINESS_ANALYTICS_BRANCH_CODES = os.getenv(
        "RBAC_BUSINESS_ANALYTICS_BRANCH_CODES", ""
    ).strip()
    AGENT_TEMPLATES_FILE = os.getenv("AGENT_TEMPLATES_FILE", "./data/agent_templates.json")

    # Agent 整图 / SSE 总时限（图执行 + SSE 流式汇总共享同一墙钟预算，<=0 表示不限制）
    AGENT_GRAPH_TIMEOUT_SEC = float(os.getenv("AGENT_GRAPH_TIMEOUT_SEC", "600"))
    # 单次工具同步调用墙钟上限（<=0 表示不限制）
    TOOL_CALL_TIMEOUT_SEC = float(os.getenv("TOOL_CALL_TIMEOUT_SEC", "30"))

settings = Settings()