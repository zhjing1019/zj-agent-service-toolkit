import os
from langchain_community.document_loaders import TextLoader
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
    chunk_size=512,
    chunk_overlap=50
)

# 加载文档入库
def load_knowledge_to_vector():
    docs = []
    know_dir = settings.RAG_KNOWLEDGE_DIR
    if not os.path.exists(know_dir):
        return

    for fname in os.listdir(know_dir):
        if fname.endswith((".txt",".md")):
            loader = TextLoader(os.path.join(know_dir, fname), encoding="utf-8")
            docs.extend(loader.load())

    if not docs:
        return

    splits = text_splitter.split_documents(docs)
    Chroma.from_documents(
        documents=splits,
        embedding=embedding,
        persist_directory=settings.CHROMA_DB_DIR
    )

# 检索知识库
def query_knowledge(question: str, top_k=3) -> str:
    db = Chroma(
        persist_directory=settings.CHROMA_DB_DIR,
        embedding_function=embedding
    )
    res = db.similarity_search(question, k=top_k)
    context = "\n".join([d.page_content for d in res])
    return context