"""
RerankerService — cross-encoder reranker for hybrid search results.

Runs a cross-encoder over (query, doc) pairs and returns relevance scores
far more precise than cosine similarity alone. Used after vector+BM25 fusion
in SearchService to reorder the top-K candidates.

Default model: BAAI/bge-reranker-v2-m3 (multilingual, ~568M params, ~1GB).
Downloaded on first use and cached by sentence-transformers.
"""

import logging
import threading
from typing import List, Optional, Tuple

from ..config import Config

logger = logging.getLogger('miroshark.reranker')


class RerankerService:
    """Cross-encoder reranker. Lazy-loads the model on first call."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self._model_name_override = model_name
        self._enabled_override = enabled
        self._model = None
        self._load_lock = threading.Lock()
        self._load_failed = False

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return Config.RERANKER_ENABLED

    @property
    def model_name(self) -> str:
        return self._model_name_override or Config.RERANKER_MODEL

    @staticmethod
    def _select_device() -> str:
        """Pick a torch device for the cross-encoder.

        Honors an explicit ``RERANKER_DEVICE`` override; otherwise prefers CUDA
        and falls back to CPU. MPS (Apple-Silicon GPU) is intentionally skipped
        in auto mode — torch can hang indefinitely compiling Metal shader
        pipelines for this cross-encoder, pegging a core and stalling retrieval.
        """
        if Config.RERANKER_DEVICE:
            return Config.RERANKER_DEVICE
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _ensure_loaded(self) -> bool:
        """Load the cross-encoder lazily. Returns False on failure."""
        if self._model is not None:
            return True
        if self._load_failed:
            return False

        with self._load_lock:
            if self._model is not None:
                return True
            if self._load_failed:
                return False

            try:
                from sentence_transformers import CrossEncoder
                device = self._select_device()
                logger.info(
                    f"Loading cross-encoder reranker: {self.model_name} (device={device})"
                )
                self._model = CrossEncoder(self.model_name, max_length=512, device=device)
                logger.info(f"Reranker ready: {self.model_name}")
                return True
            except Exception as e:
                logger.error(
                    f"Reranker load failed ({self.model_name}): {e}. "
                    "Falling back to fused scores."
                )
                self._load_failed = True
                return False

    def rerank(
        self,
        query: str,
        docs: List[str],
    ) -> Optional[List[float]]:
        """
        Score each (query, doc) pair. Returns scores aligned to docs, or None
        if reranking is disabled or failed.
        """
        if not self.enabled or not docs:
            return None
        if not self._ensure_loaded():
            return None

        try:
            pairs = [(query, doc) for doc in docs]
            scores = self._model.predict(pairs, show_progress_bar=False)
            return [float(s) for s in scores]
        except Exception as e:
            logger.warning(f"Reranker inference failed: {e}. Using fused scores.")
            return None

    def rerank_with_indices(
        self,
        query: str,
        docs: List[str],
        top_k: Optional[int] = None,
    ) -> Optional[List[Tuple[int, float]]]:
        """
        Return [(original_index, score), ...] sorted by score descending.
        Convenience wrapper around rerank().
        """
        scores = self.rerank(query, docs)
        if scores is None:
            return None
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        if top_k is not None:
            indexed = indexed[:top_k]
        return indexed
