"""Local Piper TTS renderer for offline slide narration clips."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class PiperConfigError(RuntimeError):
    pass


class PiperRenderError(RuntimeError):
    pass


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_model_path() -> Path:
    return _backend_dir() / "models" / "piper" / "en_GB-alan-medium.onnx"


def render_piper_audio(
    text: str,
    *,
    output_dir: Path,
    filename: str = "narration.wav",
    model_path: str | Path | None = None,
    length_scale: float | None = None,
    sentence_silence: float | None = None,
) -> dict[str, Any]:
    """Render text to a WAV file using local Piper.

    Requires a local .onnx voice model plus its matching .onnx.json config.
    """
    clean_text = " ".join(str(text or "").split())
    if not clean_text:
        raise PiperRenderError("text is required")

    model = Path(model_path or os.environ.get("PIPER_VOICE_MODEL") or _default_model_path())
    config = Path(str(model) + ".json")
    if not model.exists():
        raise PiperConfigError(f"Piper voice model not found: {model}")
    if not config.exists():
        raise PiperConfigError(f"Piper voice config not found: {config}")

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / filename
    cmd = [
        sys.executable,
        "-m",
        "piper",
        "-m",
        str(model),
        "-c",
        str(config),
        "-f",
        str(dest),
    ]
    if length_scale is not None:
        cmd.extend(["--length-scale", str(length_scale)])
    if sentence_silence is not None:
        cmd.extend(["--sentence-silence", str(sentence_silence)])

    try:
        completed = subprocess.run(
            cmd,
            input=clean_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except Exception as exc:
        raise PiperRenderError(f"Piper request failed: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise PiperRenderError(f"Piper exited {completed.returncode}: {detail}")
    if not dest.exists() or dest.stat().st_size == 0:
        raise PiperRenderError("Piper produced no audio")

    return {
        "filename": filename,
        "provider": "local_piper",
        "model": model.name,
        "bytes": dest.stat().st_size,
        "status": "Done.",
    }
