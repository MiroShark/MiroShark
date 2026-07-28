"""Offline coverage for Settings API provider presets."""

from __future__ import annotations

from flask import Flask

from app.api.settings import settings_bp
from app.config import Config


def _make_app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    return app


def test_atlascloud_preset_configures_openai_compatible_text_slots(monkeypatch):
    tracked = {
        "LLM_PROVIDER": "",
        "LLM_BASE_URL": "",
        "LLM_MODEL_NAME": "",
        "LLM_API_KEY": "",
        "SMART_PROVIDER": "",
        "SMART_BASE_URL": "",
        "SMART_MODEL_NAME": "",
        "SMART_API_KEY": "",
        "NER_BASE_URL": "",
        "NER_MODEL_NAME": "",
        "NER_API_KEY": "",
        "WONDERWALL_BASE_URL": "",
        "WONDERWALL_MODEL_NAME": "",
        "WONDERWALL_API_KEY": "",
        "EMBEDDING_PROVIDER": "ollama",
        "EMBEDDING_BASE_URL": "http://localhost:11434",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "EMBEDDING_API_KEY": "embedding-test-key",
        "EMBEDDING_DIMENSIONS": 1024,
        "WEB_SEARCH_MODEL": "previous-search-model",
    }
    for name, value in tracked.items():
        monkeypatch.setattr(Config, name, value)

    with _make_app().test_client() as client:
        response = client.post(
            "/api/settings",
            json={"preset": "atlascloud", "preset_api_key": "atlas-test-key"},
        )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["llm"] == {
        "provider": "openai",
        "base_url": "https://api.atlascloud.ai/v1",
        "model_name": "deepseek-ai/deepseek-v4-pro",
        "api_key_masked": "****-key",
        "has_api_key": True,
    }
    assert data["smart"]["model_name"] == "deepseek-ai/deepseek-v4-pro"
    assert data["ner"]["model_name"] == "qwen/qwen3.5-flash"
    assert data["wonderwall"]["model_name"] == "deepseek-ai/deepseek-v4-flash"
    assert Config.WONDERWALL_BASE_URL == "https://api.atlascloud.ai/v1"
    assert Config.WONDERWALL_API_KEY == "atlas-test-key"
    assert Config.EMBEDDING_PROVIDER == "ollama"
    assert Config.EMBEDDING_BASE_URL == "http://localhost:11434"
    assert Config.EMBEDDING_MODEL == "nomic-embed-text"
    assert Config.EMBEDDING_API_KEY == "embedding-test-key"
    assert Config.EMBEDDING_DIMENSIONS == 1024
    assert Config.WEB_SEARCH_MODEL == ""


def test_settings_snapshot_marks_cloud_presets_as_requiring_keys():
    with _make_app().test_client() as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    presets = {
        preset["id"]: preset
        for preset in response.get_json()["data"]["available_presets"]
    }
    assert presets["atlascloud"]["needs_api_key"] is True
    assert "does not provide embedding models" in presets["atlascloud"]["note"]
    assert presets["cheap"]["needs_api_key"] is True
    assert presets["local"]["needs_api_key"] is False


def test_switching_from_atlascloud_clears_wonderwall_base_url(monkeypatch):
    monkeypatch.setattr(Config, "WONDERWALL_BASE_URL", "")

    with _make_app().test_client() as client:
        assert client.post("/api/settings", json={"preset": "atlascloud"}).status_code == 200
        assert Config.WONDERWALL_BASE_URL == "https://api.atlascloud.ai/v1"

        assert client.post("/api/settings", json={"preset": "cheap"}).status_code == 200
        assert Config.WONDERWALL_BASE_URL == ""

        assert client.post("/api/settings", json={"preset": "atlascloud"}).status_code == 200
        assert client.post("/api/settings", json={"preset": "local"}).status_code == 200
        assert Config.WONDERWALL_BASE_URL == ""
