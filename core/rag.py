import os
from typing import List
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from config.settings import settings

# 初始化嵌入模型
embedding = SentenceTransformerEmbeddings(
    model_name=settings.EMBEDDING_MODEL
)

# 文本切分器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP
)

def load_file_docs(file_path: str):
    """根据后缀自动加载 txt/md/pdf"""
    if file_path.endswith((".txt", ".md")):
        loader = TextLoader(file_path, encoding="utf-8")
    elif file_path.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    else:
        return []
    return loader.load()

def load_knowledge_to_vector_incremental():
    """增量入库：只新增未入库文档，不重复全量向量化"""
    know_dir = settings.RAG_KNOWLEDGE_DIR
    os.makedirs(know_dir, exist_ok=True)
    db_dir = settings.CHROMA_DB_DIR
    os.makedirs(db_dir, exist_ok=True)

    # 遍历知识库文件
    all_docs = []
    for fname in os.listdir(know_dir):
        fp = os.path.join(know_dir, fname)
        if os.path.isfile(fp):
            docs = load_file_docs(fp)
            all_docs.extend(docs)

    if not all_docs:
        print("ℹ️ 暂无知识库文档需要入库")
        return

    splits = text_splitter.split_documents(all_docs)

    # 增量写入Chroma
    Chroma.from_documents(
        documents=splits,
        embedding=embedding,
        persist_directory=db_dir
    )
    print("✅ 知识库增量入库完成")

def query_knowledge(question: str) -> str:
    """检索知识库 + 截断超长上下文"""
    db = Chroma(
        persist_directory=settings.CHROMA_DB_DIR,
        embedding_function=embedding
    )
    res = db.similarity_search(question, k=settings.RAG_TOP_K)
    context = "\n".join([d.page_content.strip() for d in res])
    # 截断上下文，防止超长溢出
    if len(context) > settings.RAG_MAX_CONTEXT_LEN:
        context = context[:settings.RAG_MAX_CONTEXT_LEN] + "\n...（内容已截断）"
    return context