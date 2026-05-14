"""LLM / 工具调用的可重试异常判断与带降级的大模型调用。"""
from __future__ import annotations

import time
from typing import Any, Callable, Iterator

import httpx
from langchain_core.messages import AIMessage

from config.settings import settings

try:
    from openai import APIError, APITimeoutError, RateLimitError
except ImportError:  # pragma: no cover
    APIError = type("APIError", (Exception,), {})
    RateLimitError = type("RateLimitError", (Exception,), {})
    APITimeoutError = type("APITimeoutError", (Exception,), {})


def is_degraded_reply(text: str | None) -> bool:
    p = (settings.LLM_FAILURE_DEGRADE_PREFIX or "").strip()
    if not p or not text:
        return False
    return text.strip().startswith(p)


def is_retryable_llm_error(exc: BaseException) -> bool:
    if isinstance(exc, (APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIError):
        code = getattr(exc, "status_code", None)
        if code is not None and code in (400, 401, 403, 404):
            return False
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (408, 429, 500, 502, 503, 504)
    if isinstance(exc, (TimeoutError, ConnectionError, BrokenPipeError)):
        return True
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return True
    if "429" in msg or "rate limit" in msg or "quota" in msg or "额度" in str(exc):
        return True
    if "connection" in msg or "network" in msg or "remote" in msg:
        return True
    return False


def is_retryable_tool_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, BrokenPipeError, OSError)):
        return True
    if isinstance(exc, httpx.HTTPError):
        return True
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return True
    if "connection" in msg or "network" in msg:
        return True
    if "除零" in str(exc) or "division" in msg:
        return False
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return False
    return False


def _backoff_sleep(attempt_index: int) -> None:
    base = max(0.05, float(settings.LLM_RETRY_BACKOFF_SEC))
    time.sleep(base * (attempt_index + 1))


def _get_fallback_model(get_fallback: Callable[[], Any] | None) -> Any | None:
    if get_fallback is None:
        return None
    try:
        return get_fallback()
    except Exception:
        return None


def aimessage_to_text(msg: Any) -> str:
    """将 invoke 返回的 AIMessage / 兼容对象转为纯文本，供业务侧 strip / JSON 解析。"""
    if msg is None:
        return ""
    if isinstance(msg, str):
        return msg
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text") or ""
                if t:
                    parts.append(t)
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


def invoke_llm_resilient(
    primary: Any,
    prompt: str,
    *,
    get_fallback: Callable[[], Any] | None = None,
) -> AIMessage:
    """对 Chat 模型执行 invoke：分级重试 → 备用模型 → 人工接管文案。"""
    n = max(1, int(settings.LLM_RETRY_MAX))

    def _try_model(model: Any, rounds: int) -> AIMessage | None:
        for attempt in range(rounds):
            try:
                return model.invoke(prompt)
            except Exception as e:
                if attempt + 1 < rounds and is_retryable_llm_error(e):
                    _backoff_sleep(attempt)
                    continue
                break
        return None

    out = _try_model(primary, n)
    if out is not None:
        return out

    fb = _get_fallback_model(get_fallback)
    if fb is not None and fb is not primary:
        fb_rounds = max(1, min(2, n))
        out = _try_model(fb, fb_rounds)
        if out is not None:
            return out

    return AIMessage(content=settings.LLM_FAILURE_HANDOFF_MESSAGE)


def _chunk_text(chunk: Any) -> str:
    text = getattr(chunk, "content", None)
    if isinstance(text, str) and text:
        return text
    if isinstance(text, list):
        parts: list[str] = []
        for block in text:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text") or ""
                if t:
                    parts.append(t)
        return "".join(parts)
    return ""


def stream_llm_resilient(
    primary: Any,
    prompt: str,
    *,
    get_fallback: Callable[[], Any] | None = None,
) -> Iterator[str]:
    """流式输出：重试与 invoke 一致；彻底失败时产出一条降级提示。"""
    n = max(1, int(settings.LLM_RETRY_MAX))

    for attempt in range(n):
        try:
            for chunk in primary.stream(prompt):
                t = _chunk_text(chunk)
                if t:
                    yield t
            return
        except Exception as e:
            if attempt + 1 < n and is_retryable_llm_error(e):
                _backoff_sleep(attempt)
                continue
            break

    fb = _get_fallback_model(get_fallback)
    if fb is not None and fb is not primary:
        fb_rounds = max(1, min(2, n))
        for attempt in range(fb_rounds):
            try:
                for chunk in fb.stream(prompt):
                    t = _chunk_text(chunk)
                    if t:
                        yield t
                return
            except Exception as e:
                if attempt + 1 < fb_rounds and is_retryable_llm_error(e):
                    _backoff_sleep(attempt)
                    continue
                break

    yield settings.LLM_FAILURE_HANDOFF_MESSAGE
