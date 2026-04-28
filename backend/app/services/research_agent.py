"""
Research Agent
Given a topic, uses LLM to generate search queries, executes web searches,
and fetches content from the most relevant results.
"""

import json
import os
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from duckduckgo_search import DDGS

from ..utils.llm_client import create_llm_client
from ..utils.file_parser import fetch_url_text
from ..services.text_processor import TextProcessor
from ..utils.logger import get_logger

logger = get_logger("miroshark.research_agent")

GAP_ANALYSIS_PROMPT = """You are a research analyst. The user has provided some content and stated their intent.
Analyze what information is MISSING from the content to fulfill the user's intent.

USER INTENT: {intent}

CONTENT SUMMARY (first 3000 chars):
{content_preview}

Identify 5-8 specific knowledge gaps. For each gap, provide a targeted search query.
Return JSON:
{{
  "gaps": [
    {{"gap": "What's missing", "search_query": "specific search query to fill this gap"}},
    ...
  ],
  "content_assessment": "Brief assessment of what the content already covers well",
  "missing_depth": "What type of deeper information is needed (mechanisms, data, comparisons, etc.)"
}}"""

SEARCH_PLAN_PROMPT = """You are a research assistant. Given a topic, generate search queries
to find diverse, high-quality sources for understanding this topic from multiple perspectives.

Topic: {topic}

Generate 5-8 specific search queries that would find:
- News articles with recent developments
- Analysis and opinion pieces from different viewpoints
- Official statements or reports
- Background/context articles

Return ONLY a JSON array of search query strings, no other text.
Example: ["query one", "query two", "query three"]"""

RANK_PROMPT = """You are evaluating search results for relevance to a research topic.

Topic: {topic}

Below are search results. Score each from 0-10 for relevance and information value.
Return ONLY a JSON array of objects with "url" and "score" fields, sorted by score descending.
Only include results scoring 6 or higher.

Results:
{results_text}"""


@dataclass
class ResearchResult:
    url: str
    title: str
    snippet: str
    text: str = ""
    score: float = 0.0
    fetch_error: Optional[str] = None


@dataclass
class ResearchReport:
    topic: str
    intent: str = ""
    gaps: List[Dict] = field(default_factory=list)
    content_assessment: str = ""
    queries: List[str] = field(default_factory=list)
    results: List[ResearchResult] = field(default_factory=list)
    total_chars: int = 0

    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "intent": self.intent,
            "gaps": self.gaps,
            "content_assessment": self.content_assessment,
            "queries": self.queries,
            "results": [
                {
                    "url": r.url,
                    "title": r.title,
                    "snippet": r.snippet,
                    "text_length": len(r.text),
                    "score": r.score,
                    "fetch_error": r.fetch_error,
                }
                for r in self.results
            ],
            "total_chars": self.total_chars,
            "fetched_count": sum(1 for r in self.results if r.text),
        }


def _generate_search_queries(topic: str) -> List[str]:
    """Use LLM to generate targeted search queries for a topic."""
    client = create_llm_client()
    prompt = SEARCH_PLAN_PROMPT.format(topic=topic)
    try:
        response = client.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        # Handle both list and dict-with-list responses
        if isinstance(response, list):
            return [str(q) for q in response[:8]]
        if isinstance(response, dict):
            for key in ("queries", "search_queries", "results"):
                if key in response and isinstance(response[key], list):
                    return [str(q) for q in response[key][:8]]
    except Exception as err:
        logger.warning(f"LLM query generation failed: {err}")
    return [topic]


def _search_searxng(
    queries: List[str],
    max_results_per_query: int = 5,
    base_url: Optional[str] = None,
) -> List[Dict]:
    """Execute searches via a SearXNG instance.

    Uses /search?format=json. Returns the same {url, title, snippet, query}
    shape as _search_ddg. Empty list on network error or non-200 response.
    """
    if base_url is None:
        base_url = os.environ.get("SEARXNG_BASE_URL", "")
    if not base_url:
        return []

    seen_urls: set = set()
    all_results: List[Dict] = []

    for query in queries:
        try:
            response = requests.get(
                f"{base_url.rstrip('/')}/search",
                params={"q": query, "format": "json", "language": "en"},
                timeout=15,
            )
        except requests.exceptions.RequestException as exc:
            logger.warning(f"SearXNG request failed for '{query}': {exc}")
            continue

        if response.status_code != 200:
            logger.warning(
                f"SearXNG non-200 for '{query}': HTTP {response.status_code}"
            )
            continue

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning(f"SearXNG bad JSON for '{query}': {exc}")
            continue

        items = payload.get("results", []) or []
        for item in items[:max_results_per_query]:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({
                    "url": url,
                    "title": item.get("title", "") or "",
                    "snippet": item.get("content", "") or item.get("body", "") or "",
                    "query": query,
                })

    logger.info(
        f"SearXNG: {len(all_results)} unique results from {len(queries)} queries"
    )
    return all_results


def _search_ddg(queries: List[str], max_results_per_query: int = 5) -> List[Dict]:
    """Execute DuckDuckGo searches and deduplicate results.

    For each query, try the news endpoint first (better source provenance for
    recent topics). If news returns nothing, fall back to the general text
    endpoint so policy/historical topics aren't lost.

    Region defaults to us-en for English-language bias — research is currently
    English-only. Override at call site if a future caller needs other locales.
    """
    seen_urls = set()
    all_results = []

    for query in queries:
        results = []
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(query, region="us-en", max_results=max_results_per_query))
        except Exception as search_err:
            logger.warning(f"News search failed for '{query}': {search_err}")

        if not results:
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, region="us-en", max_results=max_results_per_query))
                if results:
                    logger.info(f"Text-search fallback yielded {len(results)} results for '{query}'")
            except Exception as text_err:
                logger.warning(f"Text-search fallback failed for '{query}': {text_err}")

        for result in results:
            url = result.get("url", "") or result.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append({
                    "url": url,
                    "title": result.get("title", ""),
                    "snippet": result.get("body", "") or result.get("excerpt", ""),
                    "query": query,
                })

    logger.info(f"Found {len(all_results)} unique results from {len(queries)} queries")
    return all_results


def _rank_results(topic: str, results: List[Dict], max_keep: int = 10) -> List[Dict]:
    """Use LLM to rank results by relevance, keep top N."""
    if len(results) <= max_keep:
        return results

    results_text = "\n".join(
        f"- URL: {r['url']}\n  Title: {r['title']}\n  Snippet: {r['snippet']}"
        for r in results[:30]
    )

    try:
        client = create_llm_client()
        prompt = RANK_PROMPT.format(topic=topic, results_text=results_text)
        ranked = client.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        if isinstance(ranked, dict):
            for key in ("results", "rankings", "ranked"):
                if key in ranked and isinstance(ranked[key], list):
                    ranked = ranked[key]
                    break
        if isinstance(ranked, list):
            scored_urls = {item["url"]: item.get("score", 0) for item in ranked if isinstance(item, dict)}
            for result in results:
                result["score"] = scored_urls.get(result["url"], 0)
            results.sort(key=lambda r: r.get("score", 0), reverse=True)
    except Exception as rank_err:
        logger.warning(f"Ranking failed, using original order: {rank_err}")

    return results[:max_keep]


def _is_mostly_non_latin(text: str, threshold: float = 0.5) -> bool:
    """True when more than `threshold` of non-whitespace chars are non-Latin.

    Catches CJK/Arabic/Cyrillic content that slipped past region filters.
    Cheap heuristic — counts code points outside Basic Latin / Latin-1
    Supplement / Latin Extended ranges.
    """
    if not text:
        return False
    non_whitespace = [c for c in text if not c.isspace()]
    if len(non_whitespace) < 50:
        return False
    non_latin = sum(1 for c in non_whitespace if ord(c) > 0x024F)
    return (non_latin / len(non_whitespace)) > threshold


def _fetch_content(results: List[Dict]) -> List[ResearchResult]:
    """Fetch and extract text from each URL."""
    research_results = []
    for result in results:
        rr = ResearchResult(
            url=result["url"],
            title=result["title"],
            snippet=result["snippet"],
            score=result.get("score", 0),
        )
        try:
            raw_text = fetch_url_text(result["url"], timeout=15)
            rr.text = TextProcessor.preprocess_text(raw_text)
            if _is_mostly_non_latin(rr.text):
                logger.info(f"Dropping non-English content from {result['url']}")
                rr.text = ""
                rr.fetch_error = "non_english_content"
            else:
                logger.info(f"Fetched {len(rr.text)} chars from {result['url']}")
        except Exception as fetch_err:
            rr.fetch_error = str(fetch_err)
            logger.warning(f"Failed to fetch {result['url']}: {fetch_err}")
        research_results.append(rr)
    return research_results


def research_topic(topic: str, max_sources: int = 10) -> ResearchReport:
    """
    Research a topic end-to-end: generate queries, search, rank, fetch content.

    Args:
        topic: The topic to research.
        max_sources: Maximum number of sources to fetch.

    Returns:
        ResearchReport with all gathered data.
    """
    logger.info(f"Starting research on topic: {topic}")
    report = ResearchReport(topic=topic)

    # Step 1: Generate search queries
    logger.info("Step 1: Generating search queries...")
    report.queries = _generate_search_queries(topic)
    logger.info(f"Generated {len(report.queries)} queries: {report.queries}")

    # Step 2: Execute searches
    logger.info("Step 2: Searching...")
    raw_results = _search_searxng(report.queries)
    if not raw_results:
        logger.info("SearXNG returned no results; falling back to DDG")
        raw_results = _search_ddg(report.queries)

    # Step 3: Rank and filter
    logger.info("Step 3: Ranking results...")
    ranked = _rank_results(topic, raw_results, max_keep=max_sources)

    # Step 4: Fetch content
    logger.info(f"Step 4: Fetching content from {len(ranked)} sources...")
    report.results = _fetch_content(ranked)
    report.total_chars = sum(len(r.text) for r in report.results)

    fetched = sum(1 for r in report.results if r.text)
    logger.info(f"Research complete: {fetched}/{len(report.results)} sources fetched, {report.total_chars} total chars")

    return report


def _analyze_gaps(intent: str, content: str) -> Dict:
    """Use LLM to identify knowledge gaps between content and user intent."""
    client = create_llm_client()
    prompt = GAP_ANALYSIS_PROMPT.format(
        intent=intent,
        content_preview=content[:3000],
    )
    try:
        result = client.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        if isinstance(result, dict):
            return result
    except Exception as err:
        logger.warning(f"Gap analysis failed: {err}")
    return {"gaps": [], "content_assessment": "", "missing_depth": ""}


def research_with_intent(
    topic: str,
    intent: str,
    initial_content: str = "",
    max_sources: int = 10,
) -> ResearchReport:
    """
    Intent-guided research: analyze what's missing, then search to fill gaps.

    Args:
        topic: The topic or URL content summary.
        intent: What the user wants to understand (e.g., "the science behind gene modification").
        initial_content: Any content already provided (article text, URL content).
        max_sources: Maximum sources to fetch.

    Returns:
        ResearchReport with gap analysis and targeted sources.
    """
    logger.info(f"Starting intent-guided research: intent='{intent[:80]}', topic='{topic[:80]}'")
    report = ResearchReport(topic=topic, intent=intent)

    # Step 1: Analyze gaps between content and intent
    logger.info("Step 1: Analyzing knowledge gaps...")
    gap_analysis = _analyze_gaps(intent, initial_content or topic)
    report.gaps = gap_analysis.get("gaps", [])
    report.content_assessment = gap_analysis.get("content_assessment", "")

    logger.info(f"Found {len(report.gaps)} knowledge gaps")
    for gap in report.gaps:
        logger.info(f"  Gap: {gap.get('gap', '')[:60]}")

    # Step 2: Generate search queries from gaps (targeted, not generic)
    gap_queries = [g["search_query"] for g in report.gaps if "search_query" in g]
    if not gap_queries:
        gap_queries = _generate_search_queries(f"{topic} {intent}")
    report.queries = gap_queries

    # Step 3: Search
    logger.info(f"Step 2: Searching with {len(gap_queries)} targeted queries...")
    raw_results = _search_searxng(gap_queries)
    if not raw_results:
        logger.info("SearXNG returned no results; falling back to DDG")
        raw_results = _search_ddg(gap_queries)

    # Step 4: Rank with intent awareness
    logger.info("Step 3: Ranking results against intent...")
    ranked = _rank_results(f"{topic} — Intent: {intent}", raw_results, max_keep=max_sources)

    # Step 5: Fetch content
    logger.info(f"Step 4: Fetching content from {len(ranked)} sources...")
    report.results = _fetch_content(ranked)
    report.total_chars = sum(len(r.text) for r in report.results)

    fetched = sum(1 for r in report.results if r.text)
    logger.info(
        f"Intent research complete: {fetched}/{len(report.results)} sources, "
        f"{report.total_chars} chars, {len(report.gaps)} gaps addressed"
    )
    return report
