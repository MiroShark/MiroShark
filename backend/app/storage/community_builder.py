"""
CommunityBuilder — Graphiti tier-3 community subgraph.

Runs Leiden community detection on the entity graph (ignoring invalidated
edges), filters tiny clusters, and has an LLM write a short title + 2-sentence
summary for each. Summaries are embedded and stored as :Community nodes with
MEMBER_OF edges to their constituent entities.

The result is a "zoom out" layer the report agent can browse before drilling
into individual facts — one semantic-search call over ~20 cluster summaries
surfaces the right neighborhood far faster than scanning 200+ entities.
"""

import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from ..utils.llm_client import LLMClient, create_ner_llm_client
from .embedding_service import EmbeddingService

logger = logging.getLogger('miroshark.community_builder')


_SUMMARY_PROMPT = """You are labeling communities of related entities in a knowledge graph.

For each community below, generate:
  - "title": 2-6 word theme label (e.g. "DeFi oracle exploits", "UAE digital-asset policy").
  - "summary": 1-2 sentence description of what ties these entities together.

Be specific — avoid generic titles like "Miscellaneous" or "Various entities".
If a community has no clear theme, title it after its most central entity.

COMMUNITIES:
{block}

Return JSON only:
{{"communities": {{"1": {{"title": "...", "summary": "..."}}, "2": {{...}}, ...}}}}"""


class CommunityBuilder:
    """Build, store, and update community clusters over an entity graph."""

    def __init__(
        self,
        driver,
        embedding_service: EmbeddingService,
        llm_client: Optional[LLMClient] = None,
    ):
        self._driver = driver
        self._embedding = embedding_service
        self._llm_override = llm_client
        self._llm: Optional[LLMClient] = None

    def _llm_client(self) -> LLMClient:
        if self._llm is None:
            self._llm = self._llm_override or create_ner_llm_client()
        return self._llm

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def build(self, graph_id: str) -> Dict[str, int]:
        """
        Full rebuild: cluster → summarize → replace existing communities.

        Idempotent: deletes existing :Community nodes for the graph, then
        writes new ones. Safe to call repeatedly.

        Returns a stats dict: {clusters_found, clusters_kept, entities_clustered}.
        """
        logger.info(f"[community_builder] Building communities for graph {graph_id}")

        edges, uuid_list = self._load_entity_graph(graph_id)
        if len(uuid_list) < Config.COMMUNITY_MIN_SIZE:
            logger.info(
                f"[community_builder] Graph too small ({len(uuid_list)} entities) — skipping"
            )
            return {"clusters_found": 0, "clusters_kept": 0, "entities_clustered": 0}

        clusters = self._cluster(edges, len(uuid_list))
        clusters_found = len(clusters)

        # Filter: keep only clusters above min size, cap at max count
        kept = [
            [uuid_list[i] for i in members]
            for members in clusters
            if len(members) >= Config.COMMUNITY_MIN_SIZE
        ]
        kept = kept[: Config.COMMUNITY_MAX_COUNT]

        if not kept:
            logger.info(f"[community_builder] No clusters met size threshold")
            self._delete_existing(graph_id)
            return {
                "clusters_found": clusters_found,
                "clusters_kept": 0,
                "entities_clustered": 0,
            }

        # Pull entity data for LLM prompt + summaries
        entity_data = self._load_entity_metadata(graph_id, kept)
        labels = self._summarize(kept, entity_data)
        embeddings = self._embedding.embed_batch(
            [f"{l['title']}. {l['summary']}" for l in labels]
        )

        # Replace in one transaction
        self._delete_existing(graph_id)
        self._write(graph_id, kept, labels, embeddings)

        entities_clustered = sum(len(c) for c in kept)
        logger.info(
            f"[community_builder] Built {len(kept)} communities "
            f"({entities_clustered} entities covered, {clusters_found - len(kept)} "
            f"below size threshold)"
        )
        return {
            "clusters_found": clusters_found,
            "clusters_kept": len(kept),
            "entities_clustered": entities_clustered,
        }

    def search(
        self,
        graph_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search over community summaries."""
        query_vector = self._embedding.embed(query)
        with self._driver.session() as session:
            try:
                result = session.run(
                    """
                    CALL db.index.vector.queryNodes('community_embedding', $k, $vec)
                    YIELD node, score
                    WHERE node.graph_id = $gid
                    RETURN node.uuid AS uuid,
                           node.title AS title,
                           node.summary AS summary,
                           node.member_count AS member_count,
                           score
                    ORDER BY score DESC
                    LIMIT $k
                    """,
                    k=limit, vec=query_vector, gid=graph_id,
                )
                return [dict(rec) for rec in result]
            except Exception as e:
                logger.warning(f"Community search failed (index may not exist): {e}")
                return []

    def list_all(self, graph_id: str) -> List[Dict[str, Any]]:
        """Return all communities for a graph, largest first."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (c:Community {graph_id: $gid})
                RETURN c.uuid AS uuid, c.title AS title, c.summary AS summary,
                       c.member_count AS member_count, c.created_at AS created_at
                ORDER BY c.member_count DESC
                """,
                gid=graph_id,
            )
            return [dict(rec) for rec in result]

    def get_detail(self, community_uuid: str) -> Optional[Dict[str, Any]]:
        """Community + its member entities."""
        with self._driver.session() as session:
            row = session.run(
                """
                MATCH (c:Community {uuid: $cid})
                OPTIONAL MATCH (c)<-[:MEMBER_OF]-(e:Entity)
                RETURN c.uuid AS uuid, c.title AS title, c.summary AS summary,
                       c.graph_id AS graph_id, c.member_count AS member_count,
                       c.created_at AS created_at,
                       collect({uuid: e.uuid, name: e.name, summary: e.summary}) AS members
                """,
                cid=community_uuid,
            ).single()
            if not row or not row["uuid"]:
                return None
            return dict(row)

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    def _load_entity_graph(
        self, graph_id: str
    ) -> Tuple[List[Tuple[int, int, int]], List[str]]:
        """
        Load (src_idx, tgt_idx, weight) triples for Leiden.
        Weight = count of distinct valid RELATION edges between the pair.
        """
        with self._driver.session() as session:
            # Collect all entity uuids that appear in any valid relation.
            # Pure isolates don't cluster anyway.
            entity_uuids = [
                r["u"] for r in session.run(
                    """
                    MATCH (n:Entity {graph_id: $gid})
                    WHERE EXISTS {
                        MATCH (n)-[r:RELATION]-(:Entity)
                        WHERE r.graph_id = $gid AND r.invalid_at IS NULL
                    }
                    RETURN n.uuid AS u
                    """,
                    gid=graph_id,
                )
            ]
            idx = {u: i for i, u in enumerate(entity_uuids)}

            pair_weights: Dict[Tuple[int, int], int] = {}
            for rec in session.run(
                """
                MATCH (a:Entity)-[r:RELATION]->(b:Entity)
                WHERE r.graph_id = $gid AND r.invalid_at IS NULL
                  AND a.graph_id = $gid AND b.graph_id = $gid
                RETURN a.uuid AS src, b.uuid AS tgt
                """,
                gid=graph_id,
            ):
                s, t = idx.get(rec["src"]), idx.get(rec["tgt"])
                if s is None or t is None or s == t:
                    continue
                key = (min(s, t), max(s, t))  # undirected
                pair_weights[key] = pair_weights.get(key, 0) + 1

        edges = [(s, t, w) for (s, t), w in pair_weights.items()]
        return edges, entity_uuids

    def _cluster(self, edges: List[Tuple[int, int, int]], n_vertices: int) -> List[List[int]]:
        """Run Leiden community detection. Returns list of member-index lists."""
        try:
            import igraph as ig
        except ImportError:
            logger.error("igraph not installed — cannot build communities")
            return []

        if not edges:
            return []

        g = ig.Graph(n=n_vertices, edges=[(s, t) for s, t, _ in edges], directed=False)
        g.es["weight"] = [w for _, _, w in edges]

        try:
            partition = g.community_leiden(
                weights="weight",
                objective_function="modularity",
                n_iterations=3,
            )
        except Exception as e:
            logger.warning(f"Leiden failed, falling back to label_propagation: {e}")
            partition = g.community_label_propagation(weights="weight")

        # Group vertices by membership id
        groups: Dict[int, List[int]] = {}
        for vertex_idx, cluster_id in enumerate(partition.membership):
            groups.setdefault(cluster_id, []).append(vertex_idx)
        # Sort by size descending
        return sorted(groups.values(), key=len, reverse=True)

    def _load_entity_metadata(
        self, graph_id: str, clusters: List[List[str]]
    ) -> Dict[str, Dict]:
        """Fetch name + summary for every entity in any kept cluster."""
        all_uuids = [u for cluster in clusters for u in cluster]
        if not all_uuids:
            return {}
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (n:Entity)
                WHERE n.uuid IN $uuids AND n.graph_id = $gid
                RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary
                """,
                uuids=all_uuids, gid=graph_id,
            )
            return {rec["uuid"]: dict(rec) for rec in result}

    def _summarize(
        self,
        clusters: List[List[str]],
        entity_data: Dict[str, Dict],
    ) -> List[Dict[str, str]]:
        """One batched LLM call → {title, summary} per cluster."""
        # Build the prompt block. Cap member list per cluster to keep tokens bounded.
        MAX_MEMBERS_IN_PROMPT = 15
        blocks = []
        for i, members in enumerate(clusters, start=1):
            lines = [f"Community {i} ({len(members)} entities):"]
            sample = members[:MAX_MEMBERS_IN_PROMPT]
            for uid in sample:
                meta = entity_data.get(uid, {})
                name = meta.get("name") or uid[:8]
                summary = (meta.get("summary") or "")[:100].replace('"', "'")
                lines.append(f'  - {name}: {summary}')
            if len(members) > MAX_MEMBERS_IN_PROMPT:
                lines.append(f'  - … and {len(members) - MAX_MEMBERS_IN_PROMPT} more')
            blocks.append("\n".join(lines))

        prompt = _SUMMARY_PROMPT.format(block="\n\n".join(blocks))

        try:
            resp = self._llm_client().chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2048,
            )
            raw = resp.get("communities", {}) if isinstance(resp, dict) else {}
        except Exception as e:
            logger.warning(f"Community summarization LLM call failed: {e}")
            raw = {}

        out = []
        for i, members in enumerate(clusters, start=1):
            entry = raw.get(str(i), {}) if isinstance(raw, dict) else {}
            title = str(entry.get("title", "")).strip() or self._fallback_title(members, entity_data)
            summary = str(entry.get("summary", "")).strip() or f"{len(members)} related entities."
            out.append({"title": title[:120], "summary": summary[:600]})
        return out

    @staticmethod
    def _fallback_title(members: List[str], entity_data: Dict[str, Dict]) -> str:
        """Title = most central (first) member's name when LLM fails."""
        if not members:
            return "Cluster"
        name = entity_data.get(members[0], {}).get("name") or members[0][:8]
        return f"{name} cluster"

    def _delete_existing(self, graph_id: str) -> None:
        """Remove all Community nodes + MEMBER_OF edges for this graph."""
        with self._driver.session() as session:
            session.run(
                """
                MATCH (c:Community {graph_id: $gid})
                DETACH DELETE c
                """,
                gid=graph_id,
            )

    def _write(
        self,
        graph_id: str,
        clusters: List[List[str]],
        labels: List[Dict[str, str]],
        embeddings: List[List[float]],
    ) -> None:
        """Create Community nodes + MEMBER_OF edges."""
        now = datetime.now(timezone.utc).isoformat()
        batch = []
        for members, lab, emb in zip(clusters, labels, embeddings):
            batch.append({
                "uuid": str(uuid_mod.uuid4()),
                "title": lab["title"],
                "summary": lab["summary"],
                "embedding": emb,
                "member_uuids": members,
                "member_count": len(members),
            })

        with self._driver.session() as session:
            session.run(
                """
                UNWIND $batch AS b
                CREATE (c:Community {
                    uuid: b.uuid,
                    graph_id: $gid,
                    title: b.title,
                    summary: b.summary,
                    summary_embedding: b.embedding,
                    member_count: b.member_count,
                    created_at: $now,
                    updated_at: $now
                })
                WITH c, b
                UNWIND b.member_uuids AS muid
                MATCH (e:Entity {uuid: muid})
                CREATE (e)-[:MEMBER_OF {graph_id: $gid, created_at: $now}]->(c)
                """,
                batch=batch, gid=graph_id, now=now,
            )
