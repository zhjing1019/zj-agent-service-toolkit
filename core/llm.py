from langchain_openai import ChatOpenAI
from config.settings import settings

# DeepSeek 兼容 OpenAI 接口
def create_deepseek_llm():
    return ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        temperature=0.1,
    )

llm = create_deepseek_llm()