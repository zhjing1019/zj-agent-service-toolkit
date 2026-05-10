"""Agent 模板：内置条目 + JSON 文件持久化（管理员可写）。"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from config.settings import settings
from security.rbac import KNOWN_AGENT_IDS

_lock = threading.Lock()

_BUILTIN: list[dict[str, Any]] = [
    {
        "id": "default",
        "name": "LangGraph 多 Agent",
        "description": "安全校验 → 规划 → 工具/RAG/闲聊 → 汇总（默认）",
        "agent_id": "default",
        "builtin": True,
    },
    {
        "id": "base_tool",
        "name": "基础工具 Agent",
        "description": "计算/文件/时间等注册工具（/api/agent/run）",
        "agent_id": "base_tool",
        "builtin": True,
    },
]


def _path() -> str:
    return os.path.abspath(settings.AGENT_TEMPLATES_FILE)


def _ensure_parent() -> None:
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.isfile(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"templates": []}, f, ensure_ascii=False, indent=2)


def _read_custom() -> list[dict[str, Any]]:
    _ensure_parent()
    with open(_path(), encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("templates") or [])


def _write_custom(rows: list[dict[str, Any]]) -> None:
    _ensure_parent()
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump({"templates": rows}, f, ensure_ascii=False, indent=2)


def list_templates() -> list[dict[str, Any]]:
    with _lock:
        custom = _read_custom()
    return list(_BUILTIN) + custom


def create_template(item: dict[str, Any]) -> dict[str, Any]:
    tid = (item.get("id") or "").strip()
    if not tid:
        raise ValueError("id 不能为空")
    if any(b["id"] == tid for b in _BUILTIN):
        raise ValueError("与内置模板 id 冲突")
    row = {
        "id": tid,
        "name": (item.get("name") or tid).strip(),
        "description": (item.get("description") or "").strip(),
        "agent_id": (item.get("agent_id") or "default").strip(),
        "builtin": False,
    }
    if row["agent_id"] not in KNOWN_AGENT_IDS:
        raise ValueError(f"agent_id 必须是 {sorted(KNOWN_AGENT_IDS)} 之一")
    with _lock:
        rows = _read_custom()
        if any(r.get("id") == tid for r in rows):
            raise ValueError("id 已存在")
        rows.append(row)
        _write_custom(rows)
    return row


def delete_template(template_id: str) -> bool:
    tid = template_id.strip()
    if any(b["id"] == tid for b in _BUILTIN):
        raise ValueError("不能删除内置模板")
    with _lock:
        rows = _read_custom()
        new_rows = [r for r in rows if r.get("id") != tid]
        if len(new_rows) == len(rows):
            return False
        _write_custom(new_rows)
    return True
