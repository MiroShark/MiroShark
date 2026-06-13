"""Unit tests for WebEnricher's SearXNG search-then-synthesize path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Config
from app.services.web_enrichment import WebEnricher
from app.utils.searxng_client import SearxngError


_RESULTS = [
    {"url": "https://example.com/musk", "title": "Elon Musk", "content": "CEO of Tesla.",
     "engine": "google", "score": 4.0, "publishedDate": ""},
]


@pytest.fixture
def enricher(monkeypatch):
    monkeypatch.setattr(Config, "WEB_ENRICHMENT_ENABLED", True)
    return WebEnricher()


def _mock_llm(response="- bullet one\n- bullet two\n- enough chars to pass the floor"):
    llm = MagicMock()
    llm.chat.return_value = response
    return llm


@patch("app.services.web_enrichment.create_llm_client")
@patch("app.services.web_enrichment.SearxngClient")
def test_searxng_path_grounds_prompt_with_default_llm(mock_client_cls, mock_create, enricher, monkeypatch):
    monkeypatch.setattr(Config, "WEB_SEARCH_MODEL", "perplexity/sonar-pro")
    mock_client = mock_client_cls.return_value
    mock_client.is_configured.return_value = True
    mock_client.search.return_value = _RESULTS
    mock_create.return_value = _mock_llm()

    result = enricher.enrich_if_needed("Elon Musk", "PublicFigure", "thin")

    assert result
    # Default LLM — no model override despite WEB_SEARCH_MODEL being set
    mock_create.assert_called_once_with()
    messages = mock_create.return_value.chat.call_args.kwargs["messages"]
    user_msg = messages[1]["content"]
    assert "https://example.com/musk" in user_msg
    assert "CEO of Tesla." in user_msg
    # Grounded system prompt mentions the search results
    assert "search results" in messages[0]["content"].lower()


@patch("app.services.web_enrichment.create_llm_client")
@patch("app.services.web_enrichment.SearxngClient")
def test_search_failure_falls_back_to_web_search_model(mock_client_cls, mock_create, enricher, monkeypatch):
    monkeypatch.setattr(Config, "WEB_SEARCH_MODEL", "perplexity/sonar-pro")
    mock_client = mock_client_cls.return_value
    mock_client.is_configured.return_value = True
    mock_client.search.side_effect = SearxngError("503")
    mock_create.return_value = _mock_llm()

    result = enricher.enrich_if_needed("Elon Musk", "PublicFigure", "thin")

    assert result
    mock_create.assert_called_once_with(model="perplexity/sonar-pro")
    messages = mock_create.return_value.chat.call_args.kwargs["messages"]
    assert "https://example.com/musk" not in messages[1]["content"]


@patch("app.services.web_enrichment.create_llm_client")
@patch("app.services.web_enrichment.SearxngClient")
def test_unconfigured_searxng_uses_legacy_path(mock_client_cls, mock_create, enricher, monkeypatch):
    monkeypatch.setattr(Config, "WEB_SEARCH_MODEL", "")
    mock_client = mock_client_cls.return_value
    mock_client.is_configured.return_value = False
    mock_create.return_value = _mock_llm()

    result = enricher.enrich_if_needed("Elon Musk", "PublicFigure", "thin")

    assert result
    mock_client.search.assert_not_called()
    mock_create.assert_called_once_with()


@patch("app.services.web_enrichment.create_llm_client")
@patch("app.services.web_enrichment.SearxngClient")
def test_cache_hit_skips_search(mock_client_cls, mock_create, enricher):
    mock_client = mock_client_cls.return_value
    mock_client.is_configured.return_value = True
    mock_client.search.return_value = _RESULTS
    mock_create.return_value = _mock_llm()

    first = enricher.enrich_if_needed("Elon Musk", "PublicFigure", "thin")
    second = enricher.enrich_if_needed("Elon Musk", "PublicFigure", "thin")

    assert first == second
    assert mock_client.search.call_count == 1


@patch("app.services.web_enrichment.SearxngClient")
def test_one_word_names_disambiguated_with_type(mock_client_cls, enricher):
    mock_client = mock_client_cls.return_value
    mock_client.is_configured.return_value = True
    mock_client.search.return_value = []

    enricher._search_web("Apple", "Company", "en")
    assert mock_client.search.call_args.args[0] == "Apple Company"

    enricher._search_web("Elon Musk", "PublicFigure", "en")
    assert mock_client.search.call_args.args[0] == "Elon Musk"
