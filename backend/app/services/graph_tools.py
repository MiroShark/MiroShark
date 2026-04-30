"""Graph retrieval tools (search, node/edge queries) used by the Report Agent.

Core retrieval tools:
1. InsightForge — hybrid search that generates sub-questions and combines results
2. PanoramaSearch — broad view including expired content
3. QuickSearch — simple keyword retrieval
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient, create_llm_client, create_smart_llm_client
from ..storage import GraphStorage

logger = get_logger('miroshark.graph_tools')


@dataclass
class SearchResult:
    """Search Result"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }

    def to_text(self) -> str:
        """Convert to text format for LLM understanding"""
        text_parts = [f"Search Query: {self.query}", f"Found {self.total_count} related results"]

        if self.facts:
            text_parts.append("\n### Related Facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")

        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node Information"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }

    def to_text(self) -> str:
        """Convert to text format"""
        entity_type = next((la for la in self.labels if la not in ["Entity", "Node"]), "Unknown type")
        return f"Entity: {self.name} (Type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge Information"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # Temporal information (may be absent in Neo4j — kept for interface compat)
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }

    def to_text(self, include_temporal: bool = False) -> str:
        """Convert to text format"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relationship: {source} --[{self.name}]--> {target}\nFact: {self.fact}"

        if include_temporal:
            valid_at = self.valid_at or "Unknown"
            invalid_at = self.invalid_at or "Present"
            base_text += f"\nTime Range: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (Expired: {self.expired_at})"

        return base_text

    @property
    def is_expired(self) -> bool:
        """Whether already expired"""
        return self.expired_at is not None

    @property
    def is_invalid(self) -> bool:
        """Whether already invalid"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    Deep Insight Retrieval Result (InsightForge)
    Contains retrieval results from multiple sub-questions and integrated analysis
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]

    # Retrieval results by dimension
    semantic_facts: List[str] = field(default_factory=list)
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)
    relationship_chains: List[str] = field(default_factory=list)

    # Statistical information
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }

    def to_text(self) -> str:
        """Convert to detailed text format for LLM understanding"""
        text_parts = [
            f"## Future Prediction Deep Analysis",
            f"Analysis Query: {self.query}",
            f"Prediction Scenario: {self.simulation_requirement}",
            f"\n### Prediction Data Statistics",
            f"- Related Prediction Facts: {self.total_facts}",
            f"- Involved Entities: {self.total_entities}",
            f"- Relationship Chains: {self.total_relationships}"
        ]

        if self.sub_queries:
            text_parts.append(f"\n### Analysis Sub-Questions")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")

        if self.semantic_facts:
            text_parts.append(f"\n### Key Facts (Please quote these verbatim in the report)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        if self.entity_insights:
            text_parts.append(f"\n### Core Entities")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'Unknown')}** ({entity.get('type', 'Entity')})")
                if entity.get('summary'):
                    text_parts.append(f"  Summary: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  Related Facts: {len(entity.get('related_facts', []))} facts")

        if self.relationship_chains:
            text_parts.append(f"\n### Relationship Chains")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")

        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    Breadth Search Result (Panorama)
    Contains all related information, including expired content
    """
    query: str

    all_nodes: List[NodeInfo] = field(default_factory=list)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    active_facts: List[str] = field(default_factory=list)
    historical_facts: List[str] = field(default_factory=list)

    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }

    def to_text(self) -> str:
        """Convert to text format (complete version, no truncation)"""
        text_parts = [
            f"## Breadth Search Results (Future Panoramic View)",
            f"Query: {self.query}",
            f"\n### Statistics",
            f"- Total Nodes: {self.total_nodes}",
            f"- Total Edges: {self.total_edges}",
            f"- Current Valid Facts: {self.active_count}",
            f"- Historical/Expired Facts: {self.historical_count}"
        ]

        if self.active_facts:
            text_parts.append(f"\n### Current Valid Facts (Simulation Results Verbatim)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        if self.historical_facts:
            text_parts.append(f"\n### Historical/Expired Facts (Evolution Record)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f'{i}. "{fact}"')

        if self.all_nodes:
            text_parts.append(f"\n### Involved Entities")
            for node in self.all_nodes:
                entity_type = next((la for la in node.labels if la not in ["Entity", "Node"]), "Entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")

        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Single Agent Interview Result"""
    agent_name: str
    agent_role: str
    agent_bio: str
    question: str
    response: str
    key_quotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }

    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key Quotes:**\n"
            for quote in self.key_quotes:
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                while clean_quote and clean_quote[0] in '，,；;：:、。！？\n\r\t ':
                    clean_quote = clean_quote[1:]
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    Interview Result
    Contains interview responses from multiple simulated Agents
    """
    interview_topic: str
    interview_questions: List[str]

    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    interviews: List[AgentInterview] = field(default_factory=list)

    selection_reasoning: str = ""
    summary: str = ""

    total_agents: int = 0
    interviewed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }

    def to_text(self) -> str:
        """Convert to detailed text format for LLM understanding and report reference"""
        text_parts = [
            "## Deep Interview Report",
            f"**Interview Topic:** {self.interview_topic}",
            f"**Interviewees:** {self.interviewed_count} / {self.total_agents} Simulated Agents",
            "\n### Selection Rationale",
            self.selection_reasoning or "(Automatic Selection)",
            "\n---",
            "\n### Interview Transcripts",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(No interview records)\n\n---")

        text_parts.append("\n### Interview Summary & Key Insights")
        text_parts.append(self.summary or "(No summary)")

        return "\n".join(text_parts)


class GraphToolsService:
    """
    Graph Retrieval Tools Service (via GraphStorage / Neo4j)

    [Core Retrieval Tools - Optimized]
    1. insight_forge - Deep Insight Retrieval (Most powerful, auto-generates sub-questions, multi-dimensional retrieval)
    2. panorama_search - Breadth Search (Get comprehensive view, including expired content)
    3. quick_search - Simple Search (Quick retrieval)
    4. interview_agents - Deep Interview (Interview simulated Agents, obtain multi-perspective insights)

    [Basic Tools]
    - search_graph - Graph semantic search
    - get_all_nodes - Get all nodes in graph
    - get_all_edges - Get all edges in graph (with temporal information)
    - get_node_detail - Get detailed node information
    - get_node_edges - Get edges related to a node
    - get_entities_by_type - Get entities by type
    - get_entity_summary - Get entity relationship summary
    """

    def __init__(self, storage: GraphStorage, llm_client: Optional[LLMClient] = None):
        self.storage = storage
        self._llm_client = llm_client
        self._fast_llm_client = None
        logger.info("GraphToolsService initialization complete")

    @property
    def llm(self) -> LLMClient:
        """Lazy initialization of smart LLM client (for reasoning tasks)"""
        if self._llm_client is None:
            self._llm_client = create_smart_llm_client()
        return self._llm_client

    @property
    def fast_llm(self) -> LLMClient:
        """Lazy initialization of fast LLM client (for interviews, selection, questions)"""
        if self._fast_llm_client is None:
            self._fast_llm_client = create_llm_client()
        return self._fast_llm_client

    # ========== Basic Tools ==========

    def browse_clusters(
        self,
        graph_id: str,
        query: str = "",
        limit: int = 8,
    ) -> str:
        """
        "Zoom out" tool — return LLM-summarized community clusters over the graph.

        Behaviour:
          - If no communities exist yet, auto-builds them once (first call pays
            the ~5s Leiden+summarization cost; subsequent calls are fast).
          - With `query`: semantic search over cluster summaries.
          - Without `query`: lists the largest clusters in the graph.

        The goal is for the report agent to get its bearings before drilling
        into individual facts — one call surfaces the 5-8 themes the graph
        is actually about.
        """
        logger.info(f"browse_clusters: graph_id={graph_id}, query={query[:40]!r}, limit={limit}")

        existing = self.storage.list_communities(graph_id)
        if not existing:
            logger.info(f"No communities for {graph_id} — auto-building")
            try:
                stats = self.storage.build_communities(graph_id)
                logger.info(f"Auto-build stats: {stats}")
                existing = self.storage.list_communities(graph_id)
            except Exception as e:
                logger.warning(f"Community auto-build failed: {e}")
                return "⚠️ No community clusters available and auto-build failed. Skip this tool for now."

        if not existing:
            return (
                "No clusters could be formed — the graph is too sparse or has fewer "
                f"than {Config.COMMUNITY_MIN_SIZE} entities per potential cluster. "
                "Use search_graph or panorama_search instead."
            )

        # Query-guided mode: semantic search
        if query and query.strip():
            results = self.storage.search_communities(graph_id, query.strip(), limit=limit)
            if not results:
                return f"No clusters found matching {query!r}. Try a broader query or call without a query to list all clusters."
            return self._format_clusters(results, header=f"Top {len(results)} clusters relevant to {query!r}:")

        # Browse mode: return largest clusters
        top = existing[:limit]
        return self._format_clusters(top, header=f"Graph contains {len(existing)} clusters (showing top {len(top)} by size):")

    @staticmethod
    def _format_clusters(clusters: List[Dict[str, Any]], header: str = "") -> str:
        """Render a cluster list for the agent to read."""
        lines = []
        if header:
            lines.append(header)
            lines.append("")
        for i, c in enumerate(clusters, start=1):
            title = c.get("title", "") or "(untitled)"
            summary = (c.get("summary") or "").strip()
            member_count = c.get("member_count", 0)
            score_part = f" · relevance {c['score']:.2f}" if "score" in c else ""
            lines.append(f"{i}. {title}  [{member_count} entities{score_part}]")
            if summary:
                lines.append(f"   {summary}")
            lines.append(f"   uuid: {c.get('uuid', '')}")
            lines.append("")
        lines.append(
            "Tip: use search_graph or quick_search with a query focused on one "
            "of these cluster themes to drill into specific facts."
        )
        return "\n".join(lines)

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph semantic search (hybrid: vector + BM25 via Neo4j)

        Args:
            graph_id: Graph ID
            query: Search query
            limit: Number of results to return
            scope: Search scope, "edges" or "nodes" or "both"

        Returns:
            SearchResult
        """
        logger.info(f"Graph search: graph_id={graph_id}, query={query[:50]}...")

        try:
            search_results = self.storage.search(
                graph_id=graph_id,
                query=query,
                limit=limit,
                scope=scope,
            )

            facts = []
            edges = []
            nodes = []

            # Parse edge results
            if hasattr(search_results, 'edges'):
                edge_list = search_results.edges
            elif isinstance(search_results, dict) and 'edges' in search_results:
                edge_list = search_results['edges']
            else:
                edge_list = []

            for edge in edge_list:
                if isinstance(edge, dict):
                    fact = edge.get('fact', '')
                    if fact:
                        facts.append(fact)
                    edges.append({
                        "uuid": edge.get('uuid', ''),
                        "name": edge.get('name', ''),
                        "fact": fact,
                        "source_node_uuid": edge.get('source_node_uuid', ''),
                        "target_node_uuid": edge.get('target_node_uuid', ''),
                    })

            # Parse node results
            if hasattr(search_results, 'nodes'):
                node_list = search_results.nodes
            elif isinstance(search_results, dict) and 'nodes' in search_results:
                node_list = search_results['nodes']
            else:
                node_list = []

            for node in node_list:
                if isinstance(node, dict):
                    nodes.append({
                        "uuid": node.get('uuid', ''),
                        "name": node.get('name', ''),
                        "labels": node.get('labels', []),
                        "summary": node.get('summary', ''),
                    })
                    summary = node.get('summary', '')
                    if summary:
                        facts.append(f"[{node.get('name', '')}]: {summary}")

            logger.info(f"Search complete: Found {len(facts)} related facts")

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )

        except Exception as e:
            logger.warning(f"Graph search failed, degrading to local search: {str(e)}")
            return self._local_search(graph_id, query, limit, scope)

    def _local_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword matching search (fallback approach)
        """
        logger.info(f"Using local search: query={query[:30]}...")

        facts = []
        edges_result = []
        nodes_result = []

        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            if not text:
                return 0
            text_lower = text.lower()
            if query_lower in text_lower:
                return 100
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score

        try:
            if scope in ["edges", "both"]:
                all_edges = self.storage.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.get("fact", "")) + match_score(edge.get("name", ""))
                    if score > 0:
                        scored_edges.append((score, edge))

                scored_edges.sort(key=lambda x: x[0], reverse=True)

                for score, edge in scored_edges[:limit]:
                    fact = edge.get("fact", "")
                    if fact:
                        facts.append(fact)
                    edges_result.append({
                        "uuid": edge.get("uuid", ""),
                        "name": edge.get("name", ""),
                        "fact": fact,
                        "source_node_uuid": edge.get("source_node_uuid", ""),
                        "target_node_uuid": edge.get("target_node_uuid", ""),
                    })

            if scope in ["nodes", "both"]:
                all_nodes = self.storage.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.get("name", "")) + match_score(node.get("summary", ""))
                    if score > 0:
                        scored_nodes.append((score, node))

                scored_nodes.sort(key=lambda x: x[0], reverse=True)

                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.get("uuid", ""),
                        "name": node.get("name", ""),
                        "labels": node.get("labels", []),
                        "summary": node.get("summary", ""),
                    })
                    summary = node.get("summary", "")
                    if summary:
                        facts.append(f"[{node.get('name', '')}]: {summary}")

            logger.info(f"Local search complete: Found {len(facts)} related facts")

        except Exception as e:
            logger.error(f"Local search failed: {str(e)}")

        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """Get all nodes in the graph"""
        logger.info(f"Getting all nodes in graph {graph_id}...")

        raw_nodes = self.storage.get_all_nodes(graph_id)

        result = []
        for node in raw_nodes:
            result.append(NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {})
            ))

        logger.info(f"Retrieved {len(result)} nodes")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """Get all edges in the graph (with temporal information)"""
        logger.info(f"Getting all edges in graph {graph_id}...")

        raw_edges = self.storage.get_all_edges(graph_id)

        result = []
        for edge in raw_edges:
            edge_info = EdgeInfo(
                uuid=edge.get("uuid", ""),
                name=edge.get("name", ""),
                fact=edge.get("fact", ""),
                source_node_uuid=edge.get("source_node_uuid", ""),
                target_node_uuid=edge.get("target_node_uuid", "")
            )

            if include_temporal:
                edge_info.created_at = edge.get("created_at")
                edge_info.valid_at = edge.get("valid_at")
                edge_info.invalid_at = edge.get("invalid_at")
                edge_info.expired_at = edge.get("expired_at")

            result.append(edge_info)

        logger.info(f"Retrieved {len(result)} edges")
        return result

    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """Get detailed information about a single node"""
        logger.info(f"Getting node details: {node_uuid[:8]}...")

        try:
            node = self.storage.get_node(node_uuid)
            if not node:
                return None

            return NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {})
            )
        except Exception as e:
            logger.error(f"Failed to get node details: {str(e)}")
            return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Get all edges related to a node

        Optimized: uses storage.get_node_edges() (O(degree) Cypher)
        instead of loading ALL edges and filtering.
        """
        logger.info(f"Getting edges related to node {node_uuid[:8]}...")

        try:
            raw_edges = self.storage.get_node_edges(node_uuid)

            result = []
            for edge in raw_edges:
                result.append(EdgeInfo(
                    uuid=edge.get("uuid", ""),
                    name=edge.get("name", ""),
                    fact=edge.get("fact", ""),
                    source_node_uuid=edge.get("source_node_uuid", ""),
                    target_node_uuid=edge.get("target_node_uuid", ""),
                    created_at=edge.get("created_at"),
                    valid_at=edge.get("valid_at"),
                    invalid_at=edge.get("invalid_at"),
                    expired_at=edge.get("expired_at"),
                ))

            logger.info(f"Found {len(result)} edges related to the node")
            return result

        except Exception as e:
            logger.warning(f"Failed to get node edges: {str(e)}")
            return []

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str
    ) -> List[NodeInfo]:
        """Get entities by type"""
        logger.info(f"Getting entities of type {entity_type}...")

        # Use optimized label-based query from storage
        raw_nodes = self.storage.get_nodes_by_label(graph_id, entity_type)

        result = []
        for node in raw_nodes:
            result.append(NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=node.get("labels", []),
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {})
            ))

        logger.info(f"Found {len(result)} entities of type {entity_type}")
        return result

    def get_entity_summary(
        self,
        graph_id: str,
        entity_name: str
    ) -> Dict[str, Any]:
        """Get relationship summary for a specific entity"""
        logger.info(f"Getting relationship summary for entity {entity_name}...")

        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )

        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break

        related_edges = []
        if entity_node:
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)

        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """Get statistics for the graph"""
        logger.info(f"Getting statistics for graph {graph_id}...")

        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)

        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1

        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1

        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }

    def get_simulation_context(
        self,
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """Get simulation-related context information"""
        logger.info(f"Getting simulation context: {simulation_requirement[:50]}...")

        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )

        stats = self.get_graph_statistics(graph_id)

        all_nodes = self.get_all_nodes(graph_id)

        entities = []
        for node in all_nodes:
            custom_labels = [la for la in node.labels if la not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })

        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],
            "total_entities": len(entities)
        }

    # ========== Core Retrieval Tools (Optimized) ==========

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        [InsightForge - Deep Insight Retrieval]

        The most powerful hybrid retrieval function, automatically decomposes problems and performs multi-dimensional retrieval:
        1. Use LLM to decompose the problem into multiple sub-questions
        2. Perform semantic search on each sub-question
        3. Extract related entities and get their detailed information
        4. Trace relationship chains
        5. Integrate all results and generate deep insights
        """
        logger.info(f"InsightForge deep insight retrieval: {query[:50]}...")

        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )

        # Step 1: Use LLM to generate sub-questions
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"Generated {len(sub_queries)} sub-questions")

        # Step 2: Perform semantic search on each sub-question
        all_facts = []
        all_edges = []
        seen_facts = set()

        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )

            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)

            all_edges.extend(search_result.edges)

        # Also search for the original question
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        # Step 3: Extract related entity UUIDs from edges
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)

        # Get related entity details
        entity_insights = []
        node_map = {}

        for uuid in list(entity_uuids):
            if not uuid:
                continue
            try:
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((la for la in node.labels if la not in ["Entity", "Node"]), "Entity")

                    related_facts = [
                        f for f in all_facts
                        if node.name.lower() in f.lower()
                    ]

                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts
                    })
            except Exception as e:
                logger.debug(f"Failed to get node {uuid}: {e}")
                continue

        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)

        # Step 4: Build relationship chains
        relationship_chains = []
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')

                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]

                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)

        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)

        logger.info(f"InsightForge complete: {result.total_facts} facts, {result.total_entities} entities, {result.total_relationships} relationships")
        return result

    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """Use LLM to generate sub-questions"""
        from ..prompts import get_prompt
        from ..utils.i18n import get_active_locale
        locale = get_active_locale()

        system_prompt = get_prompt("graph_tools.subquery_system", locale)

        report_context_block = ""
        if report_context:
            report_context_block = get_prompt(
                "graph_tools.subquery_user_report_context",
                locale,
                report_context=report_context[:500],
            )

        user_prompt = get_prompt(
            "graph_tools.subquery_user",
            locale,
            simulation_requirement=simulation_requirement,
            report_context_block=report_context_block,
            max_queries=max_queries,
            query=query,
        )

        try:
            response = self.fast_llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            sub_queries = response.get("sub_queries", [])
            return [str(sq) for sq in sub_queries[:max_queries]]

        except Exception as e:
            logger.warning(f"Failed to generate sub-questions: {str(e)}, using default sub-questions")
            return [
                query,
                f"Main participants in {query}",
                f"Causes and impacts of {query}",
                f"Development process of {query}"
            ][:max_queries]

    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        [PanoramaSearch - Breadth Search]

        Get a comprehensive panoramic view, including all related content and historical/expired information.
        """
        logger.info(f"PanoramaSearch breadth search: {query[:50]}...")

        result = PanoramaResult(query=query)

        # Get all nodes
        all_nodes = self.get_all_nodes(graph_id)
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)

        # Get all edges (including temporal information)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)

        # Categorize facts
        active_facts = []
        historical_facts = []

        for edge in all_edges:
            if not edge.fact:
                continue

            is_historical = edge.is_expired or edge.is_invalid

            if is_historical:
                valid_at = edge.valid_at or "Unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "Unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                active_facts.append(edge.fact)

        # Sort by relevance based on query
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score

        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)

        logger.info(f"PanoramaSearch complete: {result.active_count} valid, {result.historical_count} historical")
        return result

    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        [QuickSearch - Simple Search]
        Fast and lightweight retrieval tool.
        """
        logger.info(f"QuickSearch simple search: {query[:50]}...")

        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )

        logger.info(f"QuickSearch complete: {result.total_count} results")
        return result

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 8,
        custom_questions: List[str] = None,
        agent_names: List[str] = None,
        dual_platform: bool = False,
    ) -> InterviewResult:
        """
        [InterviewAgents - Deep Interview]

        Call the real Wonderwall interview API to interview Agents running in the simulation.
        This method does NOT use GraphStorage — it calls SimulationRunner
        and reads agent profiles from disk.

        Args:
            agent_names: If provided, skip LLM-based selection and use these agents directly.
            dual_platform: If True, interview on both platforms. If False (default),
                           interview on the platform where each agent was most active.
        """
        from .simulation_runner import SimulationRunner

        logger.info(f"InterviewAgents deep interview (real API): {interview_requirement[:50]}...")

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )

        # Step 1: Read agent profile files
        profiles = self._load_agent_profiles(simulation_id)

        if not profiles:
            logger.warning(f"No profile files found for simulation {simulation_id}")
            result.summary = "No Agent profile files found for interview"
            return result

        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)} Agent profiles")

        # Step 2: Select agents — skip LLM selection if specific names are provided
        if agent_names:
            selected_agents, selected_indices, selection_reasoning = self._select_agents_by_name(
                profiles=profiles,
                agent_names=agent_names,
                max_agents=max_agents,
            )
        else:
            selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
                profiles=profiles,
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                max_agents=max_agents
            )

        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selected {len(selected_agents)} Agents for interview: {selected_indices}")

        # Step 3: Generate interview questions
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")

        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])

        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Please combine your character profile, all past memories and actions, "
            "and directly answer the following questions in plain text.\n"
            "Response requirements:\n"
            "1. Answer directly in natural language, do not call any tools\n"
            "2. Do not return JSON format or tool call format\n"
            "3. Do not use Markdown headings (e.g., #, ##, ###)\n"
            "4. Answer the questions in order, with each answer starting with 'Question X:' (X is the question number)\n"
            "5. Separate each answer with a blank line\n"
            "6. Provide substantive answers, at least 2-3 sentences per question\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"

        # Step 3.5: Determine platform for each agent (single-platform by default)
        if not dual_platform:
            agent_platforms = self._determine_agent_platforms(simulation_id, selected_indices)
            interview_platform = agent_platforms.get("dominant_platform", "twitter")
            logger.info(f"Single-platform interview mode: using '{interview_platform}' (most active platform)")
        else:
            interview_platform = None  # None means dual-platform in the batch API
            logger.info("Dual-platform interview mode (explicitly requested)")

        # Step 4: Call the real interview API (only if env is alive)
        try:
            # Check run state first — skip IPC entirely if simulation is completed/stopped
            run_state = SimulationRunner.get_run_state(simulation_id)
            if run_state and run_state.runner_status.value in ("completed", "stopped", "failed"):
                logger.info(f"Simulation {simulation_id} is {run_state.runner_status.value}, using LLM-based interview directly")
                raise ValueError("Simulation completed, skipping IPC")

            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt
                })

            platform_label = "dual platform" if dual_platform else f"single platform ({interview_platform})"
            logger.info(f"Calling batch interview API ({platform_label}): {len(interviews_request)} Agents")

            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=interview_platform,
                timeout=180.0
            )

            logger.info(f"Interview API returned: {api_result.get('interviews_count', 0)} results, success={api_result.get('success')}")

            if not api_result.get("success", False):
                error_msg = api_result.get("error", "Unknown error")
                logger.info(f"Interview API returned error: {error_msg}, using LLM-based interview")
                return self._fallback_interview(
                    result=result,
                    selected_agents=selected_agents,
                    selected_indices=selected_indices,
                    combined_prompt=combined_prompt,
                    interview_requirement=interview_requirement,
                )

            # Step 5: Parse API response
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}

            import re

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "Unknown")
                agent_bio = agent.get("bio", "")

                if dual_platform:
                    # Dual-platform: collect from both
                    twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                    reddit_result = results_dict.get(f"reddit_{agent_idx}", {})

                    twitter_response = self._clean_tool_call_response(twitter_result.get("response", ""))
                    reddit_response = self._clean_tool_call_response(reddit_result.get("response", ""))

                    twitter_text = twitter_response if twitter_response else "(No response from this platform)"
                    reddit_text = reddit_response if reddit_response else "(No response from this platform)"
                    response_text = f"[Twitter Platform Response]\n{twitter_text}\n\n[Reddit Platform Response]\n{reddit_text}"
                    combined_responses = f"{twitter_response} {reddit_response}"
                else:
                    # Single-platform: only use the selected platform
                    platform_result = results_dict.get(f"{interview_platform}_{agent_idx}", {})
                    platform_response = self._clean_tool_call_response(platform_result.get("response", ""))
                    platform_text = platform_response if platform_response else "(No response from this platform)"
                    response_text = f"[{interview_platform.capitalize()} Platform Response]\n{platform_text}"
                    combined_responses = platform_response

                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'Question\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', 'Question'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]

                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)

            result.interviewed_count = len(result.interviews)

        except (ValueError, Exception) as e:
            logger.info(f"Simulation process not running, using LLM-based interview (reason: {e})")
            return self._fallback_interview(
                result=result,
                selected_agents=selected_agents,
                selected_indices=selected_indices,
                combined_prompt=combined_prompt,
                interview_requirement=interview_requirement,
            )

        # Step 6: Generate interview summary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )

        platform_label = "dual platform" if dual_platform else f"single platform ({interview_platform})"
        logger.info(f"InterviewAgents complete: Interviewed {result.interviewed_count} Agents ({platform_label})")
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Clean JSON tool call wrappers in Agent responses and extract actual content"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _interview_single_agent_llm(
        self,
        agent: Dict[str, Any],
        agent_idx: int,
        combined_prompt: str,
    ) -> 'AgentInterview':
        """
        Interview a single agent via LLM. Designed to be called in parallel
        from a ThreadPoolExecutor.
        """
        import re

        agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
        agent_role = agent.get("profession", "Unknown")
        agent_bio = agent.get("bio", "")
        agent_persona = agent.get("persona", "")

        profile_desc = f"Name: {agent_name}\nRole: {agent_role}"
        if agent_bio:
            profile_desc += f"\nBio: {agent_bio[:500]}"
        if agent_persona:
            profile_desc += f"\nPersona: {agent_persona[:500]}"

        prompt = (
            f"You are role-playing as the following character in a simulation:\n\n"
            f"{profile_desc}\n\n"
            f"Stay fully in character. Answer the following interview questions based on "
            f"your profile, beliefs, and perspective. Be specific and substantive.\n\n"
            f"{combined_prompt}"
        )

        try:
            response_text = self.fast_llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1024,
            )
            if not response_text:
                response_text = "(No response generated)"
        except Exception as e:
            logger.warning(f"Fallback interview failed for {agent_name}: {e}")
            response_text = f"(Interview generation failed: {e})"

        # Extract key quotes
        clean_text = re.sub(r'#{1,6}\s+', '', response_text)
        clean_text = re.sub(r'Question\s*\d+[：:]\s*', '', clean_text)
        sentences = re.split(r'[.。！？!?]', clean_text)
        meaningful = [
            s.strip() for s in sentences
            if 20 <= len(s.strip()) <= 150
        ]
        meaningful.sort(key=len, reverse=True)
        key_quotes = [s + "." for s in meaningful[:3]]

        return AgentInterview(
            agent_name=agent_name,
            agent_role=agent_role,
            agent_bio=agent_bio[:1000],
            question=combined_prompt,
            response=f"[LLM-based Interview]\n{response_text}",
            key_quotes=key_quotes[:5]
        )

    def _fallback_interview(
        self,
        result: 'InterviewResult',
        selected_agents: List[Dict[str, Any]],
        selected_indices: List[int],
        combined_prompt: str,
        interview_requirement: str,
    ) -> 'InterviewResult':
        """
        Fallback: generate interviews using the LLM directly from agent profiles
        when the real Wonderwall interview API is unavailable or fails.

        Uses ThreadPoolExecutor to run LLM calls concurrently instead of serially.
        """
        logger.info(f"Running LLM-based fallback interview for {len(selected_agents)} agents (parallel)")

        # Run all agent interviews concurrently via thread pool
        max_workers = min(len(selected_agents), 4)  # Cap concurrency to avoid API rate limits
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {}
            for i, agent_idx in enumerate(selected_indices):
                future = executor.submit(
                    self._interview_single_agent_llm,
                    agent=selected_agents[i],
                    agent_idx=agent_idx,
                    combined_prompt=combined_prompt,
                )
                future_to_idx[future] = i  # preserve original order

            # Collect results, maintaining insertion order
            interviews_by_order: Dict[int, AgentInterview] = {}
            for future in as_completed(future_to_idx):
                order_idx = future_to_idx[future]
                try:
                    interviews_by_order[order_idx] = future.result()
                except Exception as e:
                    agent = selected_agents[order_idx]
                    agent_name = agent.get("realname", agent.get("username", f"Agent_{selected_indices[order_idx]}"))
                    logger.warning(f"Parallel interview thread failed for {agent_name}: {e}")
                    interviews_by_order[order_idx] = AgentInterview(
                        agent_name=agent_name,
                        agent_role=agent.get("profession", "Unknown"),
                        agent_bio=agent.get("bio", "")[:1000],
                        question=combined_prompt,
                        response=f"[LLM-based Interview]\n(Interview generation failed: {e})",
                        key_quotes=[]
                    )

        # Append in original order
        for i in sorted(interviews_by_order.keys()):
            result.interviews.append(interviews_by_order[i])

        result.interviewed_count = len(result.interviews)

        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )

        logger.info(f"Fallback interview complete: {result.interviewed_count} agents (parallel)")
        return result

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load Agent profile files for simulation"""
        import os
        import csv

        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        profiles = []

        # Preferentially try to read Reddit JSON format
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"Loaded {len(profiles)} profiles from reddit_profiles.json")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        # Try to read Twitter CSV format
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "Unknown"
                        })
                logger.info(f"Loaded {len(profiles)} profiles from twitter_profiles.csv")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        return profiles

    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """Use LLM to select Agents for interview"""

        agent_summaries = []
        for i, profile in enumerate(profiles):
            name = profile.get("realname", profile.get("username", f"Agent_{i}"))
            profession = profile.get("profession", "Unknown")
            topics = profile.get("interested_topics", [])
            topics_str = f" [{', '.join(topics)}]" if topics else ""
            agent_summaries.append(f"{i}: {name} — {profession}{topics_str}")

        from ..prompts import get_prompt
        from ..utils.i18n import get_active_locale
        locale = get_active_locale()

        system_prompt = get_prompt("graph_tools.interview_select_system", locale)

        agents_list = "\n".join(agent_summaries)
        background = (
            simulation_requirement
            if simulation_requirement
            else get_prompt("graph_tools.interview_select_no_background", locale)
        )
        user_prompt = get_prompt(
            "graph_tools.interview_select_user",
            locale,
            interview_requirement=interview_requirement,
            simulation_background=background,
            total=len(agent_summaries),
            agents_list=agents_list,
            max_agents=max_agents,
        )

        try:
            response = self.fast_llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get(
                "reasoning",
                get_prompt("graph_tools.interview_select_default_reasoning", locale),
            )

            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)

            return selected_agents, valid_indices, reasoning

        except Exception as e:
            logger.warning(f"LLM agent selection failed, using default selection: {e}")
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, get_prompt(
                "graph_tools.interview_select_default_strategy", locale,
            )

    def _select_agents_by_name(
        self,
        profiles: List[Dict[str, Any]],
        agent_names: List[str],
        max_agents: int,
    ) -> tuple:
        """
        Select agents by name without an LLM call.
        Matches against realname and username fields (case-insensitive, substring match).
        Falls back to LLM selection if no names match.
        """
        selected_agents = []
        selected_indices = []
        names_lower = [n.lower() for n in agent_names]

        for i, profile in enumerate(profiles):
            if len(selected_agents) >= max_agents:
                break
            realname = (profile.get("realname") or "").lower()
            username = (profile.get("username") or "").lower()
            for name_query in names_lower:
                if name_query in realname or name_query in username:
                    selected_agents.append(profile)
                    selected_indices.append(i)
                    break

        if selected_agents:
            matched_names = [a.get("realname", a.get("username", "?")) for a in selected_agents]
            reasoning = f"Directly selected by name: {', '.join(matched_names)}"
            logger.info(f"Agent name match: {len(selected_agents)} of {len(agent_names)} requested names found")
            return selected_agents, selected_indices, reasoning

        logger.warning(f"No agents matched requested names {agent_names}, falling back to default selection")
        selected = profiles[:max_agents]
        indices = list(range(min(max_agents, len(profiles))))
        return selected, indices, f"Requested names not found ({agent_names}), using default selection"

    def _determine_agent_platforms(
        self,
        simulation_id: str,
        agent_indices: List[int],
    ) -> Dict[str, Any]:
        """
        Determine which platform each agent was most active on by counting
        actions in twitter/actions.jsonl and reddit/actions.jsonl.

        Returns a dict with:
            - per_agent: {agent_idx: "twitter"|"reddit"}
            - dominant_platform: the platform with more total actions across selected agents
        """
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )

        agent_set = set(agent_indices)
        twitter_counts: Dict[int, int] = {idx: 0 for idx in agent_indices}
        reddit_counts: Dict[int, int] = {idx: 0 for idx in agent_indices}

        for platform_name, counts in [("twitter", twitter_counts), ("reddit", reddit_counts)]:
            actions_path = os.path.join(sim_dir, platform_name, "actions.jsonl")
            if not os.path.exists(actions_path):
                continue
            try:
                with open(actions_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            aid = entry.get("agent_id")
                            if aid is not None and aid in agent_set and entry.get("action_type"):
                                counts[aid] = counts.get(aid, 0) + 1
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception as e:
                logger.warning(f"Failed to read {platform_name} actions for platform detection: {e}")

        per_agent: Dict[int, str] = {}
        total_twitter = 0
        total_reddit = 0
        for idx in agent_indices:
            tc = twitter_counts.get(idx, 0)
            rc = reddit_counts.get(idx, 0)
            total_twitter += tc
            total_reddit += rc
            per_agent[idx] = "twitter" if tc >= rc else "reddit"

        dominant = "twitter" if total_twitter >= total_reddit else "reddit"
        logger.info(f"Platform activity: twitter={total_twitter}, reddit={total_reddit}, dominant={dominant}")

        return {
            "per_agent": per_agent,
            "dominant_platform": dominant,
        }

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """Use LLM to generate interview questions"""

        from ..prompts import get_prompt
        from ..utils.i18n import get_active_locale
        locale = get_active_locale()
        agent_roles = [a.get("profession", "Unknown") for a in selected_agents]

        system_prompt = get_prompt("graph_tools.interview_questions_system", locale)
        background = (
            simulation_requirement
            if simulation_requirement
            else get_prompt("graph_tools.interview_select_no_background", locale)
        )
        user_prompt = get_prompt(
            "graph_tools.interview_questions_user",
            locale,
            interview_requirement=interview_requirement,
            simulation_background=background,
            agent_roles=', '.join(agent_roles),
        )

        default_q = get_prompt(
            "graph_tools.interview_questions_default_perspective",
            locale,
            topic=interview_requirement,
        )
        try:
            response = self.fast_llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )

            return response.get("questions", [default_q])

        except Exception as e:
            logger.warning(f"Failed to generate interview questions: {e}")
            return [
                default_q,
                get_prompt("graph_tools.interview_questions_default_impact", locale),
                get_prompt("graph_tools.interview_questions_default_solution", locale),
            ]

    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generate interview summary"""

        from ..prompts import get_prompt
        from ..utils.i18n import get_active_locale
        locale = get_active_locale()

        if not interviews:
            return get_prompt("graph_tools.interview_summary_no_interviews", locale)

        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name} ({interview.agent_role})]\n{interview.response[:500]}")

        system_prompt = get_prompt("graph_tools.interview_summary_system", locale)
        user_prompt = get_prompt(
            "graph_tools.interview_summary_user",
            locale,
            interview_requirement=interview_requirement,
            interview_content="".join(interview_texts),
        )

        try:
            summary = self.fast_llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary

        except Exception as e:
            logger.warning(f"Failed to generate interview summary: {e}")
            return get_prompt(
                "graph_tools.interview_summary_fallback",
                locale,
                count=len(interviews),
                names=", ".join([i.agent_name for i in interviews]),
            )

    # ================================================================
    # Graph Reasoning Tools (structural analysis, not just retrieval)
    # ================================================================

    def analyze_graph_structure(self, graph_id: str, query: str = "") -> str:
        """
        [Graph Structure Analysis]

        Runs degree centrality, community detection, and bridge entity identification.
        Returns a structured analysis of the graph's topology — who is central,
        what clusters exist, and which entities connect disparate groups.
        """
        logger.info(f"Analyzing graph structure for {graph_id}")

        lines = ["=== Graph Structure Analysis ===", ""]

        # 1. Degree centrality
        try:
            top_entities = self.storage.get_degree_centrality(graph_id, limit=15)
            if top_entities:
                lines.append("**Most Connected Entities (Degree Centrality):**")
                for i, entity in enumerate(top_entities[:10], 1):
                    types_str = ", ".join(entity.get("types", []))
                    lines.append(
                        f"  {i}. {entity['name']} ({types_str}) — {entity['degree']} connections"
                    )
                    if entity.get("summary"):
                        lines.append(f"     {entity['summary'][:120]}")
                lines.append("")
        except Exception as e:
            logger.warning(f"Centrality query failed: {e}")
            lines.append("(Centrality analysis unavailable)")
            lines.append("")

        # 2. Community detection
        try:
            communities = self.storage.get_entity_communities(graph_id)
            if communities:
                lines.append(f"**Communities Detected: {len(communities)}**")
                for i, community in enumerate(communities[:5], 1):
                    names = [n["name"] for n in community[:8]]
                    types = set()
                    for n in community:
                        types.update(n.get("types", []))
                    names_str = ", ".join(names)
                    if len(community) > 8:
                        names_str += f", ... (+{len(community) - 8} more)"
                    lines.append(
                        f"  Cluster {i} ({len(community)} entities, types: {', '.join(types)}):"
                    )
                    lines.append(f"    {names_str}")
                lines.append("")

                # Identify isolated vs interconnected structure
                if len(communities) == 1:
                    lines.append("  → All entities form ONE connected component (densely interconnected)")
                elif len(communities) <= 3:
                    lines.append(f"  → {len(communities)} distinct clusters — look for bridge entities that connect them")
                else:
                    lines.append(f"  → {len(communities)} clusters — fragmented graph, possible information silos")
                lines.append("")
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")
            lines.append("(Community detection unavailable)")
            lines.append("")

        # 3. Bridge entities
        try:
            bridges = self.storage.get_bridge_entities(graph_id, limit=5)
            if bridges:
                lines.append("**Bridge Entities (Connectors Between Clusters):**")
                for entity in bridges:
                    types_str = ", ".join(entity.get("types", []))
                    lines.append(
                        f"  - {entity['name']} ({types_str}) — "
                        f"{entity['degree']} connections, bridge score: {entity.get('bridge_score', 'N/A')}"
                    )
                lines.append("  → These entities control information flow between groups")
                lines.append("")
        except Exception as e:
            logger.debug(f"Bridge entity query failed: {e}")

        return "\n".join(lines)

    def find_causal_path(self, graph_id: str, source: str, target: str, max_hops: int = 6) -> str:
        """
        [Causal Path Finder]

        Traces the shortest relationship path between two entities.
        Each step is annotated with the edge fact, revealing the causal chain.
        """
        logger.info(f"Finding path: {source} → {target}")

        try:
            steps = self.storage.get_shortest_path(graph_id, source, target, max_hops=max_hops)
        except Exception as e:
            return f"Path search failed: {str(e)}"

        if not steps:
            return f"No path found between '{source}' and '{target}' within {max_hops} hops."

        lines = [f"=== Causal Path: {source} → {target} ({len(steps)} steps) ===", ""]

        for i, step in enumerate(steps, 1):
            fact = step.get("fact", "")
            relation = step.get("relation", "related to")
            lines.append(
                f"  Step {i}: {step['source']} --[{relation}]--> {step['target']}"
            )
            if fact:
                lines.append(f"    Fact: \"{fact}\"")
        lines.append("")
        lines.append("This path shows how these two entities are connected through the knowledge graph.")

        return "\n".join(lines)

    def detect_contradictions(self, graph_id: str) -> str:
        """
        [Contradiction Detector]

        Finds entity pairs connected by edges with opposing sentiments.
        Contradictions reveal tension points, evolving relationships, or conflicting perspectives.
        """
        logger.info(f"Detecting contradictions in graph {graph_id}")

        try:
            contradictions = self.storage.detect_contradictions(graph_id, limit=15)
        except Exception as e:
            return f"Contradiction detection failed: {str(e)}"

        if not contradictions:
            return "No clear contradictions detected in the graph. All relationships appear internally consistent."

        lines = [f"=== Contradictions Detected: {len(contradictions)} ===", ""]

        for i, c in enumerate(contradictions[:10], 1):
            lines.append(
                f"**{i}. {c['source_name']} ↔ {c['target_name']}** "
                f"({c['contradiction_type']})"
            )
            for j, edge in enumerate(c["edges"]):
                sentiment = c["sentiments"][j] if j < len(c["sentiments"]) else "?"
                fact = edge.get("fact", "")
                lines.append(f"  [{sentiment.upper()}] \"{fact[:200]}\"")
            lines.append("")

        lines.append(
            "These contradictions may indicate: evolving relationships, "
            "conflicting perspectives from different sources, or temporal shifts in stance."
        )

        return "\n".join(lines)
