"""Render infographic slide prompts with Google's Nano Banana / Gemini Image API."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests


class NanoBananaConfigError(RuntimeError):
    """Raised when image rendering is not configured."""


class NanoBananaRenderError(RuntimeError):
    """Raised when the image provider does not return an image."""


DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def render_infographic_slide(
    slide: dict[str, Any],
    *,
    output_dir: Path,
    filename: str,
    model: str | None = None,
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
    timeout: int = 180,
) -> dict[str, Any]:
    """Render one slide and persist it to output_dir/filename.

    Returns small metadata suitable for saving in a session. The caller can expose
    the saved file through an authenticated/local API route rather than storing
    large base64 blobs in the session JSON.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise NanoBananaConfigError("GEMINI_API_KEY or GOOGLE_API_KEY is required")

    selected_model = model or os.environ.get("GEMINI_IMAGE_MODEL") or DEFAULT_MODEL
    prompt = slide.get("image_prompt") or slide.get("prompt") or ""
    if not prompt.strip():
        raise NanoBananaRenderError("slide has no image_prompt")

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }
    # Gemini 2.5 Flash Image supports aspect ratio but not all newer image-size
    # controls. Keep the payload conservative for that model.
    if "2.5" not in selected_model and image_size:
        payload["generationConfig"]["imageConfig"]["imageSize"] = image_size

    response = requests.post(
        API_URL_TEMPLATE.format(model=selected_model),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        raise NanoBananaRenderError(f"Gemini image API failed: HTTP {response.status_code} {response.text[:500]}")

    data = response.json()
    inline = _first_inline_image(data)
    if not inline:
        text = _first_text(data)
        detail = f" Provider text: {text[:300]}" if text else ""
        raise NanoBananaRenderError(f"Gemini image API returned no image.{detail}")

    mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
    raw = base64.b64decode(inline["data"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_bytes(raw)

    return {
        "filename": filename,
        "mime_type": mime_type,
        "bytes": len(raw),
        "model": selected_model,
        "aspect_ratio": aspect_ratio,
        "image_size": image_size if "2.5" not in selected_model else None,
    }


def _first_inline_image(data: dict[str, Any]) -> dict[str, Any] | None:
    for candidate in data.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return inline
    for part in data.get("parts", []) or []:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return inline
    return None


def _first_text(data: dict[str, Any]) -> str:
    texts: list[str] = []
    for candidate in data.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            if part.get("text"):
                texts.append(part["text"])
    return "\n".join(texts)
