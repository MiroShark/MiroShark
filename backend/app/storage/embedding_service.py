"""
EmbeddingService — pluggable embedding via Ollama or OpenAI-compatible API

Supports two providers (set via EMBEDDING_PROVIDER env var):
  - "ollama"  (default): Uses Ollama's /api/embed endpoint
  - "openai":            Uses OpenAI-compatible /v1/embeddings endpoint
                         (works with OpenRouter, OpenAI, Azure, any compatible API)

Vector dimensions are configurable via EMBEDDING_DIMENSIONS (default: 768).
"""

import time
import logging
from typing import List, Optional

import requests

from ..config import Config

logger = logging.getLogger('miroshark.embedding')


class EmbeddingService:
    """Generate embeddings using Ollama or OpenAI-compatible API."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        # Explicit overrides (rare — tests, alternate pipelines). When None,
        # every property below falls through to Config at call time, so
        # POST /api/settings edits take effect without a restart.
        self._provider_override = provider.lower() if provider else None
        self._model_override = model
        self._base_url_override = base_url.rstrip('/') if base_url else None
        self._api_key_override = api_key
        self._dimensions_override = dimensions
        self.max_retries = max_retries
        self.timeout = timeout

        # Simple in-memory cache (text -> embedding vector)
        self._cache: dict[str, List[float]] = {}
        self._cache_max_size = 2000

    @property
    def provider(self) -> str:
        return (self._provider_override or Config.EMBEDDING_PROVIDER).lower()

    @property
    def model(self) -> str:
        return self._model_override or Config.EMBEDDING_MODEL

    @property
    def base_url(self) -> str:
        return (self._base_url_override or Config.EMBEDDING_BASE_URL).rstrip('/')

    @property
    def api_key(self) -> str:
        return self._api_key_override or Config.EMBEDDING_API_KEY

    @property
    def dimensions(self) -> int:
        return self._dimensions_override or Config.EMBEDDING_DIMENSIONS

    @property
    def _embed_url(self) -> str:
        if self.provider == 'openai':
            return f"{self.base_url}/v1/embeddings"
        return f"{self.base_url}/api/embed"

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Returns:
            Float vector of configured dimensions
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text")

        text = text.strip()

        if text in self._cache:
            return self._cache[text]

        vectors = self._request_embeddings([text])
        vector = vectors[0]

        self._cache_put(text, vector)
        return vector

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for i, text in enumerate(texts):
            text = text.strip() if text else ""
            if text in self._cache:
                results[i] = self._cache[text]
            elif text:
                uncached_indices.append(i)
                uncached_texts.append(text)
            else:
                results[i] = [0.0] * self.dimensions

        if uncached_texts:
            all_vectors: List[List[float]] = []
            for start in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[start:start + batch_size]
                vectors = self._request_embeddings(batch)
                all_vectors.extend(vectors)

            for idx, vec, text in zip(uncached_indices, all_vectors, uncached_texts):
                results[idx] = vec
                self._cache_put(text, vec)

        return results  # type: ignore

    def _request_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Dispatch to the correct provider backend."""
        if self.provider == 'openai':
            return self._request_openai(texts)
        return self._request_ollama(texts)

    def _request_ollama(self, texts: List[str]) -> List[List[float]]:
        """Ollama /api/embed endpoint."""
        payload = {
            "model": self.model,
            "input": texts,
        }
        return self._do_request(payload, self._parse_ollama_response)

    def _request_openai(self, texts: List[str]) -> List[List[float]]:
        """OpenAI-compatible /v1/embeddings endpoint."""
        payload = {
            "model": self.model,
            "input": texts,
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions
        return self._do_request(payload, self._parse_openai_response)

    def _do_request(self, payload: dict, parser) -> List[List[float]]:
        """HTTP POST with retry logic."""
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/aaronjmars/MiroShark",
            "X-OpenRouter-Title": "MiroShark - Universal Swarm Intelligence Engine",
            "X-OpenRouter-Categories": "roleplay",
            "User-Agent": "MiroShark/1.0 (EmbeddingService)",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self._embed_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return parser(response.json(), len(payload["input"]))

            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(
                    f"Embedding connection failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(
                    f"Embedding request timed out (attempt {attempt + 1}/{self.max_retries})"
                )
            except requests.exceptions.HTTPError as e:
                last_error = e
                logger.error(f"Embedding HTTP error: {e.response.status_code} - {e.response.text}")
                if e.response.status_code >= 500:
                    pass  # retry
                else:
                    raise EmbeddingError(f"Embedding request failed: {e}") from e
            except (KeyError, ValueError) as e:
                raise EmbeddingError(f"Invalid embedding response: {e}") from e

            if attempt < self.max_retries - 1:
                wait = 2 ** attempt
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)

        raise EmbeddingError(
            f"Embedding failed after {self.max_retries} retries: {last_error}"
        )

    @staticmethod
    def _parse_ollama_response(data: dict, expected_count: int) -> List[List[float]]:
        """Parse Ollama response: {"embeddings": [[...], ...]}"""
        embeddings = data.get("embeddings", [])
        if len(embeddings) != expected_count:
            raise EmbeddingError(
                f"Expected {expected_count} embeddings, got {len(embeddings)}"
            )
        return embeddings

    @staticmethod
    def _parse_openai_response(data: dict, expected_count: int) -> List[List[float]]:
        """Parse OpenAI response: {"data": [{"embedding": [...], "index": 0}, ...]}"""
        items = data.get("data", [])
        if len(items) != expected_count:
            raise EmbeddingError(
                f"Expected {expected_count} embeddings, got {len(items)}"
            )
        # Sort by index to preserve input order
        items.sort(key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in items]

    def _cache_put(self, text: str, vector: List[float]) -> None:
        """Add to cache, evicting oldest entries if full."""
        if len(self._cache) >= self._cache_max_size:
            keys_to_remove = list(self._cache.keys())[:self._cache_max_size // 10]
            for key in keys_to_remove:
                del self._cache[key]
        self._cache[text] = vector

    def health_check(self) -> bool:
        """Check if embedding endpoint is reachable."""
        try:
            vec = self.embed("health check")
            return len(vec) > 0
        except Exception:
            return False


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""
    pass
