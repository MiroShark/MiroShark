"""Unit tests for the SearXNG client — all HTTP mocked, no live instance."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.config import Config
from app.utils.searxng_client import (
    SearxngClient,
    SearxngError,
    format_results_block,
)


def _response(json_data=None, status=200, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("not json")
    if status >= 400:
        err = requests.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = err
    else:
        resp.raise_for_status.return_value = None
    return resp


_SAMPLE = {
    "query": "anthropic",
    "number_of_results": 100,
    "results": [
        {
            "url": "https://www.anthropic.com/",
            "title": "Home \\ Anthropic",
            "content": "AI safety and research company.",
            "engine": "bing",
            "score": 4.0,
            "publishedDate": None,
        },
        {
            "url": "https://claude.ai/",
            "title": "Claude",
            "content": None,
            "engine": "google",
            "score": 2.5,
            "publishedDate": "2026-01-01",
        },
        {"url": "", "title": "no url — dropped", "content": "x"},
        {"url": "https://example.com/3", "title": "Third", "content": "c3"},
    ],
}


def test_is_configured(monkeypatch):
    monkeypatch.setattr(Config, "SEARXNG_BASE_URL", "")
    assert not SearxngClient().is_configured()
    monkeypatch.setattr(Config, "SEARXNG_BASE_URL", "https://sxng.example.org")
    assert SearxngClient().is_configured()
    assert SearxngClient(base_url="https://other.example.org/").base_url == "https://other.example.org"


def test_search_unconfigured_raises(monkeypatch):
    monkeypatch.setattr(Config, "SEARXNG_BASE_URL", "")
    with pytest.raises(SearxngError):
        SearxngClient().search("test")


def test_search_empty_query_raises():
    client = SearxngClient(base_url="https://sxng.example.org")
    with pytest.raises(SearxngError):
        client.search("   ")


@patch("app.utils.searxng_client.requests.get")
def test_search_params_and_normalization(mock_get):
    mock_get.return_value = _response(_SAMPLE)
    client = SearxngClient(base_url="https://sxng.example.org")

    results = client.search("anthropic", language="en", max_results=10)

    args, kwargs = mock_get.call_args
    assert args[0] == "https://sxng.example.org/search"
    params = kwargs["params"]
    assert params["q"] == "anthropic"
    assert params["format"] == "json"
    assert params["language"] == "en"
    # Non-set optionals are not sent
    assert "engines" not in params and "time_range" not in params

    # Empty-url result dropped, content None → ''
    assert len(results) == 3
    assert results[0]["url"] == "https://www.anthropic.com/"
    assert results[1]["content"] == ""
    assert results[1]["publishedDate"] == "2026-01-01"
    assert all(
        set(r) == {"url", "title", "content", "engine", "score", "publishedDate"}
        for r in results
    )


@patch("app.utils.searxng_client.requests.get")
def test_search_max_results_truncation(mock_get):
    mock_get.return_value = _response(_SAMPLE)
    client = SearxngClient(base_url="https://sxng.example.org")
    assert len(client.search("anthropic", max_results=1)) == 1


@patch("app.utils.searxng_client.requests.get")
def test_search_default_max_results_from_config(mock_get, monkeypatch):
    monkeypatch.setattr(Config, "SEARXNG_MAX_RESULTS", 2)
    mock_get.return_value = _response(_SAMPLE)
    client = SearxngClient(base_url="https://sxng.example.org")
    assert len(client.search("anthropic")) == 2


@patch("app.utils.searxng_client.requests.get")
def test_4xx_raises_without_retry(mock_get):
    mock_get.return_value = _response(json_data={}, status=403, text="forbidden")
    client = SearxngClient(base_url="https://sxng.example.org", max_retries=3)
    with pytest.raises(SearxngError):
        client.search("test")
    assert mock_get.call_count == 1


@patch("app.utils.searxng_client.time.sleep")
@patch("app.utils.searxng_client.requests.get")
def test_5xx_retried_then_raises(mock_get, mock_sleep):
    mock_get.return_value = _response(json_data={}, status=503, text="overloaded")
    client = SearxngClient(base_url="https://sxng.example.org", max_retries=3)
    with pytest.raises(SearxngError):
        client.search("test")
    assert mock_get.call_count == 3


@patch("app.utils.searxng_client.time.sleep")
@patch("app.utils.searxng_client.requests.get")
def test_connection_error_retried(mock_get, mock_sleep):
    mock_get.side_effect = [
        requests.exceptions.ConnectionError("refused"),
        _response(_SAMPLE),
    ]
    client = SearxngClient(base_url="https://sxng.example.org", max_retries=3)
    results = client.search("anthropic", max_results=10)
    assert len(results) == 3
    assert mock_get.call_count == 2


@patch("app.utils.searxng_client.requests.get")
def test_non_json_response_raises(mock_get):
    mock_get.return_value = _response(json_data=None, text="<html>index</html>")
    client = SearxngClient(base_url="https://sxng.example.org", max_retries=1)
    with pytest.raises(SearxngError):
        client.search("test")


def test_format_results_block():
    results = [
        {"url": "https://a.example", "title": "Alpha", "content": "x" * 400,
         "publishedDate": "2026-01-01"},
        {"url": "https://b.example", "title": "Beta", "content": ""},
    ]
    block = format_results_block(results, max_snippet_chars=100)
    lines = block.splitlines()
    assert lines[0] == "[1] Alpha — https://a.example"
    assert lines[1].endswith("(published: 2026-01-01)")
    assert "…" in lines[1]  # truncated snippet
    assert lines[2] == "[2] Beta — https://b.example"
    assert len(lines) == 3  # empty snippet → no snippet line


@patch("app.utils.searxng_client.requests.get")
def test_html_stripped_from_snippets(mock_get):
    payload = {"results": [{
        "url": "https://a.example",
        "title": "Elon <strong>Musk</strong>",
        "content": "He said it&#x27;s <em>fine</em>.",
    }]}
    mock_get.return_value = _response(payload)
    client = SearxngClient(base_url="https://sxng.example.org")
    r = client.search("musk", max_results=1)[0]
    assert r["title"] == "Elon Musk"
    assert r["content"] == "He said it's fine."
