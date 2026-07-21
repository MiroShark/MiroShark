"""
ReasoningTrace — persist report-agent decision traces as Neo4j nodes.

Each report section becomes a traversable subgraph:

    (:Report)-[:HAS_SECTION]->(:ReportSection)-[:HAS_STEP]->(:ReasoningStep)

A :ReasoningStep.kind is one of:
    "thought"     — LLM-generated reasoning text before a tool call
    "tool_call"   — the agent invoked a tool (name + params captured)
    "observation" — the tool's output that fed the next iteration
    "conclusion"  — the final section content

This gives us:
  • Re-queryable reports ("why did the agent conclude X?")
  • Cross-report pattern mining ("did the agent keep missing Y?")
  • An audit trail alongside the :Community zoom-out layer

The recorder accumulates steps in memory per section and flushes to Neo4j at
section end — keeps the ReACT hot path fast and transactional.
"""

import json
import logging
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger('miroshark.reasoning_trace')


@dataclass
class _StepRecord:
    """In-memory buffer row before flush."""
    uuid: str
    step_index: int
    kind: str
    content: str
    iteration: int = 0
    tool_name: Optional[str] = None
    tool_params_json: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReasoningTraceRecorder:
    """
    Per-report buffer. Start a section, record steps, finalize (which flushes
    one section's rows to Neo4j atomically), move to the next section.

    Created fresh per report. Cheap to construct; the Report node isn't
    actually written until the first finalize_section() call.
    """

    def __init__(
        self,
        driver,
        graph_id: str,
        report_id: str,
        simulation_id: Optional[str],
        report_title: str,
    ):
        self._driver = driver
        self.graph_id = graph_id
        self.report_id = report_id
        self.simulation_id = simulation_id or ""
        self.report_title = report_title
        self._report_written = False
        self._current_section_uuid: Optional[str] = None
        self._current_section_index: int = 0
        self._current_section_title: str = ""
        self._buffer: List[_StepRecord] = []

    # ----------------------------------------------------------------
    # Public API — the report agent calls these
    # ----------------------------------------------------------------

    def start_section(self, title: str, index: int) -> str:
        """Begin buffering steps for a new section. Returns a section UUID."""
        # Flush any forgotten prior section (defensive, shouldn't normally happen).
        if self._buffer:
            self._flush_section(final_text=None)
        self._current_section_uuid = str(uuid_mod.uuid4())
        self._current_section_index = index
        self._current_section_title = title
        self._buffer = []
        return self._current_section_uuid

    def record_thought(self, iteration: int, content: str) -> None:
        self._append("thought", content, iteration=iteration)

    def record_tool_call(
        self, iteration: int, tool_name: str, params: Dict[str, Any]
    ) -> None:
        self._append(
            "tool_call",
            content=f"{tool_name}({json.dumps(params, ensure_ascii=False)})",
            iteration=iteration,
            tool_name=tool_name,
            tool_params_json=json.dumps(params, ensure_ascii=False),
        )

    def record_observation(self, iteration: int, content: str) -> None:
        # Tool outputs can be long — cap content length to keep Neo4j payloads sane.
        MAX_LEN = 6000
        if len(content) > MAX_LEN:
            content = content[:MAX_LEN] + f"\n...[{len(content) - MAX_LEN} more chars truncated]"
        self._append("observation", content, iteration=iteration)

    def finalize_section(self, final_text: str) -> None:
        """Write the conclusion step and flush everything to Neo4j."""
        self._append("conclusion", final_text or "", iteration=0)
        self._flush_section(final_text=final_text)
        self._current_section_uuid = None
        self._buffer = []

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------

    def _append(
        self,
        kind: str,
        content: str,
        iteration: int = 0,
        tool_name: Optional[str] = None,
        tool_params_json: Optional[str] = None,
    ) -> None:
        if self._current_section_uuid is None:
            logger.warning(
                "ReasoningTrace: record called outside a section — dropping step"
            )
            return
        self._buffer.append(_StepRecord(
            uuid=str(uuid_mod.uuid4()),
            step_index=len(self._buffer),
            kind=kind,
            content=content or "",
            iteration=iteration,
            tool_name=tool_name,
            tool_params_json=tool_params_json,
        ))

    def _ensure_report_node(self, session) -> None:
        if self._report_written:
            return
        session.run(
            """
            MERGE (r:Report {uuid: $rid})
            ON CREATE SET
                r.graph_id = $gid,
                r.simulation_id = $sid,
                r.title = $title,
                r.created_at = $now
            """,
            rid=self.report_id,
            gid=self.graph_id,
            sid=self.simulation_id,
            title=self.report_title,
            now=datetime.now(timezone.utc).isoformat(),
        )
        self._report_written = True

    def _flush_section(self, final_text: Optional[str]) -> None:
        """Write one section's steps to Neo4j in a single transaction."""
        if not self._buffer or not self._current_section_uuid:
            return

        section_uuid = self._current_section_uuid
        step_payload = [
            {
                "uuid": s.uuid,
                "step_index": s.step_index,
                "kind": s.kind,
                "content": s.content,
                "iteration": s.iteration,
                "tool_name": s.tool_name,
                "tool_params_json": s.tool_params_json,
                "timestamp": s.timestamp,
            }
            for s in self._buffer
        ]

        try:
            with self._driver.session() as session:
                self._ensure_report_node(session)
                session.run(
                    """
                    MATCH (r:Report {uuid: $rid})
                    CREATE (sec:ReportSection {
                        uuid: $sec_uuid,
                        graph_id: $gid,
                        report_id: $rid,
                        title: $title,
                        section_index: $idx,
                        final_text: $final_text,
                        created_at: $now
                    })
                    CREATE (r)-[:HAS_SECTION {index: $idx}]->(sec)
                    WITH sec
                    UNWIND $steps AS s
                    CREATE (st:ReasoningStep {
                        uuid: s.uuid,
                        graph_id: $gid,
                        section_id: $sec_uuid,
                        step_index: s.step_index,
                        kind: s.kind,
                        content: s.content,
                        iteration: s.iteration,
                        tool_name: s.tool_name,
                        tool_params_json: s.tool_params_json,
                        timestamp: s.timestamp
                    })
                    CREATE (sec)-[:HAS_STEP {index: s.step_index}]->(st)
                    """,
                    rid=self.report_id,
                    sec_uuid=section_uuid,
                    gid=self.graph_id,
                    title=self._current_section_title,
                    idx=self._current_section_index,
                    final_text=final_text or "",
                    now=datetime.now(timezone.utc).isoformat(),
                    steps=step_payload,
                )
            logger.info(
                f"[reasoning_trace] Flushed section {self._current_section_index} "
                f"'{self._current_section_title}' — {len(step_payload)} steps"
            )
        except Exception as e:
            logger.warning(f"[reasoning_trace] Flush failed: {e}")
