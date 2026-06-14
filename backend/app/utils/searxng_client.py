"""
SearXNG client — real web search via a self-hosted SearXNG instance.

Hits ``GET {MIROSHARK_SEARXNG_BASE_URL}/search?format=json`` and returns normalized
result dicts. When configured, web enrichment uses this to ground persona
research with live search snippets so ANY model can synthesize them — no
websearch-enabled LLM (`:online` / Perplexity sonar) required.

Configuration falls through to Config at call time (same pattern as
EmbeddingService), so POST /api/settings edits apply without a restart.
"""

import html
import re
import time
from typing import List, Optional

import requests

from ..config import Config
from .logger import get_logger

logger = get_logger("miroshark.searxng")


class SearxngError(Exception):
    """Raised when a SearXNG search request fails."""
    pass


def _clean_text(value: str) -> str:
    """Strip HTML tags/entities some engines leave in titles and snippets."""
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip()


class SearxngClient:
    """Thin JSON-API client for a SearXNG instance."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: int = 3,
    ):
        # Explicit overrides (tests, alternate pipelines). When None, the
        # properties below fall through to Config at call time.
        self._base_url_override = base_url.rstrip('/') if base_url else None
        self._timeout_override = timeout
        self.max_retries = max_retries

    @property
    def base_url(self) -> str:
        return (self._base_url_override or Config.SEARXNG_BASE_URL or '').rstrip('/')

    @property
    def timeout(self) -> int:
        return self._timeout_override or Config.SEARXNG_TIMEOUT

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def search(
        self,
        query: str,
        *,
        categories: Optional[str] = None,
        engines: Optional[str] = None,
        language: Optional[str] = None,
        time_range: Optional[str] = None,
        safesearch: Optional[int] = None,
        pageno: int = 1,
        max_results: Optional[int] = None,
    ) -> List[dict]:
        """Run a search and return normalized result dicts.

        Each result has keys: url, title, content, engine, score,
        publishedDate (all present, '' / 0 when the engine omits them).

        Raises:
            SearxngError: when unconfigured, on 4xx, exhausted retries,
                or a non-JSON response body.
        """
        if not self.is_configured():
            raise SearxngError("MIROSHARK_SEARXNG_BASE_URL is not configured")
        if not query or not query.strip():
            raise SearxngError("Cannot search with an empty query")

        params = {'q': query.strip(), 'format': 'json'}
        if categories:
            params['categories'] = categories
        if engines:
            params['engines'] = engines
        if language:
            params['language'] = language
        if time_range:
            params['time_range'] = time_range
        if safesearch is not None:
            params['safesearch'] = safesearch
        if pageno and pageno != 1:
            params['pageno'] = pageno

        data = self._do_request(params)

        if max_results is None:
            max_results = Config.SEARXNG_MAX_RESULTS

        results = []
        for raw in data.get('results', []):
            url = (raw.get('url') or '').strip()
            if not url:
                continue
            results.append({
                'url': url,
                'title': _clean_text(raw.get('title') or ''),
                'content': _clean_text(raw.get('content') or ''),
                'engine': raw.get('engine') or '',
                'score': raw.get('score') or 0,
                'publishedDate': raw.get('publishedDate') or '',
            })
            if len(results) >= max_results:
                break

        logger.info(f"SearXNG search '{query.strip()[:80]}': {len(results)} results")
        return results

    def _do_request(self, params: dict) -> dict:
        """GET /search with retry on connection errors / timeouts / 5xx."""
        url = f"{self.base_url}/search"
        # Some SearXNG instances rate-limit default python user agents.
        headers = {"User-Agent": "MiroShark/1.0 (SearxngClient)"}

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url, params=params, headers=headers, timeout=self.timeout,
                )
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as e:
                    raise SearxngError(
                        f"SearXNG returned non-JSON response: {response.text[:200]}"
                    ) from e

            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(
                    f"SearXNG connection failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(
                    f"SearXNG request timed out (attempt {attempt + 1}/{self.max_retries})"
                )
            except requests.exceptions.HTTPError as e:
                last_error = e
                status = e.response.status_code
                logger.warning(f"SearXNG HTTP error: {status} - {e.response.text[:200]}")
                if status < 500:
                    # 403 = JSON format disabled on the instance; 429 = rate limit
                    raise SearxngError(f"SearXNG request failed: {e}") from e
                # 5xx → retry

            if attempt < self.max_retries - 1:
                wait = 2 ** attempt
                logger.info(f"Retrying SearXNG in {wait}s...")
                time.sleep(wait)

        raise SearxngError(
            f"SearXNG search failed after {self.max_retries} retries: {last_error}"
        )


def format_results_block(results: List[dict], max_snippet_chars: int = 300) -> str:
    """Format normalized results as a numbered sources block for prompts.

    [1] Title — https://example.com
        Snippet text… (published: 2026-01-01)
    """
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get('title') or r.get('url') or ''
        lines.append(f"[{i}] {title} — {r.get('url', '')}")
        snippet = (r.get('content') or '').strip()
        if snippet:
            if len(snippet) > max_snippet_chars:
                snippet = snippet[:max_snippet_chars].rstrip() + '…'
            suffix = ''
            if r.get('publishedDate'):
                suffix = f" (published: {r['publishedDate']})"
            lines.append(f"    {snippet}{suffix}")
    return "\n".join(lines)
