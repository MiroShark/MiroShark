import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.nano_banana_renderer import (
    NanoBananaConfigError,
    render_infographic_slide,
)


def test_render_infographic_slide_saves_inline_image(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake_png = b"fake-png-bytes"
    response = MagicMock()
    response.ok = True
    response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(fake_png).decode("ascii"),
                            }
                        }
                    ]
                }
            }
        ]
    }

    with patch("app.services.nano_banana_renderer.requests.post", return_value=response) as mock_post:
        result = render_infographic_slide(
            {"image_prompt": "Create an infographic"},
            output_dir=tmp_path,
            filename="slide-01.png",
        )

    assert (tmp_path / "slide-01.png").read_bytes() == fake_png
    assert result["filename"] == "slide-01.png"
    assert result["bytes"] == len(fake_png)
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["contents"][0]["parts"][0]["text"] == "Create an infographic"


def test_render_infographic_slide_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(NanoBananaConfigError):
        render_infographic_slide({"image_prompt": "x"}, output_dir=tmp_path, filename="x.png")
