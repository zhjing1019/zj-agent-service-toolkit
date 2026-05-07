import os
import shutil
from typing import List, Dict
from rank_bm25 import BM25Okapi
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from config.settings import settings


def _apply_hf_hub_env():
    """在创建 SentenceTransformer 前设置 Hub 环境，减轻直连 huggingface.co 超时。"""
    if settings.HF_ENDPOINT:
        os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(settings.HF_HUB_DOWNLOAD_TIMEOUT)
    if settings.HUGGINGFACE_HUB_CACHE:
        os.environ["HUGGINGFACE_HUB_CACHE"] = settings.HUGGINGFACE_HUB_CACHE


_apply_hf_hub_env()

# 初始化嵌入模型（首次会从 Hub 拉取；已缓存则走本地）
embedding = SentenceTransformerEmbeddings(model_name=settings.EMBEDDING_MODEL)

# 全局缓存：用于BM25
all_chunks: List[str] = []
bm25_model: BM25Okapi | None = None

# 文本切分器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP
)

def load_file_docs(file_path: str):
    """根据后缀自动加载 txt/md/pdf（后缀不区分大小写）"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".txt", ".md"):
        loader = TextLoader(file_path, encoding="utf-8")
    elif ext == ".pdf":
        loader = PyPDFLoader(file_path)
    else:
        return []
    return loader.load()


def _iter_knowledge_files(know_dir: str) -> List[str]:
    """递归收集 knowledge 目录下支持的文件路径。"""
    paths: List[str] = []
    if not os.path.isdir(know_dir):
        return paths
    for root, _dirs, files in os.walk(know_dir):
        for fname in files:
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".pdf", ".txt", ".md"):
                continue
            paths.append(os.path.join(root, fname))
    return sorted(paths)


def load_knowledge_to_vector_incremental(rebuild: bool = False):
    """扫描 knowledge 目录，向量化写入 Chroma，并构建 BM25 索引。

    :param rebuild: True 时先清空本地 Chroma 目录再全量重建（适合更新 PDF 后避免重复块）。
    """
    global all_chunks, bm25_model
    know_dir = os.path.abspath(settings.RAG_KNOWLEDGE_DIR)
    os.makedirs(know_dir, exist_ok=True)
    db_dir = os.path.abspath(settings.CHROMA_DB_DIR)
    os.makedirs(db_dir, exist_ok=True)

    if rebuild and os.path.isdir(db_dir):
        shutil.rmtree(db_dir)
        os.makedirs(db_dir, exist_ok=True)
        all_chunks = []
        bm25_model = None

    all_docs = []
    for fp in _iter_knowledge_files(know_dir):
        try:
            docs = load_file_docs(fp)
            if docs:
                for d in docs:
                    d.metadata = {**(d.metadata or {}), "source": fp}
                all_docs.extend(docs)
        except Exception as e:
            print(f"⚠️ 跳过文件（读取失败）: {fp}\n   {e}")

    if not all_docs:
        print(f"ℹ️ 在目录中未找到可入库文件: {know_dir}\n   支持: .pdf .txt .md（含子目录）")
        return

    splits = text_splitter.split_documents(all_docs)
    # 保存文本块给BM25
    all_chunks = [d.page_content.strip() for d in splits]

    # 1. 向量库入库
    Chroma.from_documents(
        documents=splits,
        embedding=embedding,
        persist_directory=db_dir
    )

    # 2. 构建BM25索引
    tokenized_corpus = [chunk.split() for chunk in all_chunks]
    bm25_model = BM25Okapi(tokenized_corpus)
    n_sources = len({(d.metadata or {}).get("source", "") for d in all_docs})
    print(f"✅ 向量库 + BM25 索引构建完成（共 {len(splits)} 条文本块，来自 {n_sources} 个源文件）")

def bm25_retrieve(query: str, top_k: int = 3) -> List[str]:
    """BM25 关键词检索"""
    if not bm25_model or not all_chunks:
        return []
    tokenized_query = query.split()
    top_indices = bm25_model.get_top_n(tokenized_query, all_chunks, n=top_k)
    return top_indices

def vector_retrieve(query: str, top_k: int = 3) -> List[str]:
    """向量语义检索"""
    db = Chroma(
        persist_directory=settings.CHROMA_DB_DIR,
        embedding_function=embedding
    )
    res = db.similarity_search(query, k=top_k)
    return [d.page_content.strip() for d in res]

def hybrid_retrieve(query: str) -> str:
    """混合检索：BM25关键词 + 向量语义 融合"""
    # 两路检索
    bm25_res = bm25_retrieve(query, settings.BM25_TOP_K)
    vec_res = vector_retrieve(query, settings.HYBRID_TOP_K)

    # 合并去重
    combined = []
    seen = set()
    for doc in bm25_res + vec_res:
        if doc not in seen:
            seen.add(doc)
            combined.append(doc)

    # 拼接上下文
    context = "\n\n".join(combined)
    # 截断超长
    if len(context) > settings.RAG_MAX_CONTEXT_LEN:
        context = context[:settings.RAG_MAX_CONTEXT_LEN] + "\n...（内容截断）"
    return context

def query_knowledge(question: str) -> str:
    """检索知识库：有 BM25 索引时用混合检索，否则仅向量检索。"""
    if bm25_model and all_chunks:
        return hybrid_retrieve(question)
    db = Chroma(
        persist_directory=settings.CHROMA_DB_DIR,
        embedding_function=embedding
    )
    res = db.similarity_search(question, k=settings.RAG_TOP_K)
    context = "\n".join([d.page_content.strip() for d in res])
    if len(context) > settings.RAG_MAX_CONTEXT_LEN:
        context = context[: settings.RAG_MAX_CONTEXT_LEN] + "\n...（内容已截断）"
    return context


def query_knowledge_with_history(question: str, history_list: List[Dict]) -> str:
    """拼接历史对话 + 当前问题，再做 RAG（混合或向量）。"""
    history_text = ""
    for item in history_list[-6:]:
        history_text += f"{item['role']}：{item['content']}\n"
    full_query = f"对话历史：\n{history_text}\n当前问题：{question}"
    return query_knowledge(full_query)