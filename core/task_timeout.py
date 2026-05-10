"""墙钟级超时：阻塞型 LangGraph / 工具在独立线程中执行，超时则放弃等待并打告警日志。

说明：超时后调用方不再等待，但子线程内的同步代码可能仍会运行直至自身结束，无法强制中断 Python 线程。
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, Iterator

from config.logger import logger
from config.settings import settings

_SENTINEL = object()


class AgentExecutionTimeoutError(TimeoutError):
    """整图或 SSE 整段（图 + 流式汇总）超过总时限。"""


class ToolExecutionTimeoutError(TimeoutError):
    """单次工具同步调用超过单工具时限。"""


def invoke_langgraph_with_timeout(graph: Any, input_state: Any, config: dict, timeout_sec: float | None) -> Any:
    """对 ``graph.invoke(input_state, config)`` 施加墙钟超时；``timeout_sec <= 0`` 表示不限制。"""
    ts = float(timeout_sec if timeout_sec is not None else settings.AGENT_GRAPH_TIMEOUT_SEC)
    if ts <= 0:
        return graph.invoke(input_state, config)
    tid = (config or {}).get("configurable", {}).get("thread_id", "")
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(graph.invoke, input_state, config)
        try:
            return fut.result(timeout=ts)
        except FuturesTimeout:
            logger.warning(
                "【告警】Agent 图执行超时：limit=%.0fs checkpoint_thread_id=%s",
                ts,
                tid,
            )
            raise AgentExecutionTimeoutError(
                f"【告警】Agent 图执行已超过 {ts:.0f} 秒，已终止等待。"
            ) from None


def run_tool_call_with_timeout(func: Callable[..., Any], args: tuple, timeout_sec: float | None) -> Any:
    """单次工具调用超时；``timeout_sec <= 0`` 表示不限制。"""
    ts = float(timeout_sec if timeout_sec is not None else settings.TOOL_CALL_TIMEOUT_SEC)
    name = getattr(func, "__name__", repr(func))
    if ts <= 0:
        return func(*args)
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(func, *args)
        try:
            return fut.result(timeout=ts)
        except FuturesTimeout:
            logger.warning(
                "【告警】工具调用超时：limit=%.0fs tool=%s",
                ts,
                name,
            )
            raise ToolExecutionTimeoutError(
                f"【告警】工具「{name}」单次执行已超过 {ts:.0f} 秒，已终止等待。"
            ) from None


def _next_chunk(it: Iterator[str]) -> object | str:
    try:
        return next(it)
    except StopIteration:
        return _SENTINEL


async def async_iterate_summary_stream(
    stream_factory: Callable[[], Iterator[str]],
    deadline_monotonic: float | None,
) -> Any:
    """
    将同步生成器 ``stream_factory()`` 转为异步迭代。
    ``deadline_monotonic`` 为 ``None`` 时不限制总时长；否则在每次拉取块时检查剩余时间。
    """
    it = iter(stream_factory())
    if deadline_monotonic is None:
        for piece in it:
            yield piece
        return

    while True:
        left = deadline_monotonic - time.monotonic()
        if left <= 0:
            logger.warning(
                "【告警】SSE 任务总超时：limit=%.0fs",
                settings.AGENT_GRAPH_TIMEOUT_SEC,
            )
            raise AgentExecutionTimeoutError(
                f"【告警】任务总执行时间（图 + 流式汇总）已超过 {settings.AGENT_GRAPH_TIMEOUT_SEC:.0f} 秒，已终止。"
            )
        step = max(0.01, left)
        try:
            val = await asyncio.wait_for(asyncio.to_thread(_next_chunk, it), timeout=step)
        except asyncio.TimeoutError:
            logger.warning(
                "【告警】SSE 流式汇总等待下一块超时：budget=%.0fs",
                settings.AGENT_GRAPH_TIMEOUT_SEC,
            )
            raise AgentExecutionTimeoutError(
                f"【告警】任务总执行时间（图 + 流式汇总）已超过 {settings.AGENT_GRAPH_TIMEOUT_SEC:.0f} 秒，已终止。"
            ) from None
        if val is _SENTINEL:
            return
        yield val  # type: ignore[misc]
