"""Client helper for the k2-fsa/OmniVoice Hugging Face Space."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class OmniVoiceRenderError(RuntimeError):
    pass


def render_omnivoice_audio(
    text: str,
    *,
    output_dir: Path,
    filename: str = "narration.wav",
    language: str = "English",
    duration: float = 0,
    gender: str = "Auto",
    age: str = "Auto",
    pitch: str = "Auto",
    style: str = "Auto",
    accent: str = "Australian Accent / 澳大利亚口音",
    timeout_note: str = "Hugging Face ZeroGPU can queue or sleep; retry if the Space is cold.",
) -> dict[str, Any]:
    try:
        from gradio_client import Client
    except Exception as exc:  # pragma: no cover - environment guard
        raise OmniVoiceRenderError(f"gradio_client is not installed: {exc}") from exc

    if not text.strip():
        raise OmniVoiceRenderError("text is required")

    client = Client("k2-fsa/OmniVoice")
    try:
        audio_path, status = client.predict(
            text,
            language,
            32,
            2.0,
            True,
            1.0,
            duration,
            True,
            True,
            gender,
            age,
            pitch,
            style,
            accent,
            "Auto",
            api_name="/_design_fn",
        )
    except Exception as exc:
        raise OmniVoiceRenderError(f"OmniVoice request failed ({timeout_note}): {exc}") from exc

    if not audio_path:
        raise OmniVoiceRenderError(f"OmniVoice returned no audio: {status}")

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / filename
    shutil.copyfile(audio_path, dest)
    return {
        "filename": filename,
        "provider": "omnivoice_hf_space",
        "source_space": "k2-fsa/OmniVoice",
        "bytes": dest.stat().st_size,
        "status": status,
    }
