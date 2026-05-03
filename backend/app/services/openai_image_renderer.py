"""Render infographic slide prompts with OpenAI GPT Image models."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests


class OpenAIImageConfigError(RuntimeError):
    """Raised when OpenAI image rendering is not configured."""


class OpenAIImageRenderError(RuntimeError):
    """Raised when OpenAI does not return an image."""


DEFAULT_MODEL = "gpt-image-2"
API_URL = "https://api.openai.com/v1/images/generations"
EDIT_API_URL = "https://api.openai.com/v1/images/edits"


def render_openai_infographic_slide(
    slide: dict[str, Any],
    *,
    output_dir: Path,
    filename: str,
    model: str | None = None,
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
    timeout: int = 240,
) -> dict[str, Any]:
    """Render one slide through OpenAI Images API and save it locally."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIImageConfigError("OPENAI_API_KEY is required")

    selected_model = model or os.environ.get("OPENAI_IMAGE_MODEL") or DEFAULT_MODEL
    prompt = slide.get("image_prompt") or slide.get("prompt") or ""
    if not prompt.strip():
        raise OpenAIImageRenderError("slide has no image_prompt")

    size = _size_for(aspect_ratio, selected_model)
    payload: dict[str, Any] = {
        "model": selected_model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
        "output_format": "png",
    }

    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        raise OpenAIImageRenderError(f"OpenAI image API failed: HTTP {response.status_code} {response.text[:500]}")

    data = response.json()
    item = (data.get("data") or [{}])[0]
    b64 = item.get("b64_json")
    if not b64:
        raise OpenAIImageRenderError(f"OpenAI image API returned no b64_json: {str(data)[:500]}")

    raw = base64.b64decode(b64)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_bytes(raw)

    return {
        "filename": filename,
        "mime_type": "image/png",
        "bytes": len(raw),
        "model": selected_model,
        "provider": "openai",
        "aspect_ratio": aspect_ratio,
        "size": size,
        "image_size": image_size,
    }


def render_openai_infographic_slide_edit(
    slide: dict[str, Any],
    *,
    output_dir: Path,
    filename: str,
    reference_image: Path,
    prompt: str,
    model: str | None = None,
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
    timeout: int = 240,
) -> dict[str, Any]:
    """Render one slide through OpenAI image edits using a reference image."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIImageConfigError("OPENAI_API_KEY is required")
    if not reference_image.exists():
        raise OpenAIImageRenderError(f"reference image not found: {reference_image}")

    selected_model = model or os.environ.get("OPENAI_IMAGE_MODEL") or DEFAULT_MODEL
    if not prompt.strip():
        raise OpenAIImageRenderError("strict render prompt is empty")

    size = _size_for(aspect_ratio, selected_model)
    output_dir.mkdir(parents=True, exist_ok=True)
    with reference_image.open("rb") as image_file:
        response = requests.post(
            EDIT_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data={
                "model": selected_model,
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
                "output_format": "png",
            },
            files={"image": ("reference.png", image_file, "image/png")},
            timeout=timeout,
        )
    if not response.ok:
        raise OpenAIImageRenderError(f"OpenAI image edit API failed: HTTP {response.status_code} {response.text[:500]}")

    data = response.json()
    item = (data.get("data") or [{}])[0]
    b64 = item.get("b64_json")
    if not b64:
        raise OpenAIImageRenderError(f"OpenAI image edit API returned no b64_json: {str(data)[:500]}")

    raw = base64.b64decode(b64)
    path = output_dir / filename
    path.write_bytes(raw)

    return {
        "filename": filename,
        "mime_type": "image/png",
        "bytes": len(raw),
        "model": selected_model,
        "provider": "openai-strict-reference-edit",
        "aspect_ratio": aspect_ratio,
        "size": size,
        "image_size": image_size,
        "reference_image": reference_image.name,
    }


def _size_for(aspect_ratio: str, model: str) -> str:
    if aspect_ratio == "9:16":
        return "1024x1536"
    if aspect_ratio == "16:9":
        return "1536x1024"
    return "1024x1024"
