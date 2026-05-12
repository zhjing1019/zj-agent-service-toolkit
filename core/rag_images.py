"""知识库图片：CLIP 向量索引 + 检索；索引时可选 BLIP 描述或侧写 .caption.txt。"""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

from config.settings import settings


def _pil_image_mod():
    """延迟导入 Pillow，避免未安装时阻塞整个应用导入。"""
    try:
        from PIL import Image as PILImage

        return PILImage
    except ImportError as e:
        raise ImportError(
            "图片 RAG 需要 Pillow，请安装：pip install Pillow"
        ) from e

MANIFEST = "image_rag_manifest.json"
EMBEDDINGS = "image_rag_embeddings.npy"

_clip_model: Any = None
_blip_processor: Any = None
_blip_model: Any = None
_index_cache: tuple[float, list[dict[str, Any]], np.ndarray] | None = None


def _apply_hf_hub_env():
    if settings.HF_ENDPOINT:
        os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(settings.HF_HUB_DOWNLOAD_TIMEOUT)
    if settings.HUGGINGFACE_HUB_CACHE:
        os.environ["HUGGINGFACE_HUB_CACHE"] = settings.HUGGINGFACE_HUB_CACHE


def _index_dir() -> str:
    d = os.path.abspath(settings.IMAGE_RAG_INDEX_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def _manifest_path() -> str:
    return os.path.join(_index_dir(), MANIFEST)


def _emb_path() -> str:
    return os.path.join(_index_dir(), EMBEDDINGS)


def clear_image_rag_index_files() -> None:
    for p in (_manifest_path(), _emb_path()):
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    global _index_cache
    _index_cache = None


def _iter_image_files(know_dir: str) -> list[str]:
    exts = frozenset(
        x.strip().lower()
        for x in settings.IMAGE_RAG_EXTENSIONS.split(",")
        if x.strip()
    )
    out: list[str] = []
    if not os.path.isdir(know_dir):
        return out
    for root, _dirs, files in os.walk(know_dir):
        for fname in files:
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in exts:
                continue
            out.append(os.path.join(root, fname))
    return sorted(out)


def _get_clip_model():
    global _clip_model
    if _clip_model is not None:
        return _clip_model
    _apply_hf_hub_env()
    from sentence_transformers import SentenceTransformer

    _clip_model = SentenceTransformer(settings.IMAGE_RAG_CLIP_MODEL)
    return _clip_model


def _read_sidecar_caption(abs_path: str) -> str:
    side = abs_path + ".caption.txt"
    if not os.path.isfile(side):
        return ""
    try:
        with open(side, encoding="utf-8") as f:
            return (f.read() or "").strip()
    except OSError:
        return ""


def _caption_blip(abs_path: str) -> str:
    if not settings.IMAGE_RAG_BLIP_CAPTION:
        return ""
    global _blip_processor, _blip_model
    try:
        import torch
        from transformers import BlipForConditionalGeneration, BlipProcessor
    except ImportError:
        return ""

    if _blip_processor is None:
        name = settings.IMAGE_RAG_BLIP_MODEL
        _blip_processor = BlipProcessor.from_pretrained(name)
        _blip_model = BlipForConditionalGeneration.from_pretrained(name).eval()

    try:
        PILImage = _pil_image_mod()
        img = PILImage.open(abs_path).convert("RGB")
    except OSError:
        return ""
    except ImportError:
        return ""

    try:
        inputs = _blip_processor(img, return_tensors="pt")
        with torch.no_grad():
            out = _blip_model.generate(**inputs, max_length=settings.IMAGE_RAG_BLIP_MAX_LENGTH)
        text = _blip_processor.decode(out[0], skip_special_tokens=True)
        return (text or "").strip()
    except Exception:
        return ""


def build_image_rag_index(rebuild: bool = False) -> None:
    """扫描 RAG_KNOWLEDGE_DIR 下图片，写 manifest + 归一化 CLIP 向量矩阵。"""
    global _index_cache
    _index_cache = None
    if rebuild:
        clear_image_rag_index_files()

    know_dir = os.path.abspath(settings.RAG_KNOWLEDGE_DIR)
    paths = _iter_image_files(know_dir)
    if not paths:
        with open(_manifest_path(), "w", encoding="utf-8") as f:
            json.dump([], f)
        np.save(_emb_path(), np.zeros((0, 0), dtype=np.float32))
        print(f"ℹ️ 图片 RAG：在 {know_dir} 下未发现图片（扩展名 {settings.IMAGE_RAG_EXTENSIONS}）")
        return

    try:
        PILImage = _pil_image_mod()
    except ImportError as e:
        print(f"⚠️ 图片 RAG 跳过索引：{e}")
        return

    model = _get_clip_model()
    manifest: list[dict[str, Any]] = []
    embs_list: list[np.ndarray] = []

    for i, abs_p in enumerate(paths):
        try:
            img = PILImage.open(abs_p).convert("RGB")
        except Exception as e:
            print(f"⚠️ 跳过图片（无法打开）: {abs_p}\n   {e}")
            continue
        try:
            v = model.encode(img, convert_to_numpy=True, show_progress_bar=False)
        except Exception as e:
            print(f"⚠️ 跳过图片（CLIP 编码失败）: {abs_p}\n   {e}")
            continue
        v = np.asarray(v, dtype=np.float32).reshape(-1)
        nrm = float(np.linalg.norm(v) + 1e-9)
        v = v / nrm

        rel = os.path.relpath(abs_p, know_dir)
        cap = _read_sidecar_caption(abs_p)
        if not cap:
            cap = _caption_blip(abs_p)

        manifest.append({"rel": rel.replace(os.sep, "/"), "caption": cap})
        embs_list.append(v)

        if (i + 1) % 20 == 0:
            print(f"   …已索引图片 {i + 1}/{len(paths)}")

    if not embs_list:
        with open(_manifest_path(), "w", encoding="utf-8") as f:
            json.dump([], f)
        np.save(_emb_path(), np.zeros((0, 0), dtype=np.float32))
        print("ℹ️ 图片 RAG：无有效图片向量可写入")
        return

    mat = np.stack(embs_list, axis=0)
    with open(_manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=0)
    np.save(_emb_path(), mat)
    _index_cache = (os.path.getmtime(_emb_path()), manifest, mat)
    print(
        f"✅ 图片 RAG 索引完成：{len(manifest)} 张，CLIP={settings.IMAGE_RAG_CLIP_MODEL}"
        + ("，已尝试 BLIP 描述" if settings.IMAGE_RAG_BLIP_CAPTION else "")
    )


def _load_index() -> tuple[list[dict[str, Any]], np.ndarray] | tuple[None, None]:
    global _index_cache
    mp, ep = _manifest_path(), _emb_path()
    if not (os.path.isfile(mp) and os.path.isfile(ep)):
        return None, None
    try:
        mtime = os.path.getmtime(ep)
    except OSError:
        return None, None
    if _index_cache is not None and _index_cache[0] == mtime:
        return _index_cache[1], _index_cache[2]

    with open(mp, encoding="utf-8") as f:
        manifest = json.load(f)
    mat = np.load(ep)
    if not isinstance(manifest, list):
        return None, None
    if mat.ndim != 2 or mat.shape[0] != len(manifest):
        return None, None
    _index_cache = (mtime, manifest, mat)
    return manifest, mat


def encode_user_image_clip_vectors(abs_paths: list[str]) -> list[np.ndarray]:
    """对用户上传图片做 CLIP 编码并归一化；失败项跳过。"""
    if not abs_paths:
        return []
    try:
        PILImage = _pil_image_mod()
    except ImportError:
        return []
    model = _get_clip_model()
    vecs: list[np.ndarray] = []
    for p in abs_paths:
        if not os.path.isfile(p):
            continue
        try:
            img = PILImage.open(p).convert("RGB")
            v = model.encode(img, convert_to_numpy=True, show_progress_bar=False)
        except Exception:
            continue
        v = np.asarray(v, dtype=np.float32).reshape(-1)
        v = v / (float(np.linalg.norm(v)) + 1e-9)
        vecs.append(v)
    return vecs


def _combined_clip_query_embedding(
    text_query: str, user_vecs: list[np.ndarray] | None
) -> np.ndarray | None:
    """文本 + 用户多图均值向量按权重融合，再归一化。"""
    t = (text_query or "").strip()
    has_u = bool(user_vecs)
    if not t and not has_u:
        return None
    model = _get_clip_model()
    tw = float(settings.IMAGE_RAG_TEXT_WEIGHT)
    uw = float(settings.IMAGE_RAG_USER_IMAGE_WEIGHT)
    if has_u:
        u = np.mean(np.stack(user_vecs, axis=0), axis=0)
        u = u / (float(np.linalg.norm(u)) + 1e-9)
        if not t:
            return u
        t_emb = model.encode(
            [t], convert_to_numpy=True, show_progress_bar=False
        )[0]
        t_emb = np.asarray(t_emb, dtype=np.float32).reshape(-1)
        t_emb = t_emb / (float(np.linalg.norm(t_emb)) + 1e-9)
        s = tw + uw
        q = (tw / s) * t_emb + (uw / s) * u
        return q / (float(np.linalg.norm(q)) + 1e-9)
    try:
        q = model.encode(
            [t], convert_to_numpy=True, show_progress_bar=False
        )[0]
    except Exception:
        return None
    q = np.asarray(q, dtype=np.float32).reshape(-1)
    return q / (float(np.linalg.norm(q)) + 1e-9)


def retrieve_image_rag_block_and_refs(
    text_query: str,
    user_image_abs_paths: list[str] | None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    CLIP 检索知识库图片；若提供用户上传图路径，与 text_query 向量融合后再检索。
    返回 (RAG 文本块, [{rel, score, caption}, ...])。
    """
    refs: list[dict[str, Any]] = []
    if not settings.IMAGE_RAG_ENABLE:
        return "", refs
    tq = (text_query or "").strip()
    paths = user_image_abs_paths or []
    if not tq and not paths:
        return "", refs

    manifest, mat = _load_index()
    if not manifest or mat is None or mat.shape[0] == 0:
        return "", refs

    user_vecs = encode_user_image_clip_vectors(paths) if paths else []
    u_for_combine: list[np.ndarray] | None = user_vecs if user_vecs else None
    q = _combined_clip_query_embedding(text_query, u_for_combine)
    if q is None:
        return "", refs

    sims = mat @ q
    k = max(1, int(settings.IMAGE_RAG_TOP_K))
    k = min(k, sims.shape[0])
    top_idx = np.argsort(-sims)[:k]

    know_dir = os.path.abspath(settings.RAG_KNOWLEDGE_DIR)
    lines: list[str] = []
    for rank, idx in enumerate(top_idx, start=1):
        row = manifest[int(idx)]
        rel = row.get("rel") or ""
        cap = (row.get("caption") or "").strip()
        score = float(sims[int(idx)])
        abs_p = os.path.normpath(os.path.join(know_dir, rel.replace("/", os.sep)))
        cap_line = (
            f"描述：{cap}"
            if cap
            else "描述：（无，可依赖文件名与用户问题推断；或索引时安装 transformers 并开启 BLIP，或添加「图片路径.caption.txt」侧写）"
        )
        lines.append(
            f"{rank}. 相对路径：`{rel}`\n   {cap_line}\n   CLIP相关度：{score:.3f}\n   本地绝对路径：{abs_p}"
        )
        refs.append({"rel": rel, "score": score, "caption": cap})

    body = "\n\n".join(lines)
    max_c = max(200, int(settings.IMAGE_RAG_MAX_CONTEXT_CHARS))
    if len(body) > max_c:
        body = body[:max_c] + "\n...（图片检索块已截断）"

    note = ""
    if user_vecs:
        note = "（已融合用户本轮上传图片的 CLIP 语义。）\n"
    block = (
        "【多模态-知识库图片检索】以下为 CLIP 图文向量相似度命中的图片（按相关度排序）。\n"
        + note
        + "回答时请结合「文本知识库片段」与下列图片描述/路径；若描述为空勿编造画面细节。\n\n"
        + body
    )
    return block, refs


def retrieve_image_rag_context(query: str) -> str:
    """仅用文本问句检索知识库图片（兼容旧调用）。"""
    block, _ = retrieve_image_rag_block_and_refs(query, None)
    return block
