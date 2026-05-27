"""
Neo4jStorage — Neo4j Community Edition implementation of GraphStorage.

Replaces all Zep Cloud API calls with local Neo4j Cypher queries.
Includes: CRUD, NER/RE-based text ingestion, hybrid search, retry logic.
"""

import json
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

from neo4j import GraphDatabase
from neo4j.exceptions import (
    TransientError,
    ServiceUnavailable,
    SessionExpired,
)

from ..config import Config
from .graph_storage import GraphStorage
from .community_builder import CommunityBuilder
from .contradiction_detector import ContradictionDetector
from .embedding_service import EmbeddingService
from .entity_resolver import EntityResolver
from .ner_extractor import NERExtractor
from .search_service import SearchService
from . import neo4j_schema

logger = logging.getLogger('miroshark.neo4j_storage')


class Neo4jStorage(GraphStorage):
    """Neo4j CE implementation of the GraphStorage interface."""

    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 1  # seconds

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None,
        ner_extractor: Optional[NERExtractor] = None,
    ):
        self._uri = uri or Config.NEO4J_URI
        self._user = user or Config.NEO4J_USER
        self._password = password or Config.NEO4J_PASSWORD

        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        self._embedding = embedding_service or EmbeddingService()
        self._ner = ner_extractor or NERExtractor()
        self._search = SearchService(self._embedding)
        self._resolver = EntityResolver()
        self._contradiction = ContradictionDetector()
        self._community = CommunityBuilder(self._driver, self._embedding)

        # Initialize schema (indexes, constraints)
        self._ensure_schema()

    def close(self):
        """Close the Neo4j driver connection."""
        self._driver.close()

    def _ensure_schema(self):
        """Create indexes and constraints if they don't exist."""
        with self._driver.session() as session:
            for query in neo4j_schema.get_all_schema_queries():
                try:
                    session.run(query)
                except Exception as e:
                    logger.warning(f"Schema query warning (may already exist): {e}")

    # ----------------------------------------------------------------
    # Retry wrapper
    # ----------------------------------------------------------------

    def _call_with_retry(self, func, *args, **kwargs):
        """
        Execute a function with retry on Neo4j transient errors.
        Replaces 3 different retry patterns from the Zep codebase.
        """
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (TransientError, ServiceUnavailable, SessionExpired) as e:
                last_error = e
                wait = self.RETRY_DELAY_BASE * (2 ** attempt)
                logger.warning(
                    f"Neo4j transient error (attempt {attempt + 1}/{self.MAX_RETRIES}), "
                    f"retrying in {wait}s: {e}"
                )
                time.sleep(wait)

        raise last_error  # type: ignore

    # ----------------------------------------------------------------
    # Graph lifecycle
    # ----------------------------------------------------------------

    def create_graph(self, name: str, description: str = "") -> str:
        graph_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        def _create(tx):
            tx.run(
                """
                CREATE (g:Graph {
                    graph_id: $graph_id,
                    name: $name,
                    description: $description,
                    ontology_json: '{}',
                    created_at: $created_at
                })
                """,
                graph_id=graph_id,
                name=name,
                description=description,
                created_at=now,
            )

        with self._driver.session() as session:
            self._call_with_retry(session.execute_write, _create)

        logger.info(f"Created graph '{name}' with id {graph_id}")
        return graph_id

    def delete_graph(self, graph_id: str) -> None:
        def _delete(tx):
            # Delete all entities and their relationships
            tx.run(
                "MATCH (n {graph_id: $gid}) DETACH DELETE n",
                gid=graph_id,
            )
            # Delete graph node
            tx.run(
                "MATCH (g:Graph {graph_id: $gid}) DELETE g",
                gid=graph_id,
            )

        with self._driver.session() as session:
            self._call_with_retry(session.execute_write, _delete)
        logger.info(f"Deleted graph {graph_id}")

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        def _set(tx):
            tx.run(
                """
                MATCH (g:Graph {graph_id: $gid})
                SET g.ontology_json = $ontology_json
                """,
                gid=graph_id,
                ontology_json=json.dumps(ontology, ensure_ascii=False),
            )

        with self._driver.session() as session:
            self._call_with_retry(session.execute_write, _set)

    def get_ontology(self, graph_id: str) -> Dict[str, Any]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (g:Graph {graph_id: $gid}) RETURN g.ontology_json AS oj",
                gid=graph_id,
            )
            record = result.single()
            if record and record["oj"]:
                return json.loads(record["oj"])
            return {}

    # ----------------------------------------------------------------
    # Add data (NER → nodes/edges)
    # ----------------------------------------------------------------

    def add_text(
        self,
        graph_id: str,
        text: str,
        valid_at: Optional[str] = None,
        kind: str = "fact",
        source_type: str = "document",
        source_id: Optional[str] = None,
    ) -> str:
        """
        Process text: NER/RE → batch embed → create nodes/edges → return episode_id.

        Args:
            valid_at: ISO-8601 timestamp of when the extracted facts became true
                in the world. Defaults to ingestion time (`now`).
            kind: epistemic label on the produced edges. One of:
                "fact" (ground-truth world fact, default)
                "belief" (subjective opinion held by an agent)
                "observation" (what an agent perceived)
            source_type: where the edges came from — "document" (default),
                "agent", or "simulation".
            source_id: optional identifier for the source (agent UUID, episode
                UUID, etc.). Defaults to the episode UUID.
        """
        if kind not in ("fact", "belief", "observation"):
            raise ValueError(f"kind must be fact|belief|observation, got {kind!r}")

        episode_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Get ontology for NER guidance
        ontology = self.get_ontology(graph_id)

        # Extract entities and relations
        logger.info(f"[add_text] Starting NER extraction for chunk ({len(text)} chars)...")
        extraction = self._ner.extract(text, ontology)
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])

        logger.info(
            f"[add_text] NER done: {len(entities)} entities, {len(relations)} relations"
        )

        # --- Batch embed all texts at once ---
        # Build summaries: prefer NER-extracted summary from attributes, fall back to Name (Type)
        entity_summaries = []
        for e in entities:
            attrs = e.get("attributes", {})
            summary = attrs.pop("summary", None) or attrs.get("description", None)
            if summary and len(str(summary)) > 10:
                entity_summaries.append(str(summary))
            else:
                entity_summaries.append(f"{e['name']} ({e['type']})")
        fact_texts = [r.get("fact", f"{r['source']} {r['type']} {r['target']}") for r in relations]
        all_texts_to_embed = entity_summaries + fact_texts

        all_embeddings: list = []
        if all_texts_to_embed:
            logger.info(f"[add_text] Batch-embedding {len(all_texts_to_embed)} texts...")
            try:
                all_embeddings = self._embedding.embed_batch(all_texts_to_embed)
            except Exception as e:
                logger.warning(f"[add_text] Batch embedding failed, falling back to empty: {e}")
                all_embeddings = [[] for _ in all_texts_to_embed]

        entity_embeddings = all_embeddings[:len(entities)]
        relation_embeddings = all_embeddings[len(entities):]
        logger.info(f"[add_text] Embedding done, writing to Neo4j...")

        with self._driver.session() as session:
            # Create episode node
            def _create_episode(tx):
                tx.run(
                    """
                    CREATE (ep:Episode {
                        uuid: $uuid,
                        graph_id: $graph_id,
                        data: $data,
                        processed: true,
                        created_at: $created_at
                    })
                    """,
                    uuid=episode_id,
                    graph_id=graph_id,
                    data=text,
                    created_at=now,
                )

            self._call_with_retry(session.execute_write, _create_episode)

            # Entity resolution — map variant names to canonical existing ones
            # before MERGE, so duplicates fold into the existing node instead
            # of creating a parallel one.
            try:
                resolution_map = self._resolver.resolve_batch(
                    session, graph_id, entities, entity_embeddings
                )
            except Exception as e:
                logger.warning(f"[add_text] Entity resolution failed, skipping: {e}")
                resolution_map = {}

            # MERGE entities in batch (UNWIND for bulk upsert)
            entity_uuid_map: Dict[str, str] = {}  # name_lower -> uuid
            entity_batch = []
            label_batch: Dict[str, list] = {}  # label -> [name_lower, ...]

            for idx, entity in enumerate(entities):
                ename = entity["name"]
                etype = entity["type"]
                attrs = entity.get("attributes", {})
                summary_text = entity_summaries[idx]
                embedding = entity_embeddings[idx] if idx < len(entity_embeddings) else []
                e_uuid = str(uuid.uuid4())
                # If resolver matched this entity to an existing one, use the
                # canonical name_lower for MERGE so it hits the existing node.
                canonical_nl = resolution_map.get(idx)
                name_lower_for_merge = canonical_nl or ename.lower()
                entity_uuid_map[ename.lower()] = e_uuid

                entity_batch.append({
                    "uuid": e_uuid,
                    "name": ename,
                    "name_lower": name_lower_for_merge,
                    "summary": summary_text,
                    "attrs_json": json.dumps(attrs, ensure_ascii=False),
                    "embedding": embedding,
                })

                if etype and etype != "Entity":
                    label_batch.setdefault(etype, []).append(name_lower_for_merge)

            if entity_batch:
                def _merge_entities_batch(tx, _batch=entity_batch):
                    result = tx.run(
                        """
                        UNWIND $batch AS e
                        MERGE (n:Entity {graph_id: $gid, name_lower: e.name_lower})
                        ON CREATE SET
                            n.uuid = e.uuid,
                            n.name = e.name,
                            n.summary = e.summary,
                            n.attributes_json = e.attrs_json,
                            n.embedding = e.embedding,
                            n.created_at = $now
                        ON MATCH SET
                            n.summary = CASE WHEN n.summary = '' OR n.summary IS NULL
                                THEN e.summary ELSE n.summary END,
                            n.attributes_json = e.attrs_json,
                            n.embedding = e.embedding
                        RETURN e.name_lower AS name_lower, n.uuid AS uuid
                        """,
                        batch=_batch,
                        gid=graph_id,
                        now=now,
                    )
                    return [(r["name_lower"], r["uuid"]) for r in result]

                uuid_pairs = self._call_with_retry(session.execute_write, _merge_entities_batch)
                for name_lower, actual_uuid in uuid_pairs:
                    entity_uuid_map[name_lower] = actual_uuid

                # Alias: relations extracted by NER reference entities by their
                # original (un-resolved) names. Map each original_name_lower to
                # the canonical UUID so relation creation below finds the right
                # endpoint.
                for idx, canonical_nl in resolution_map.items():
                    original_nl = entities[idx]["name"].lower()
                    if canonical_nl in entity_uuid_map:
                        entity_uuid_map[original_nl] = entity_uuid_map[canonical_nl]

                # Add type labels in batch (one query per label type)
                for label, name_lowers in label_batch.items():
                    try:
                        def _add_labels(tx, _label=label, _names=name_lowers):
                            tx.run(
                                f"UNWIND $names AS nl "
                                f"MATCH (n:Entity {{graph_id: $gid, name_lower: nl}}) "
                                f"SET n:`{_label}`",
                                names=_names,
                                gid=graph_id,
                            )
                        self._call_with_retry(session.execute_write, _add_labels)
                    except Exception as e:
                        logger.warning(f"Failed to add label '{label}': {e}")

            # Create relations in batch (UNWIND)
            relation_batch = []
            for idx, relation in enumerate(relations):
                source_name = relation["source"]
                target_name = relation["target"]
                source_uuid = entity_uuid_map.get(source_name.lower())
                target_uuid = entity_uuid_map.get(target_name.lower())

                if not source_uuid or not target_uuid:
                    logger.warning(
                        f"Skipping relation {source_name}->{target_name}: "
                        f"entity not found in extraction results"
                    )
                    continue

                fact_embedding = relation_embeddings[idx] if idx < len(relation_embeddings) else []
                relation_batch.append({
                    "uuid": str(uuid.uuid4()),
                    "src_uuid": source_uuid,
                    "tgt_uuid": target_uuid,
                    "name": relation["type"],
                    "fact": relation["fact"],
                    "fact_embedding": fact_embedding,
                    "episode_id": episode_id,
                })

            # Contradiction detection — invalidate existing edges that this
            # batch supersedes. Runs before the CREATE so the new edges see a
            # clean "current" view when hybrid search runs.
            if relation_batch:
                try:
                    to_invalidate = self._contradiction.detect(
                        session, graph_id, relation_batch
                    )
                    for edge_uuid in to_invalidate:
                        self.invalidate_edge(edge_uuid, invalidated_at=now)
                except Exception as e:
                    logger.warning(f"[add_text] Contradiction detection failed: {e}")

            if relation_batch:
                # valid_at defaults to now; callers can override via add_text(valid_at=...)
                # to express round-aware or historical ingestion (e.g., a simulation
                # fact that became true at round N's wall-clock time).
                edge_valid_at = valid_at if valid_at is not None else now
                edge_source_id = source_id if source_id is not None else episode_id

                def _create_relations_batch(tx, _batch=relation_batch):
                    tx.run(
                        """
                        UNWIND $batch AS r
                        MATCH (src:Entity {uuid: r.src_uuid})
                        MATCH (tgt:Entity {uuid: r.tgt_uuid})
                        CREATE (src)-[rel:RELATION {
                            uuid: r.uuid,
                            graph_id: $gid,
                            name: r.name,
                            fact: r.fact,
                            fact_embedding: r.fact_embedding,
                            attributes_json: '{}',
                            episode_ids: [r.episode_id],
                            created_at: $now,
                            valid_at: $valid_at,
                            invalid_at: null,
                            expired_at: null,
                            kind: $kind,
                            source_type: $source_type,
                            source_id: $source_id
                        }]->(tgt)
                        """,
                        batch=_batch,
                        gid=graph_id,
                        now=now,
                        valid_at=edge_valid_at,
                        kind=kind,
                        source_type=source_type,
                        source_id=edge_source_id,
                    )

                self._call_with_retry(session.execute_write, _create_relations_batch)

        logger.info(f"[add_text] Chunk done: episode={episode_id}")
        return episode_id

    def add_text_batch(
        self,
        graph_id: str,
        chunks: List[str],
        batch_size: int = 3,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[str]:
        """Batch-add text chunks with progress reporting."""
        episode_ids = []
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            if not chunk or not chunk.strip():
                continue
            episode_id = self.add_text(graph_id, chunk)
            episode_ids.append(episode_id)

            if progress_callback:
                progress = (i + 1) / total
                progress_callback(progress)

            logger.info(f"Processed chunk {i + 1}/{total}")

        return episode_ids

    def wait_for_processing(
        self,
        episode_ids: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        timeout: int = 600,
    ) -> None:
        """No-op — processing is synchronous in Neo4j."""
        if progress_callback:
            progress_callback(1.0)

    # ----------------------------------------------------------------
    # Read nodes
    # ----------------------------------------------------------------

    def get_all_nodes(self, graph_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
        def _read(tx):
            result = tx.run(
                """
                MATCH (n:Entity {graph_id: $gid})
                RETURN n, labels(n) AS labels
                ORDER BY n.created_at DESC
                LIMIT $limit
                """,
                gid=graph_id,
                limit=limit,
            )
            return [self._node_to_dict(record["n"], record["labels"]) for record in result]

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    def get_node(self, uuid: str) -> Optional[Dict[str, Any]]:
        def _read(tx):
            result = tx.run(
                "MATCH (n:Entity {uuid: $uuid}) RETURN n, labels(n) AS labels",
                uuid=uuid,
            )
            record = result.single()
            if record:
                return self._node_to_dict(record["n"], record["labels"])
            return None

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """O(1) Cypher — NOT full scan + filter like the old Zep code."""
        def _read(tx):
            result = tx.run(
                """
                MATCH (n:Entity {uuid: $uuid})-[r:RELATION]-(m:Entity)
                RETURN r, startNode(r).uuid AS src_uuid, endNode(r).uuid AS tgt_uuid
                """,
                uuid=node_uuid,
            )
            return [
                self._edge_to_dict(record["r"], record["src_uuid"], record["tgt_uuid"])
                for record in result
            ]

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    def get_nodes_by_label(self, graph_id: str, label: str) -> List[Dict[str, Any]]:
        def _read(tx):
            # Dynamic label in query (safe — label comes from ontology, not user input)
            query = f"""
                MATCH (n:Entity:`{label}` {{graph_id: $gid}})
                RETURN n, labels(n) AS labels
            """
            result = tx.run(query, gid=graph_id)
            return [self._node_to_dict(record["n"], record["labels"]) for record in result]

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    # ----------------------------------------------------------------
    # Read edges
    # ----------------------------------------------------------------

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        def _read(tx):
            result = tx.run(
                """
                MATCH (src:Entity)-[r:RELATION {graph_id: $gid}]->(tgt:Entity)
                RETURN r, src.uuid AS src_uuid, tgt.uuid AS tgt_uuid
                ORDER BY r.created_at DESC
                """,
                gid=graph_id,
            )
            return [
                self._edge_to_dict(record["r"], record["src_uuid"], record["tgt_uuid"])
                for record in result
            ]

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    # ----------------------------------------------------------------
    # Search
    # ----------------------------------------------------------------

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
        Hybrid search — returns results matching the scope.

        Args:
            as_of: ISO-8601 timestamp. If set, returns only edges that were
                valid at that moment.
            include_invalidated: If True, returns superseded edges alongside
                current ones.
            kinds: optional filter on edge epistemic kind — a list containing
                any of "fact", "belief", "observation". None = all kinds.

        Returns a dict with 'edges' and/or 'nodes' lists.
        """
        if kinds is not None:
            for k in kinds:
                if k not in ("fact", "belief", "observation"):
                    raise ValueError(f"Invalid kind: {k!r}")

        result = {"edges": [], "nodes": [], "query": query}

        with self._driver.session() as session:
            if scope in ("edges", "both"):
                result["edges"] = self._search.search_edges(
                    session, graph_id, query, limit,
                    as_of=as_of, include_invalidated=include_invalidated, kinds=kinds,
                )

            if scope in ("nodes", "both"):
                result["nodes"] = self._search.search_nodes(
                    session, graph_id, query, limit,
                    as_of=as_of, include_invalidated=include_invalidated, kinds=kinds,
                )

        return result

    def invalidate_edge(
        self,
        edge_uuid: str,
        invalidated_at: Optional[str] = None,
    ) -> bool:
        """
        Mark an edge as superseded: sets invalid_at and expired_at to the given
        timestamp (or now if omitted). Edge is NOT deleted — preserved for
        historical / audit queries via `search(include_invalidated=True)` or
        `search(as_of=t)` where t < invalidated_at.

        Returns True if the edge was updated, False if it didn't exist.
        """
        ts = invalidated_at or datetime.now(timezone.utc).isoformat()

        def _invalidate(tx):
            # Directed match to avoid double-returning the same edge.
            result = tx.run(
                """
                MATCH (s)-[r:RELATION {uuid: $uuid}]->(t)
                WHERE r.invalid_at IS NULL
                SET r.invalid_at = $ts, r.expired_at = $ts
                RETURN r.uuid AS uuid
                """,
                uuid=edge_uuid, ts=ts,
            )
            return result.single() is not None

        with self._driver.session() as session:
            return bool(self._call_with_retry(session.execute_write, _invalidate))

    # ----------------------------------------------------------------
    # Community subgraph (zoom-out layer)
    # ----------------------------------------------------------------

    def build_communities(self, graph_id: str) -> Dict[str, int]:
        """
        Leiden-cluster the entity graph, summarize each cluster with an LLM,
        and replace any existing :Community nodes for this graph.

        Returns {clusters_found, clusters_kept, entities_clustered}.
        """
        return self._community.build(graph_id)

    def search_communities(
        self, graph_id: str, query: str, limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search over community summaries for this graph."""
        return self._community.search(graph_id, query, limit=limit)

    def list_communities(self, graph_id: str) -> List[Dict[str, Any]]:
        """All communities for this graph, largest first."""
        return self._community.list_all(graph_id)

    def get_community(self, community_uuid: str) -> Optional[Dict[str, Any]]:
        """Community metadata + list of member entities."""
        return self._community.get_detail(community_uuid)

    # ----------------------------------------------------------------
    # Reasoning trace (report-agent decision subgraph)
    # ----------------------------------------------------------------

    def create_reasoning_recorder(
        self,
        report_id: str,
        graph_id: str,
        simulation_id: Optional[str],
        report_title: str,
    ):
        """
        Return a fresh ReasoningTraceRecorder bound to this storage's driver.
        The recorder buffers per-section steps in memory and flushes on
        finalize_section().
        """
        from .reasoning_trace import ReasoningTraceRecorder
        return ReasoningTraceRecorder(
            driver=self._driver,
            graph_id=graph_id,
            report_id=report_id,
            simulation_id=simulation_id,
            report_title=report_title,
        )

    def list_reports(self, graph_id: str) -> List[Dict[str, Any]]:
        """All reports generated for a graph, most recent first."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (r:Report {graph_id: $gid})
                OPTIONAL MATCH (r)-[:HAS_SECTION]->(s:ReportSection)
                WITH r, count(s) AS section_count
                RETURN r.uuid AS uuid, r.title AS title,
                       r.simulation_id AS simulation_id,
                       r.created_at AS created_at,
                       section_count
                ORDER BY r.created_at DESC
                """,
                gid=graph_id,
            )
            return [dict(rec) for rec in result]

    def get_reasoning_trace(self, section_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Full trace for one section: metadata + ordered steps.
        Use list_reports + list_report_sections to navigate to a section UUID.
        """
        with self._driver.session() as session:
            row = session.run(
                """
                MATCH (s:ReportSection {uuid: $sid})
                OPTIONAL MATCH (s)-[:HAS_STEP]->(st:ReasoningStep)
                WITH s, st ORDER BY st.step_index
                WITH s, collect({
                    uuid: st.uuid,
                    step_index: st.step_index,
                    kind: st.kind,
                    content: st.content,
                    iteration: st.iteration,
                    tool_name: st.tool_name,
                    tool_params_json: st.tool_params_json,
                    timestamp: st.timestamp
                }) AS steps
                RETURN s.uuid AS uuid, s.report_id AS report_id,
                       s.title AS title, s.section_index AS section_index,
                       s.final_text AS final_text, s.created_at AS created_at,
                       [st IN steps WHERE st.uuid IS NOT NULL] AS steps
                """,
                sid=section_uuid,
            ).single()
            if not row or not row["uuid"]:
                return None
            return dict(row)

    def list_report_sections(self, report_uuid: str) -> List[Dict[str, Any]]:
        """All sections of a report in order."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (:Report {uuid: $rid})-[:HAS_SECTION]->(s:ReportSection)
                OPTIONAL MATCH (s)-[:HAS_STEP]->(st:ReasoningStep)
                WITH s, count(st) AS step_count
                RETURN s.uuid AS uuid, s.title AS title,
                       s.section_index AS section_index, step_count,
                       s.created_at AS created_at
                ORDER BY s.section_index
                """,
                rid=report_uuid,
            )
            return [dict(rec) for rec in result]

    # ----------------------------------------------------------------
    # Graph info
    # ----------------------------------------------------------------

    def get_graph_info(self, graph_id: str) -> Dict[str, Any]:
        def _read(tx):
            # Count nodes
            node_result = tx.run(
                "MATCH (n:Entity {graph_id: $gid}) RETURN count(n) AS cnt",
                gid=graph_id,
            )
            node_count = node_result.single()["cnt"]

            # Count edges
            edge_result = tx.run(
                "MATCH ()-[r:RELATION {graph_id: $gid}]->() RETURN count(r) AS cnt",
                gid=graph_id,
            )
            edge_count = edge_result.single()["cnt"]

            # Distinct entity types
            label_result = tx.run(
                """
                MATCH (n:Entity {graph_id: $gid})
                UNWIND labels(n) AS lbl
                WITH lbl WHERE lbl <> 'Entity'
                RETURN DISTINCT lbl
                """,
                gid=graph_id,
            )
            entity_types = [record["lbl"] for record in label_result]

            return {
                "graph_id": graph_id,
                "node_count": node_count,
                "edge_count": edge_count,
                "entity_types": entity_types,
            }

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """
        Full graph dump with enriched edge format (for frontend).
        Includes derived fields: fact_type, source_node_name, target_node_name.
        """
        def _read(tx):
            # Get all nodes
            node_result = tx.run(
                """
                MATCH (n:Entity {graph_id: $gid})
                RETURN n, labels(n) AS labels
                """,
                gid=graph_id,
            )
            nodes = []
            node_map: Dict[str, str] = {}  # uuid -> name
            for record in node_result:
                nd = self._node_to_dict(record["n"], record["labels"])
                nodes.append(nd)
                node_map[nd["uuid"]] = nd["name"]

            # Get all edges with source/target node names (JOIN)
            edge_result = tx.run(
                """
                MATCH (src:Entity)-[r:RELATION {graph_id: $gid}]->(tgt:Entity)
                RETURN r, src.uuid AS src_uuid, tgt.uuid AS tgt_uuid,
                       src.name AS src_name, tgt.name AS tgt_name
                """,
                gid=graph_id,
            )
            edges = []
            for record in edge_result:
                ed = self._edge_to_dict(record["r"], record["src_uuid"], record["tgt_uuid"])
                # Enriched fields for frontend
                ed["fact_type"] = ed["name"]
                ed["source_node_name"] = record["src_name"] or ""
                ed["target_node_name"] = record["tgt_name"] or ""
                # Legacy alias
                ed["episodes"] = ed.get("episode_ids", [])
                edges.append(ed)

            return {
                "graph_id": graph_id,
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges),
            }

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    # ----------------------------------------------------------------
    # Dict conversion helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _node_to_dict(node, labels: List[str]) -> Dict[str, Any]:
        """Convert Neo4j node to the standard node dict format."""
        props = dict(node)
        attrs_json = props.pop("attributes_json", "{}")
        try:
            attributes = json.loads(attrs_json) if attrs_json else {}
        except (json.JSONDecodeError, TypeError):
            attributes = {}

        # Remove internal fields from dict
        props.pop("embedding", None)
        props.pop("name_lower", None)

        return {
            "uuid": props.get("uuid", ""),
            "name": props.get("name", ""),
            "labels": [l for l in labels if l != "Entity"] if labels else [],
            "summary": props.get("summary", ""),
            "attributes": attributes,
            "created_at": props.get("created_at"),
        }

    @staticmethod
    def _edge_to_dict(rel, source_uuid: str, target_uuid: str) -> Dict[str, Any]:
        """Convert Neo4j relationship to the standard edge dict format."""
        props = dict(rel)
        attrs_json = props.pop("attributes_json", "{}")
        try:
            attributes = json.loads(attrs_json) if attrs_json else {}
        except (json.JSONDecodeError, TypeError):
            attributes = {}

        # Remove internal fields
        props.pop("fact_embedding", None)

        episode_ids = props.get("episode_ids", [])
        if episode_ids and not isinstance(episode_ids, list):
            episode_ids = [str(episode_ids)]

        return {
            "uuid": props.get("uuid", ""),
            "name": props.get("name", ""),
            "fact": props.get("fact", ""),
            "source_node_uuid": source_uuid,
            "target_node_uuid": target_uuid,
            "attributes": attributes,
            "created_at": props.get("created_at"),
            "valid_at": props.get("valid_at"),
            "invalid_at": props.get("invalid_at"),
            "expired_at": props.get("expired_at"),
            "episode_ids": episode_ids,
        }

    # ================================================================
    # Graph reasoning queries (Cypher-native, no GDS dependency)
    # ================================================================

    def get_degree_centrality(self, graph_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Top entities by total relationship count (degree centrality)."""
        def _read(tx):
            result = tx.run(
                """
                MATCH (n:Entity {graph_id: $gid})-[r:RELATION]-()
                WITH n, labels(n) AS labels, count(r) AS degree
                ORDER BY degree DESC
                LIMIT $limit
                RETURN n.name AS name, n.uuid AS uuid,
                       [l IN labels WHERE l <> 'Entity'] AS types,
                       n.summary AS summary, degree
                """,
                gid=graph_id,
                limit=limit,
            )
            return [dict(record) for record in result]

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    def get_bridge_entities(self, graph_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Entities that connect otherwise separate clusters (high betweenness approximation).

        Uses a heuristic: entities whose neighbors have the least overlap with each other.
        """
        def _read(tx):
            result = tx.run(
                """
                MATCH (n:Entity {graph_id: $gid})-[:RELATION]-(neighbor)
                WITH n, labels(n) AS labels, collect(DISTINCT neighbor.uuid) AS neighbors, count(DISTINCT neighbor) AS deg
                WHERE deg >= 2
                WITH n, labels, neighbors, deg,
                     // Count how many of n's neighbors are connected to each other
                     size([i IN range(0, size(neighbors)-2) |
                           [j IN range(i+1, size(neighbors)-1) |
                            EXISTS { MATCH (a:Entity {uuid: neighbors[i]})-[:RELATION]-(b:Entity {uuid: neighbors[j]}) }
                           ]
                          ]) AS internal_edges
                // Bridge score: high degree but low internal connectivity
                WITH n, labels, deg, internal_edges,
                     toFloat(deg) / (CASE WHEN internal_edges > 0 THEN internal_edges ELSE 0.5 END) AS bridge_score
                ORDER BY bridge_score DESC
                LIMIT $limit
                RETURN n.name AS name, n.uuid AS uuid,
                       [l IN labels WHERE l <> 'Entity'] AS types,
                       n.summary AS summary, deg AS degree, bridge_score
                """,
                gid=graph_id,
                limit=limit,
            )
            return [dict(record) for record in result]

        try:
            with self._driver.session() as session:
                return self._call_with_retry(session.execute_read, _read)
        except Exception as e:
            logger.warning(f"Bridge entity query failed (may need Neo4j 5.9+ for EXISTS subquery): {e}")
            # Fallback: just return high-degree nodes
            return self.get_degree_centrality(graph_id, limit)

    def get_shortest_path(
        self, graph_id: str, source_name: str, target_name: str, max_hops: int = 6
    ) -> List[Dict[str, Any]]:
        """Find shortest path between two named entities."""
        def _read(tx):
            result = tx.run(
                f"""
                MATCH (a:Entity {{graph_id: $gid}}), (b:Entity {{graph_id: $gid}})
                WHERE toLower(a.name) CONTAINS toLower($src)
                  AND toLower(b.name) CONTAINS toLower($tgt)
                WITH a, b LIMIT 1
                MATCH p = shortestPath((a)-[:RELATION*1..{max_hops}]-(b))
                UNWIND relationships(p) AS r
                WITH r, startNode(r) AS sn, endNode(r) AS en
                RETURN sn.name AS source, r.name AS relation, r.fact AS fact, en.name AS target
                """,
                gid=graph_id,
                src=source_name,
                tgt=target_name,
            )
            return [dict(record) for record in result]

        with self._driver.session() as session:
            return self._call_with_retry(session.execute_read, _read)

    def get_entity_communities(self, graph_id: str) -> List[List[Dict[str, Any]]]:
        """Detect communities using weakly connected components via Cypher.

        Returns a list of communities (each is a list of node dicts), sorted largest first.
        """
        def _read(tx):
            # Get all nodes and their neighbors to build adjacency
            result = tx.run(
                """
                MATCH (n:Entity {graph_id: $gid})
                OPTIONAL MATCH (n)-[:RELATION]-(m:Entity {graph_id: $gid})
                RETURN n.uuid AS node_uuid, n.name AS name,
                       [l IN labels(n) WHERE l <> 'Entity'] AS types,
                       n.summary AS summary,
                       collect(DISTINCT m.uuid) AS neighbor_uuids
                """,
                gid=graph_id,
            )
            return [dict(record) for record in result]

        with self._driver.session() as session:
            nodes_data = self._call_with_retry(session.execute_read, _read)

        # Build adjacency and run union-find
        uuid_to_info = {}
        adjacency = {}
        for nd in nodes_data:
            uid = nd["node_uuid"]
            uuid_to_info[uid] = {
                "uuid": uid,
                "name": nd["name"],
                "types": nd["types"],
                "summary": nd["summary"],
            }
            adjacency[uid] = [u for u in nd["neighbor_uuids"] if u]

        # Union-Find
        parent = {uid: uid for uid in uuid_to_info}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for uid, neighbors in adjacency.items():
            for nid in neighbors:
                if nid in parent:
                    union(uid, nid)

        # Group by component
        components: Dict[str, list] = {}
        for uid in uuid_to_info:
            root = find(uid)
            components.setdefault(root, []).append(uuid_to_info[uid])

        # Sort by size descending
        communities = sorted(components.values(), key=len, reverse=True)
        return communities

    def detect_contradictions(self, graph_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Find node pairs connected by multiple edges with potentially contradicting facts.

        Looks for node pairs that have 2+ edges and checks for opposing sentiment signals.
        """
        def _read(tx):
            result = tx.run(
                """
                MATCH (a:Entity {graph_id: $gid})-[r:RELATION]->(b:Entity {graph_id: $gid})
                WITH a, b, collect({fact: r.fact, name: r.name, created_at: r.created_at}) AS edges
                WHERE size(edges) >= 2
                RETURN a.name AS source_name, a.uuid AS source_uuid,
                       b.name AS target_name, b.uuid AS target_uuid,
                       edges
                ORDER BY size(edges) DESC
                LIMIT $limit
                """,
                gid=graph_id,
                limit=limit,
            )
            return [dict(record) for record in result]

        with self._driver.session() as session:
            pairs = self._call_with_retry(session.execute_read, _read)

        # Heuristic: check for opposing sentiment in facts
        positive_words = {"support", "agree", "approve", "benefit", "positive", "welcome", "praise"}
        negative_words = {"oppose", "disagree", "reject", "harm", "negative", "condemn", "criticize"}

        contradictions = []
        for pair in pairs:
            facts = pair["edges"]
            sentiments = []
            for edge in facts:
                fact = (edge.get("fact") or "").lower()
                pos = sum(1 for w in positive_words if w in fact)
                neg = sum(1 for w in negative_words if w in fact)
                if pos > neg:
                    sentiments.append("positive")
                elif neg > pos:
                    sentiments.append("negative")
                else:
                    sentiments.append("neutral")

            # A contradiction exists if we have both positive and negative
            has_positive = "positive" in sentiments
            has_negative = "negative" in sentiments
            if has_positive and has_negative:
                contradictions.append({
                    "source_name": pair["source_name"],
                    "target_name": pair["target_name"],
                    "edges": facts,
                    "sentiments": sentiments,
                    "contradiction_type": "opposing_sentiments",
                })

        return contradictions

    def get_temporal_evolution(self, graph_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Group edges by creation time to show how the graph evolved."""
        def _read(tx):
            result = tx.run(
                """
                MATCH (src:Entity {graph_id: $gid})-[r:RELATION {graph_id: $gid}]->(tgt:Entity)
                WHERE r.created_at IS NOT NULL
                RETURN r.created_at AS created_at, r.fact AS fact, r.name AS relation,
                       src.name AS source_name, tgt.name AS target_name
                ORDER BY r.created_at
                """,
                gid=graph_id,
            )
            return [dict(record) for record in result]

        with self._driver.session() as session:
            edges = self._call_with_retry(session.execute_read, _read)

        # Group into time buckets (by episode/created_at)
        buckets: Dict[str, list] = {}
        for edge in edges:
            ts = str(edge.get("created_at", "unknown"))
            # Group by date portion if it's a datetime string
            date_key = ts[:10] if len(ts) >= 10 else ts
            buckets.setdefault(date_key, []).append(edge)

        return buckets
