"""Unit tests for fetch_url_text — Firecrawl primary path + LLM fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.config import Config
from app.utils.url_fetcher import fetch_url_text


_MARKDOWN = "# Heading\n\n" + "Lorem ipsum dolor sit amet. " * 10


def _firecrawl_response(markdown=_MARKDOWN, title="Example Page", success=True):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "success": success,
        "data": {"markdown": markdown, "metadata": {"title": title}},
        **({} if success else {"error": "scrape failed"}),
    }
    return resp


@pytest.fixture
def firecrawl_configured(monkeypatch):
    monkeypatch.setattr(Config, "FIRECRAWL_BASE_URL", "https://fc.example.org")
    monkeypatch.setattr(Config, "FIRECRAWL_API_KEY", "secret-key")


def test_invalid_scheme_rejected():
    with pytest.raises(ValueError):
        fetch_url_text("ftp://example.com/file")


def test_private_address_rejected():
    with pytest.raises(ValueError):
        fetch_url_text("http://127.0.0.1/admin")


@patch("app.utils.url_fetcher.requests.post")
def test_firecrawl_success(mock_post, firecrawl_configured):
    mock_post.return_value = _firecrawl_response()

    result = fetch_url_text("https://example.com/article")

    args, kwargs = mock_post.call_args
    assert args[0] == "https://fc.example.org/v1/scrape"
    assert kwargs["json"]["url"] == "https://example.com/article"
    assert kwargs["json"]["formats"] == ["markdown"]
    assert kwargs["headers"]["Authorization"] == "Bearer secret-key"

    assert result["title"] == "Example Page"
    assert result["text"].startswith("# Heading")
    assert result["char_count"] == len(result["text"])
    assert result["url"] == "https://example.com/article"


@patch("app.utils.url_fetcher.create_llm_client")
@patch("app.utils.url_fetcher.requests.post")
def test_firecrawl_failure_falls_back_to_llm(mock_post, mock_create, firecrawl_configured, monkeypatch):
    monkeypatch.setattr(Config, "WEB_SEARCH_MODEL", "some/model:online")
    mock_post.side_effect = requests.exceptions.ConnectionError("refused")
    llm = MagicMock()
    llm.chat.return_value = (
        '{"title": "LLM Title", "text": "' + "fallback body text " * 10 + '"}'
    )
    mock_create.return_value = llm

    result = fetch_url_text("https://example.com/article")

    assert result["title"] == "LLM Title"
    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["model"] == "some/model:online"


@patch("app.utils.url_fetcher.create_llm_client")
@patch("app.utils.url_fetcher.requests.post")
def test_firecrawl_short_text_falls_back_to_llm(mock_post, mock_create, firecrawl_configured, monkeypatch):
    monkeypatch.setattr(Config, "WEB_SEARCH_MODEL", "some/model:online")
    mock_post.return_value = _firecrawl_response(markdown="too short")
    llm = MagicMock()
    llm.chat.return_value = (
        '{"title": "LLM Title", "text": "' + "fallback body text " * 10 + '"}'
    )
    mock_create.return_value = llm

    result = fetch_url_text("https://example.com/article")
    assert result["title"] == "LLM Title"


@patch("app.utils.url_fetcher.create_llm_client")
def test_llm_only_path_when_firecrawl_unset(mock_create, monkeypatch):
    monkeypatch.setattr(Config, "FIRECRAWL_BASE_URL", "")
    monkeypatch.setattr(Config, "WEB_SEARCH_MODEL", "some/model:online")
    llm = MagicMock()
    llm.chat.return_value = (
        '{"title": "LLM Title", "text": "' + "body text " * 20 + '"}'
    )
    mock_create.return_value = llm

    result = fetch_url_text("https://example.com/article")
    assert result["title"] == "LLM Title"


@patch("app.utils.url_fetcher.requests.post")
def test_firecrawl_title_fallback_to_hostname(mock_post, firecrawl_configured):
    mock_post.return_value = _firecrawl_response(title="")

    result = fetch_url_text("https://example.com/article")
    assert result["title"] == "example.com"
