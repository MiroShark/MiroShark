"""
Research Agent
Given a topic, uses LLM to generate search queries, executes web searches,
and fetches content from the most relevant results.
"""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from duckduckgo_search import DDGS

from ..utils.llm_client import create_llm_client
from ..utils.file_parser import fetch_url_text
from ..services.text_processor import TextProcessor
from ..utils.logger import get_logger

logger = get_logger("miroshark.research_agent")

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
    queries: List[str] = field(default_factory=list)
    results: List[ResearchResult] = field(default_factory=list)
    total_chars: int = 0

    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
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


def _search_ddg(queries: List[str], max_results_per_query: int = 5) -> List[Dict]:
    """Execute DuckDuckGo searches and deduplicate results."""
    seen_urls = set()
    all_results = []

    for query in queries:
        try:
            with DDGS() as ddgs:
                # Use news endpoint for better English results globally
                results = list(ddgs.news(query, region="wt-wt", max_results=max_results_per_query))
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
        except Exception as search_err:
            logger.warning(f"Search failed for '{query}': {search_err}")

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
