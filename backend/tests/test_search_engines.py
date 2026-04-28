"""Tests for search engine implementations in research_agent."""

from unittest.mock import patch, MagicMock


def test_search_searxng_returns_normalized_results():
    """SearXNG JSON results are mapped to the standard {url, title, snippet, query} shape."""
    from app.services.research_agent import _search_searxng

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "results": [
            {"url": "https://www.afr.com/article-1", "title": "AFR piece",
             "content": "Body snippet from AFR."},
            {"url": "https://www.theguardian.com/article-2", "title": "Guardian piece",
             "content": "Guardian body snippet."},
        ]
    }

    with patch("app.services.research_agent.requests.get", return_value=fake_response):
        results = _search_searxng(["q1"], max_results_per_query=5, base_url="http://test:8888")

    assert len(results) == 2
    assert results[0]["url"] == "https://www.afr.com/article-1"
    assert results[0]["title"] == "AFR piece"
    assert results[0]["snippet"] == "Body snippet from AFR."
    assert results[0]["query"] == "q1"


def test_search_searxng_dedupes_across_queries():
    from app.services.research_agent import _search_searxng

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "results": [
            {"url": "https://example.com/a", "title": "A", "content": "x"},
        ]
    }

    with patch("app.services.research_agent.requests.get", return_value=fake_response):
        results = _search_searxng(["q1", "q2"], max_results_per_query=5, base_url="http://test:8888")

    # Same URL appears in both query responses (mock returns same payload)
    # Dedup should leave just one result
    assert len(results) == 1


def test_search_searxng_handles_non_200_response():
    from app.services.research_agent import _search_searxng

    fake_response = MagicMock()
    fake_response.status_code = 500
    fake_response.json.return_value = {"results": []}

    with patch("app.services.research_agent.requests.get", return_value=fake_response):
        results = _search_searxng(["q1"], max_results_per_query=5, base_url="http://test:8888")

    assert results == []


def test_search_searxng_handles_request_exception():
    """Network errors should not crash; return empty list and log."""
    import requests
    from app.services.research_agent import _search_searxng

    with patch(
        "app.services.research_agent.requests.get",
        side_effect=requests.exceptions.ConnectionError("DNS fail"),
    ):
        results = _search_searxng(["q1"], max_results_per_query=5, base_url="http://test:8888")

    assert results == []
