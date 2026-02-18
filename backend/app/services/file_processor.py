"""Multimodal file processor: extract text from various file formats.

Supports: plain text, markdown, PDF (via pymupdf if available),
images (via LLM vision or pytesseract if available).
Falls back gracefully when optional dependencies are missing.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)


async def extract_text(file_path: str | Path, content_type: str | None = None) -> str:
    """Extract text content from a file. Returns the extracted text."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if content_type is None:
        content_type, _ = mimetypes.guess_type(str(path))
        content_type = content_type or "application/octet-stream"

    if content_type in ("text/plain", "text/markdown", "text/csv", "text/html"):
        return _extract_text_file(path)
    elif content_type == "application/pdf":
        return await _extract_pdf(path)
    elif content_type.startswith("image/"):
        return await _extract_image(path)
    elif content_type.startswith("audio/"):
        return f"[音频文件: {path.name}] (音频转文字功能待接入Whisper API)"
    elif content_type.startswith("video/"):
        return f"[视频文件: {path.name}] (视频处理功能待接入)"
    else:
        return f"[文件: {path.name}] (不支持的格式: {content_type})"


def _extract_text_file(path: Path) -> str:
    """Read text-based files."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="gbk")
        except Exception:
            return path.read_text(encoding="utf-8", errors="replace")


async def _extract_pdf(path: Path) -> str:
    """Extract text from PDF. Tries pymupdf (fitz), falls back to basic read."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        text = "\n\n".join(pages).strip()
        if text:
            return text
        return f"[PDF文件: {path.name}] (无法提取文本，可能是扫描件)"
    except ImportError:
        logger.warning("pymupdf not installed, PDF text extraction unavailable. Install with: pip install pymupdf")
        return f"[PDF文件: {path.name}] (需要安装pymupdf: pip install pymupdf)"


async def _extract_image(path: Path) -> str:
    """Extract text from image via OCR. Tries LLM vision first, then pytesseract."""
    try:
        return await _ocr_via_llm(path)
    except Exception as e:
        logger.debug("LLM vision OCR skipped: %s", e)

    try:
        import pytesseract
        from PIL import Image
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        if text.strip():
            return text.strip()
    except ImportError:
        logger.debug("pytesseract not installed")
    except Exception as e:
        logger.warning("pytesseract OCR failed: %s", e)

    return f"[图片: {path.name}] (OCR未配置，请安装pytesseract或使用支持vision的LLM)"


async def _ocr_via_llm(path: Path) -> str:
    """Use LLM multimodal API to describe/OCR an image."""
    import base64
    from app.services.llm_service import chat_completion
    from app.config import get_settings

    settings = get_settings()
    data = base64.b64encode(path.read_bytes()).decode("utf-8")

    suffix = path.suffix.lower().lstrip(".")
    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    mime = f"image/{mime_map.get(suffix, suffix)}"

    messages = [
        {"role": "system", "content": "你是OCR助手。请识别图片中的所有文字，保持原始排版。如果没有文字，请描述图片内容。"},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            {"type": "text", "text": "请识别并输出图片中的所有文字内容。"},
        ]},
    ]

    return await chat_completion(messages, temperature=0.1, max_tokens=4096)


def detect_content_type(filename: str) -> str:
    """Detect content type category from filename."""
    ct, _ = mimetypes.guess_type(filename)
    ct = ct or "application/octet-stream"

    if ct.startswith("text/") or ct in ("application/json", "application/xml"):
        return "text"
    elif ct == "application/pdf":
        return "pdf"
    elif ct.startswith("image/"):
        return "image"
    elif ct.startswith("audio/"):
        return "audio"
    elif ct.startswith("video/"):
        return "video"
    else:
        return "file"
