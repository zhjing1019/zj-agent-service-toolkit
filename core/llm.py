from langchain_openai import ChatOpenAI
from config.settings import settings

def get_llm_factory(provider: str | None = None):
    """工厂模式：动态获取 DeepSeek / OpenAI LLM"""
    if not provider:
        provider = settings.DEFAULT_LLM_PROVIDER

    if provider.lower() == "deepseek":
        return ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            temperature=0.1,
        )
    elif provider.lower() == "openai":
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.1,
        )
    else:
        raise ValueError("不支持的模型提供商：只支持 deepseek / openai")

# 默认全局 LLM（运行时可由 set_primary_llm_provider 切换）
llm = get_llm_factory()


def set_primary_llm_provider(provider: str) -> None:
    global llm
    llm = get_llm_factory(provider)


def _fallback_llm():
    p = (settings.LLM_FALLBACK_PROVIDER or "").strip().lower()
    if not p:
        return None
    cur = (settings.DEFAULT_LLM_PROVIDER or "").strip().lower()
    if p == cur:
        return None
    return get_llm_factory(p)


def resilient_invoke(prompt: str):
    from core.resilience import invoke_llm_resilient

    return invoke_llm_resilient(llm, prompt, get_fallback=_fallback_llm)


def resilient_stream(prompt: str):
    from core.resilience import stream_llm_resilient

    yield from stream_llm_resilient(llm, prompt, get_fallback=_fallback_llm)