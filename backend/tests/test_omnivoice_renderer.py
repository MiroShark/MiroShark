import sys
import types

import pytest

from app.services.omnivoice_renderer import OmniVoiceRenderError, render_omnivoice_audio


class FakeClient:
    def __init__(self, space):
        self.space = space

    def predict(self, *args, **kwargs):
        source = kwargs.pop("_source", None)
        assert kwargs["api_name"] == "/_design_fn"
        assert args[0] == "Hello narration"
        # The renderer should request English with Australian accent defaults.
        assert args[1] == "English"
        assert "Australian Accent" in args[13]
        return source, "ok"


def test_render_omnivoice_audio_copies_returned_audio(tmp_path, monkeypatch):
    source = tmp_path / "space-output.wav"
    source.write_bytes(b"fake-wav")

    class BoundFakeClient(FakeClient):
        def predict(self, *args, **kwargs):
            kwargs["_source"] = str(source)
            return super().predict(*args, **kwargs)

    fake_module = types.SimpleNamespace(Client=BoundFakeClient)
    monkeypatch.setitem(sys.modules, "gradio_client", fake_module)

    result = render_omnivoice_audio(
        "Hello narration",
        output_dir=tmp_path / "out",
        filename="narration.wav",
    )

    assert (tmp_path / "out" / "narration.wav").read_bytes() == b"fake-wav"
    assert result["provider"] == "omnivoice_hf_space"
    assert result["source_space"] == "k2-fsa/OmniVoice"
    assert result["bytes"] == len(b"fake-wav")


def test_render_omnivoice_audio_requires_text(tmp_path):
    with pytest.raises(OmniVoiceRenderError, match="text is required"):
        render_omnivoice_audio("   ", output_dir=tmp_path)
