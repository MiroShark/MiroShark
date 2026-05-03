import base64
from unittest.mock import MagicMock, patch

import pytest

from app.services.openai_image_renderer import (
    OpenAIImageConfigError,
    render_openai_infographic_slide_edit,
    render_openai_infographic_slide,
)


def test_render_openai_infographic_slide_saves_image(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_png = b"fake-openai-png"
    response = MagicMock()
    response.ok = True
    response.json.return_value = {"data": [{"b64_json": base64.b64encode(fake_png).decode("ascii")}]} 

    with patch("app.services.openai_image_renderer.requests.post", return_value=response) as mock_post:
        result = render_openai_infographic_slide(
            {"image_prompt": "simple infographic"},
            output_dir=tmp_path,
            filename="slide-01.png",
            aspect_ratio="9:16",
        )

    assert (tmp_path / "slide-01.png").read_bytes() == fake_png
    assert result["provider"] == "openai"
    assert result["size"] == "1024x1536"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "gpt-image-2"
    assert payload["prompt"] == "simple infographic"


def test_render_openai_infographic_slide_requires_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIImageConfigError):
        render_openai_infographic_slide({"image_prompt": "x"}, output_dir=tmp_path, filename="x.png")


def test_render_openai_infographic_slide_edit_saves_image(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reference = tmp_path / "reference.png"
    reference.write_bytes(b"fake-reference")
    fake_png = b"fake-openai-edit-png"
    response = MagicMock()
    response.ok = True
    response.json.return_value = {"data": [{"b64_json": base64.b64encode(fake_png).decode("ascii")}]}

    with patch("app.services.openai_image_renderer.requests.post", return_value=response) as mock_post:
        result = render_openai_infographic_slide_edit(
            {"title": "x"},
            output_dir=tmp_path,
            filename="strict-slide-01.png",
            reference_image=reference,
            prompt="strict prompt",
            aspect_ratio="9:16",
        )

    assert (tmp_path / "strict-slide-01.png").read_bytes() == fake_png
    assert result["provider"] == "openai-strict-reference-edit"
    assert result["reference_image"] == "reference.png"
    assert result["size"] == "1024x1536"
    data = mock_post.call_args.kwargs["data"]
    assert data["prompt"] == "strict prompt"
    assert "files" in mock_post.call_args.kwargs
