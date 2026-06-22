"""Graph building service backed by GraphStorage (Neo4j)."""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..models.task import TaskManager
from ..storage import GraphStorage
from ..utils.event_logger import EventLogger
from ..utils.trace_context import TraceContext

logger = logging.getLogger('miroshark.graph_builder')
_events = EventLogger()


@dataclass
class GraphInfo:
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """Builds a knowledge graph through the GraphStorage interface."""

    def __init__(self, storage: GraphStorage):
        self.storage = storage
        self.task_manager = TaskManager()

    def create_graph(self, name: str) -> str:
        """Create graph"""
        return self.storage.create_graph(
            name=name,
            description="MiroShark Social Simulation Graph"
        )

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """Store the ontology JSON on the Graph node for the NER extractor to read."""
        self.storage.set_ontology(graph_id, ontology)

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        max_workers: int = 6,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> List[str]:
        """Add text chunks to graph in parallel, return uuid list of all episodes.

        Uses a single thread pool across all chunks (no artificial batch
        boundaries). NER extraction is I/O-bound (LLM call), so 6 concurrent
        workers gives near-linear speedup without overwhelming the API.
        """
        episode_uuids = []
        total_chunks = len(chunks)
        completed = 0
        _lock = threading.Lock()

        logger.info(f"[graph_build] Starting: {total_chunks} chunks, {max_workers} concurrent workers")

        def _process_chunk(chunk_idx: int, chunk: str) -> str:
            chunk_preview = chunk[:80].replace('\n', ' ')
            logger.info(
                f"[graph_build] Chunk {chunk_idx}/{total_chunks} "
                f"({len(chunk)} chars): \"{chunk_preview}...\""
            )
            t0 = time.time()
            episode_id = self.storage.add_text(graph_id, chunk)
            elapsed = time.time() - t0
            logger.info(
                f"[graph_build] Chunk {chunk_idx}/{total_chunks} done in {elapsed:.1f}s"
            )
            return episode_id

        # Snapshot the caller's TraceContext so workers see the same
        # sim_phase / prompt_type / simulation_id (threading.local does
        # not propagate across pool workers).
        _process_chunk_traced = TraceContext.wrap_fn(_process_chunk)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for i, chunk in enumerate(chunks):
                if not chunk or not chunk.strip():
                    continue
                chunk_idx = i + 1
                future = pool.submit(_process_chunk_traced, chunk_idx, chunk)
                futures[future] = chunk_idx

            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    episode_id = future.result()
                    episode_uuids.append(episode_id)
                    with _lock:
                        completed += 1
                        current = completed
                    if progress_callback:
                        progress_callback(
                            f"Chunk {current}/{total_chunks} done",
                            current / total_chunks
                        )
                except Exception as e:
                    logger.error(
                        f"[graph_build] Chunk {chunk_idx}/{total_chunks} FAILED: {e}"
                    )
                    if progress_callback:
                        progress_callback(f"Chunk {chunk_idx} failed: {str(e)}", 0)
                    raise

        logger.info(f"[graph_build] All {total_chunks} chunks processed successfully")
        return episode_uuids

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """Get graph information"""
        info = self.storage.get_graph_info(graph_id)
        return GraphInfo(
            graph_id=info["graph_id"],
            node_count=info["node_count"],
            edge_count=info["edge_count"],
            entity_types=info.get("entity_types", []),
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """Get complete graph data (including details)"""
        return self.storage.get_graph_data(graph_id)

    def delete_graph(self, graph_id: str):
        """Delete graph"""
        self.storage.delete_graph(graph_id)
