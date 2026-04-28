"""Graph building service backed by GraphStorage (Neo4j)."""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..models.task import TaskManager, TaskStatus
from ..storage import GraphStorage
from ..utils.event_logger import EventLogger
from ..utils.trace_context import TraceContext
from .text_processor import TextProcessor

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

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroShark Graph",
        chunk_size: int = 1000,
        chunk_overlap: int = 50,
        max_workers: int = 6
    ) -> str:
        """
        Build graph asynchronously

        Args:
            text: Input text to process
            ontology: Ontology definition (from ontology generator output)
            graph_name: Name for the graph
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap size
            batch_size: Number of chunks to send per batch

        Returns:
            Task ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, max_workers)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        max_workers: int
    ):
        """Graph build worker thread"""
        build_t0 = time.time()
        graph_id = None
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="Starting graph building..."
            )
            _events.emit('graph_build', {
                'phase': 'start', 'graph_name': graph_name,
                'text_length': len(text), 'chunk_size': chunk_size,
            })

            # 1. Create graph
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"Graph created: {graph_id}"
            )

            # 2. Set ontology
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="Ontology set"
            )
            _events.emit('graph_build', {
                'phase': 'ontology_set', 'graph_id': graph_id,
                'entity_types': [et.get('name', et) for et in ontology.get('entity_types', [])],
            })

            # 3. Text chunking
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"Text split into {total_chunks} chunks"
            )
            _events.emit('graph_build', {
                'phase': 'chunking_done', 'graph_id': graph_id,
                'total_chunks': total_chunks,
            })

            # 4. Process chunks in parallel (NER + embedding + Neo4j insert)
            def _progress_with_events(msg, prog):
                self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.6),  # 20-80%
                    message=msg
                )
                _events.emit('graph_build', {
                    'phase': 'ner_progress', 'graph_id': graph_id,
                    'completed_chunks': int(prog * total_chunks),
                    'total_chunks': total_chunks,
                    'message': msg,
                })

            # Tag every NER/graph-extract LLM call inside the worker pool
            # so Langfuse can isolate this phase. add_text_batches uses a
            # ThreadPoolExecutor and TraceContext is thread-local, so the
            # parent thread's set is sufficient (workers inherit via the
            # wrapper inside add_text_batches when present).
            TraceContext.set(sim_phase="setup", prompt_type="graph_extract")
            episode_uuids = self.add_text_batches(
                graph_id, chunks, max_workers, _progress_with_events
            )
            TraceContext.set(sim_phase="", prompt_type="")

            # 5. Wait for processing (no-op for Neo4j — already synchronous)
            self.storage.wait_for_processing(episode_uuids)

            self.task_manager.update_task(
                task_id,
                progress=85,
                message="Data processing completed, getting graph information..."
            )

            # 6. Get graph information
            graph_info = self._get_graph_info(graph_id)

            elapsed_ms = round((time.time() - build_t0) * 1000)
            _events.emit('graph_build', {
                'phase': 'complete', 'graph_id': graph_id,
                'node_count': graph_info.node_count,
                'edge_count': graph_info.edge_count,
                'entity_types': graph_info.entity_types,
                'elapsed_ms': elapsed_ms,
            })

            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            _events.emit('error', {
                'error_class': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc(),
                'context': 'graph_builder._build_graph_worker',
                'severity': 'error',
            })
            self.task_manager.fail_task(task_id, error_msg)

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
        progress_callback: Optional[Callable] = None
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
