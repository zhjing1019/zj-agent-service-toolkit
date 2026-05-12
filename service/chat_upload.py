"""用户聊天附图的落盘与路径解析（供 CLIP 与用户预览）。"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from config.settings import settings

# 仅允许 32hex + 常见后缀，防止路径穿越
_CHAT_IMAGE_ID_RE = re.compile(
    r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp|gif)$", re.IGNORECASE
)
_ALLOWED_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def chat_upload_dir() -> Path:
    d = Path(settings.CHAT_UPLOAD_DIR).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_chat_upload(content: bytes, original_filename: str | None) -> str:
    """写入图片，返回 image_id（文件名，含扩展名）。"""
    if len(content) > int(settings.CHAT_UPLOAD_MAX_BYTES):
        raise ValueError(
            f"图片过大，最大 {settings.CHAT_UPLOAD_MAX_BYTES} 字节"
        )
    ext = Path(original_filename or "").suffix.lower() or ".jpg"
    if ext not in _ALLOWED_EXT:
        raise ValueError(f"不支持的图片扩展名：{ext}")
    uid = uuid.uuid4().hex
    name = f"{uid}{ext}"
    path = chat_upload_dir() / name
    path.write_bytes(content)
    return name


def resolve_upload_image_paths(image_ids: list[str]) -> list[str]:
    """将 image_id 列表解析为存在的绝对路径（最多 CHAT_MAX_IMAGES_PER_MESSAGE 条）。"""
    base = chat_upload_dir()
    out: list[str] = []
    lim = max(1, int(settings.CHAT_MAX_IMAGES_PER_MESSAGE))
    for raw in (image_ids or [])[:lim]:
        rid = (raw or "").strip().lower()
        if not _CHAT_IMAGE_ID_RE.match(rid):
            continue
        p = (base / rid).resolve()
        if not str(p).startswith(str(base)):
            continue
        if p.is_file():
            out.append(str(p))
    return out


def path_for_uploaded_image(image_id: str) -> Path | None:
    """校验 image_id 并返回已存在文件的绝对路径。"""
    rid = (image_id or "").strip().lower()
    if not _CHAT_IMAGE_ID_RE.match(rid):
        return None
    base = chat_upload_dir()
    p = (base / rid).resolve()
    if not str(p).startswith(str(base)):
        return None
    return p if p.is_file() else None
