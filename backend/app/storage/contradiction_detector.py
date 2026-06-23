"""
ContradictionDetector — invalidate old edges that new facts supersede.

At ingestion time, for each new relation extracted by NER, we check whether
the graph already has a valid edge between the same (source, target) pair.
If so, a batched LLM call judges whether the new fact contradicts (and
supersedes) any existing one; contradicted edges are marked invalid_at=now
rather than deleted, preserving the bi-temporal audit trail.

This is Graphiti's "contradicting facts are invalidated rather than deleted"
behavior, scoped minimally: we only look at same-endpoint contradictions
because that's where >90% of real contradictions sit.
"""

import logging
from typing import Dict, List, Optional, Tuple

from neo4j import Session as Neo4jSession

from ..config import Config
from ..utils.llm_client import LLMClient, create_ner_llm_client

logger = logging.getLogger('miroshark.contradiction_detector')


_ADJUDICATION_PROMPT = """You are checking whether new facts supersede old ones in a knowledge graph.

For each PAIR of facts about the same source and target entities, decide:
  - "contradicts": the NEW fact contradicts and supersedes the OLD fact
    (they cannot both be true at the same time; the NEW one is a later update).
  - "not_contradicts": both facts can coexist (they're complementary, or the
    new one is just a rephrasing, or they talk about different aspects).

Be conservative. Only mark as "contradicts" when you're confident the new
fact makes the old one false.

PAIRS:
{pairs_block}

Return JSON only:
{{"results": {{"1": "contradicts", "2": "not_contradicts", ...}}}}"""


class ContradictionDetector:
    """Detect and invalidate superseded edges at ingestion time."""

    # Per-pair hard limit to bound LLM cost — if a single (src,tgt) pair
    # has more existing edges than this, we'd be running an expensive LLM
    # call on a long list. Skip resolution in that case.
    MAX_EXISTING_PER_PAIR = 5
    # Upper bound on total pairs sent to the LLM in one call.
    MAX_PAIRS_PER_CALL = 30

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self._llm_override = llm_client
        self._llm: Optional[LLMClient] = None

    @property
    def enabled(self) -> bool:
        return Config.CONTRADICTION_DETECTION_ENABLED

    def _llm_client(self) -> LLMClient:
        if self._llm is None:
            self._llm = self._llm_override or create_ner_llm_client()
        return self._llm

    def detect(
        self,
        session: Neo4jSession,
        graph_id: str,
        new_relations: List[Dict],
    ) -> List[str]:
        """
        Find existing edges that are contradicted (and thus superseded) by the
        batch of new relations. Returns a list of edge UUIDs to invalidate.

        Args:
            new_relations: each dict has at least
              {src_uuid, tgt_uuid, fact, name}
              ("name" is the relation type label from NER).
        """
        if not self.enabled or not new_relations:
            return []

        # For each new relation, look up existing valid edges between the same
        # endpoint pair — these are the contradiction candidates.
        pairs: List[Tuple[Dict, Dict]] = []  # (new_rel, existing_rel)
        for new_rel in new_relations:
            src_uuid = new_rel.get("src_uuid")
            tgt_uuid = new_rel.get("tgt_uuid")
            if not src_uuid or not tgt_uuid:
                continue
            existing = self._existing_edges_between(
                session, graph_id, src_uuid, tgt_uuid
            )
            for ex in existing[: self.MAX_EXISTING_PER_PAIR]:
                # Skip pairs where the new relation is already in the graph
                # (exact fact match — this is a replay, not a contradiction).
                if ex.get("fact") == new_rel.get("fact"):
                    continue
                pairs.append((new_rel, ex))
                if len(pairs) >= self.MAX_PAIRS_PER_CALL:
                    break
            if len(pairs) >= self.MAX_PAIRS_PER_CALL:
                break

        if not pairs:
            return []

        verdicts = self._llm_adjudicate(pairs)
        to_invalidate = [
            existing["uuid"]
            for (_, existing), verdict in zip(pairs, verdicts)
            if verdict == "contradicts"
        ]

        if to_invalidate:
            logger.info(
                f"[contradiction] {len(to_invalidate)}/{len(pairs)} existing "
                "edges will be invalidated as superseded"
            )
        return to_invalidate

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    def _existing_edges_between(
        self,
        session: Neo4jSession,
        graph_id: str,
        src_uuid: str,
        tgt_uuid: str,
    ) -> List[Dict]:
        """
        Return valid (not-yet-invalidated) edges between the given entity
        pair, in either direction — contradictions can flow both ways.
        """
        try:
            result = session.run(
                """
                MATCH (s:Entity {uuid: $src})-[r:RELATION]-(t:Entity {uuid: $tgt})
                WHERE r.graph_id = $gid AND r.invalid_at IS NULL
                RETURN r.uuid AS uuid, r.fact AS fact, r.name AS name
                LIMIT 10
                """,
                src=src_uuid, tgt=tgt_uuid, gid=graph_id,
            )
            return [dict(rec) for rec in result]
        except Exception as e:
            logger.debug(f"Existing-edge lookup failed: {e}")
            return []

    def _llm_adjudicate(self, pairs: List[Tuple[Dict, Dict]]) -> List[str]:
        """Batched LLM call. Returns a verdict per pair, aligned by index."""
        lines = []
        for i, (new_rel, existing) in enumerate(pairs, start=1):
            old_fact = str(existing.get("fact", "")).replace('"', "'")
            new_fact = str(new_rel.get("fact", "")).replace('"', "'")
            lines.append(f'{i}.')
            lines.append(f'   OLD: "{old_fact}"')
            lines.append(f'   NEW: "{new_fact}"')

        prompt = _ADJUDICATION_PROMPT.format(pairs_block="\n".join(lines))

        try:
            llm = self._llm_client()
            response = llm.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=512,
                repair_truncated=True,
            )
            raw = response.get("results", {}) if isinstance(response, dict) else {}
        except Exception as e:
            logger.warning(f"Contradiction LLM call failed, skipping invalidation: {e}")
            return ["not_contradicts"] * len(pairs)

        verdicts = []
        for i in range(1, len(pairs) + 1):
            v = str(raw.get(str(i), "not_contradicts")).strip().lower()
            verdicts.append("contradicts" if v == "contradicts" else "not_contradicts")
        return verdicts
