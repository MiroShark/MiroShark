"""
URL fetching and text extraction utility for MiroShark document ingestion.

Primary path: a self-hosted Firecrawl-for-agents instance (MIROSHARK_FIRECRAWL_BASE_URL)
scrapes the page via POST /v1/scrape and returns markdown — handles JS-heavy
pages (automatic fetch → CycleTLS → Hero browser fallback) and PDFs/DOCX.

Fallback path: ask the configured web-search LLM (WEB_SEARCH_MODEL, e.g.
`deepseek/deepseek-v4-flash:online`) to read the URL and return the main
readable content. The model MUST have web access — use an `:online` variant
on OpenRouter for any model without native browsing, otherwise it'll reject
URLs dated past its training cutoff.

SSRF protection: host + resolved-IP validation is applied before either
path so a malicious URL can't coerce a fetch of an internal address.
"""

import json
import re
import socket
import ipaddress
from urllib.parse import urlparse

import requests

from ..config import Config
from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.url_fetcher")


def _check_ip(ip_str: str) -> None:
    """Raises ValueError if the IP is private/loopback/reserved."""
    addr = ipaddress.ip_address(ip_str)
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise ValueError(
            f"Requests to private or internal addresses are not allowed ({ip_str})"
        )


def _validate_url(url: str) -> str:
    """Validate scheme/host and check resolved IP. Returns the hostname."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(
            f"Only http and https URLs are supported (got '{parsed.scheme}')"
        )
    if not parsed.netloc:
        raise ValueError("Invalid URL: missing host")
    host = parsed.netloc.split(':')[0]
    try:
        _check_ip(socket.gethostbyname(host))
    except socket.gaierror:
        pass  # let the model surface the DNS error
    return host


_EXTRACT_SYSTEM_PROMPT = """\
You are a web page extractor. Given a URL, fetch it and return its main \
readable content (article body, post text, documentation, etc.) as plain text. \
Strip navigation, ads, footers, cookie banners, sidebars, and boilerplate.

Respond with STRICT JSON only, no markdown fences, matching this schema:
{"title": "<page title>", "text": "<full readable body text>"}

Rules:
- If the page is inaccessible or you cannot retrieve it, respond with:
  {"title": "", "text": "", "error": "<short reason>"}
- Do NOT summarize. Return the full readable content verbatim.
- Do NOT invent content. If unsure, return the error shape above.\
"""


def _parse_model_json(raw: str) -> dict:
    """Parse model output as JSON, tolerating ``` fences and stray prose."""
    s = raw.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Fallback: find first {...} block
    match = re.search(r'\{.*\}', s, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Model did not return valid JSON: {raw[:200]}")


def _fetch_via_firecrawl(url: str, timeout: int) -> tuple:
    """Scrape a URL via Firecrawl-for-agents. Returns (title, text).

    Raises ValueError on HTTP errors or unusable responses.
    """
    base = Config.FIRECRAWL_BASE_URL
    headers = {"Content-Type": "application/json"}
    if Config.FIRECRAWL_API_KEY:
        headers["Authorization"] = f"Bearer {Config.FIRECRAWL_API_KEY}"

    logger.info(f"Fetching URL via Firecrawl: {url}")
    try:
        response = requests.post(
            f"{base}/v1/scrape",
            json={"url": url, "formats": ["markdown"], "timeout": timeout * 1000},
            headers=headers,
            timeout=timeout + 10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        raise ValueError(f"Firecrawl scrape failed: {exc}") from exc

    if not payload.get("success"):
        raise ValueError(f"Firecrawl scrape failed: {payload.get('error', 'unknown error')}")

    data = payload.get("data") or {}
    text = (data.get("markdown") or "").strip()
    title = ((data.get("metadata") or {}).get("title") or "").strip()
    return title, text


def _fetch_via_llm(url: str, timeout: int) -> tuple:
    """Extract a URL's content via the web-search LLM. Returns (title, text).

    Raises ValueError when no model is configured or the model fails.
    """
    model = Config.WEB_SEARCH_MODEL or Config.LLM_MODEL_NAME
    if not model:
        raise ValueError(
            "No web-search model configured. Set WEB_SEARCH_MODEL in .env "
            "(e.g. deepseek/deepseek-v4-flash:online)."
        )

    logger.info(f"Fetching URL via LLM ({model}): {url}")

    client = create_llm_client(model=model, timeout=timeout)

    messages = [
        {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract the readable content from this URL: {url}"},
    ]

    try:
        raw = client.chat(messages, temperature=0.0, max_tokens=16000)
    except Exception as exc:
        logger.error(f"LLM URL fetch failed: {exc}")
        raise ValueError(f"Failed to fetch URL via model: {exc}") from exc

    try:
        parsed = _parse_model_json(raw)
    except ValueError:
        # Model returned plain text — treat it as the body, derive title from URL.
        text = raw.strip()
        parsed = {"title": "", "text": text}

    if parsed.get("error"):
        raise ValueError(f"Model could not fetch URL: {parsed['error']}")

    return (parsed.get("title") or "").strip(), (parsed.get("text") or "").strip()


def fetch_url_text(url: str, timeout: int = 60) -> dict:
    """
    Fetch a URL and return its readable content.

    Uses Firecrawl (MIROSHARK_FIRECRAWL_BASE_URL) when configured, falling back to the
    web-search LLM path on failure or when unconfigured.

    Args:
        url: The URL to fetch (must be http or https).
        timeout: Per-request timeout in seconds.

    Returns:
        dict with keys:
            - title (str): Page title (or hostname fallback)
            - text (str): Extracted plain text content
            - url (str): The original URL
            - char_count (int): Length of extracted text

    Raises:
        ValueError: For invalid URLs, blocked addresses, or unextractable content.
    """
    _validate_url(url)

    title, text = "", ""
    if Config.FIRECRAWL_BASE_URL:
        try:
            title, text = _fetch_via_firecrawl(url, timeout)
        except ValueError as exc:
            logger.warning(f"Firecrawl fetch failed, falling back to LLM: {exc}")

    if len(text) < 100:
        title, text = _fetch_via_llm(url, timeout)

    if len(text) < 100:
        raise ValueError(
            "Could not extract meaningful text from the page. "
            "The page may be blocked, empty, or unreachable."
        )

    if not title:
        parsed_url = urlparse(url)
        title = parsed_url.netloc or url

    # Cap title length — some sites stuff the entire deck into <title>.
    MAX_TITLE_CHARS = 120
    if len(title) > MAX_TITLE_CHARS:
        title = title[:MAX_TITLE_CHARS - 1].rstrip() + '…'

    return {
        'title': title,
        'text': text,
        'url': url,
        'char_count': len(text),
    }
