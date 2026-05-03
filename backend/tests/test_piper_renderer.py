from unittest.mock import MagicMock, patch

import pytest

from app.services.piper_renderer import PiperConfigError, PiperRenderError, render_piper_audio


def test_render_piper_audio_writes_local_wav(tmp_path):
    model = tmp_path / "voice.onnx"
    config = tmp_path / "voice.onnx.json"
    model.write_bytes(b"model")
    config.write_text("{}")

    def fake_run(cmd, input, text, capture_output, check, timeout):
        output_file = cmd[cmd.index("-f") + 1]
        with open(output_file, "wb") as fh:
            fh.write(b"RIFFfake")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("app.services.piper_renderer.subprocess.run", side_effect=fake_run) as mock_run:
        result = render_piper_audio(
            "Hello local TTS",
            output_dir=tmp_path / "out",
            filename="clip.wav",
            model_path=model,
        )

    assert result["provider"] == "local_piper"
    assert result["filename"] == "clip.wav"
    assert result["bytes"] == len(b"RIFFfake")
    assert mock_run.call_args.kwargs["input"] == "Hello local TTS"


def test_render_piper_audio_requires_model(tmp_path):
    with pytest.raises(PiperConfigError, match="voice model not found"):
        render_piper_audio("Hello", output_dir=tmp_path, model_path=tmp_path / "missing.onnx")


def test_render_piper_audio_requires_text(tmp_path):
    with pytest.raises(PiperRenderError, match="text is required"):
        render_piper_audio("   ", output_dir=tmp_path)
