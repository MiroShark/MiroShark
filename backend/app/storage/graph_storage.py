"""
GraphStorage — abstract interface for graph storage backends.

All Zep Cloud calls are replaced by this abstraction.
Current implementation: Neo4jStorage (neo4j_storage.py).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable


class GraphStorage(ABC):
    """Abstract interface for graph storage backends."""

    # --- Graph lifecycle ---

    @abstractmethod
    def create_graph(self, name: str, description: str = "") -> str:
        """Create a new graph. Returns graph_id."""

    @abstractmethod
    def delete_graph(self, graph_id: str) -> None:
        """Delete a graph and all its nodes/edges."""

    @abstractmethod
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        """Store ontology (entity types + relation types) for a graph."""

    @abstractmethod
    def get_ontology(self, graph_id: str) -> Dict[str, Any]:
        """Retrieve stored ontology for a graph."""

    # --- Add data ---

    @abstractmethod
    def add_text(self, graph_id: str, text: str) -> str:
        """
        Process text: NER/RE → create nodes/edges → return episode_id.
        This is synchronous (unlike Zep Cloud's async episodes).
        """

    @abstractmethod
    def add_text_batch(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[str]:
        """Batch-add text chunks. Returns list of episode_ids."""

    @abstractmethod
    def wait_for_processing(
        self,
        episode_ids: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        timeout: int = 600,
    ) -> None:
        """
        Wait for episodes to be processed.
        For Neo4j: no-op (synchronous processing).
        Kept for API compatibility with Zep-era callers.
        """

    # --- Read nodes ---

    @abstractmethod
    def get_all_nodes(self, graph_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
        """Get all nodes in a graph (with optional limit)."""

    @abstractmethod
    def get_node(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get a single node by UUID."""

    @abstractmethod
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """Get all edges connected to a node (O(1) via Cypher, not full scan)."""

    @abstractmethod
    def get_nodes_by_label(self, graph_id: str, label: str) -> List[Dict[str, Any]]:
        """Get nodes filtered by entity type label."""

    # --- Read edges ---

    @abstractmethod
    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """Get all edges in a graph."""

    # --- Search ---

    @abstractmethod
    def search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges",
        as_of: Optional[str] = None,
        include_invalidated: bool = False,
        kinds: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Hybrid search (vector + keyword) over graph data.

        Args:
            graph_id: Graph to search in
            query: Search query text
            limit: Max results
            scope: "edges", "nodes", or "both"

        Returns:
            Dict with 'edges' and/or 'nodes' lists (wrapped by GraphToolsService into SearchResult)
        """

    # --- Graph info ---

    @abstractmethod
    def get_graph_info(self, graph_id: str) -> Dict[str, Any]:
        """Get graph metadata (node count, edge count, entity types)."""

    @abstractmethod
    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        Get full graph data (enriched format for frontend).

        Returns dict with:
            graph_id, nodes, edges, node_count, edge_count
        Edge dicts include derived fields: fact_type, source_node_name, target_node_name
        """
