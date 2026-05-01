"""Belief trajectory export — CSV + JSONL renderers.

Turns ``trajectory.json`` (one snapshot per round, with per-agent
``belief_positions`` + per-round counters) into the analyst's default
serialization formats: a CSV that ``pandas.read_csv()`` / Excel /
Tableau / R / Observable consume directly, and a JSON-lines stream for
pipeline ingest.

Pairs with the share card (preview / PNG), the replay GIF (motion),
and the transcript (Markdown + JSON prose) as the **fifth** export
surface — the previous four cover the *qualitative* read of a
simulation; this one covers the *quantitative* one. ``transcript.json``
is what the LLM-as-judge pipelines parse for reasoning quality;
``trajectory.csv`` is what a quant researcher loads into a notebook to
compute variance, autocorrelation, or compare across runs.

Pure stdlib (``csv`` + ``io`` + ``json``). Reads the same on-disk
artifacts the embed-summary, share-card, replay-GIF, gallery card,
webhook, transcript, and Atom/RSS feeds already share — same ±0.2
stance threshold, so a "bullish" percentage in the trajectory matches
a "bullish" percentage on every other surface for the same round.
"""

from __future__ import annotations

import csv
import io
import json
import os
from typing import Any, Optional


# Same threshold the embed-summary, share card, replay GIF, gallery
# card, webhook, transcript, and feed renderers all use. Per-round
# bullish/neutral/bearish percentages here MUST stay consistent with
# what those surfaces report for the same simulation, otherwise an
# analyst comparing the CSV to the share card would see drift.
STANCE_THRESHOLD = 0.2


# Field order for the CSV header + JSONL key order. Locked because
# ``pandas.read_csv()`` consumers index by column name and downstream
# pipelines key on the JSONL field names — adding a new column at the
# end is fine, reordering breaks consumers.
CSV_COLUMNS: tuple[str, ...] = (
    "round",
    "round_timestamp",
    "bullish_pct",
    "neutral_pct",
    "bearish_pct",
    "participating_agents",
    "total_posts",
    "total_engagements",
    "quality_health",
    "participation_rate",
)


# ── On-disk readers ────────────────────────────────────────────────────────


def _safe_load_json(path: str) -> Any:
    """Read JSON, returning ``None`` on missing / corrupt input.

    Never raises — the route handler must produce a (possibly empty)
    feed rather than a 500 when an artifact is malformed on disk.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# ── Stance computation ────────────────────────────────────────────────────


def _avg_position(positions: dict | None) -> Optional[float]:
    """Mean of an agent's per-topic belief positions for one round.

    The per-topic dict can be empty or contain non-numeric values when
    a snapshot is mid-write; we filter those out and return ``None`` if
    no usable values remain.
    """
    if not positions:
        return None
    values = [
        float(v)
        for v in positions.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not values:
        return None
    return sum(values) / len(values)


def compute_stance_split(
    belief_positions: dict | None,
    threshold: float = STANCE_THRESHOLD,
) -> dict[str, float]:
    """Bucket per-agent belief positions into bullish/neutral/bearish %.

    ``belief_positions`` is the snapshot field: ``{agent_id: {topic: float}}``.
    Each agent's per-topic positions are averaged into a single scalar,
    then bucketed against ``±threshold``.

    Returns ``{"bullish": pct, "neutral": pct, "bearish": pct}`` with
    each percentage rounded to one decimal place. Empty input returns
    all zeros so the row can still be emitted (downstream consumers
    expect a constant column count).
    """
    if not belief_positions:
        return {"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}

    stances: list[float] = []
    for agent_positions in belief_positions.values():
        avg = _avg_position(agent_positions)
        if avg is not None:
            stances.append(avg)

    total = len(stances)
    if total == 0:
        return {"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}

    n_bull = sum(1 for s in stances if s > threshold)
    n_bear = sum(1 for s in stances if s < -threshold)
    n_neut = total - n_bull - n_bear
    return {
        "bullish": round(n_bull / total * 100, 1),
        "neutral": round(n_neut / total * 100, 1),
        "bearish": round(n_bear / total * 100, 1),
    }


# ── Row assembly ───────────────────────────────────────────────────────────


def _participating_agents(snapshot: dict) -> int:
    """Count agents that posted at least once in this round.

    ``active_agent_count`` is the runner's recorded headline number;
    we prefer the ``viral_posts`` set count when both are present and
    diverge, since the post set is what an analyst would reproduce
    from the same trajectory file.
    """
    posts = snapshot.get("viral_posts") or []
    posters: set[int] = set()
    if isinstance(posts, list):
        for vp in posts:
            if not isinstance(vp, dict):
                continue
            try:
                posters.add(int(vp.get("user_id")))
            except (TypeError, ValueError):
                continue
    if posters:
        return len(posters)
    # Fall back to the snapshot's recorded active_agent_count when
    # viral_posts is empty — a "no posts" round still has agents
    # holding positions.
    try:
        return int(snapshot.get("active_agent_count") or 0)
    except (TypeError, ValueError):
        return 0


def _row_from_snapshot(
    snapshot: dict,
    quality_health: str,
    participation_rate: Optional[float],
) -> Optional[dict[str, Any]]:
    """Project one trajectory snapshot into one CSV / JSONL row.

    Returns ``None`` for snapshots that aren't usable as analyst rows
    (missing round number, no belief data); the route handler skips
    those so the resulting file has only well-formed rows.
    """
    if not isinstance(snapshot, dict):
        return None

    raw_round = snapshot.get("round_num")
    try:
        round_num = int(raw_round)
    except (TypeError, ValueError):
        return None

    split = compute_stance_split(snapshot.get("belief_positions"))

    timestamp = (snapshot.get("timestamp") or "").strip()

    try:
        total_posts = int(snapshot.get("total_posts_created") or 0)
    except (TypeError, ValueError):
        total_posts = 0
    try:
        total_engagements = int(snapshot.get("total_engagements") or 0)
    except (TypeError, ValueError):
        total_engagements = 0

    return {
        "round": round_num,
        "round_timestamp": timestamp,
        "bullish_pct": split["bullish"],
        "neutral_pct": split["neutral"],
        "bearish_pct": split["bearish"],
        "participating_agents": _participating_agents(snapshot),
        "total_posts": total_posts,
        "total_engagements": total_engagements,
        "quality_health": quality_health,
        "participation_rate": (
            round(participation_rate, 4)
            if isinstance(participation_rate, (int, float))
            else ""
        ),
    }


def build_rows(sim_dir: str) -> list[dict[str, Any]]:
    """Read sim_dir on-disk artifacts and return the analyst row list.

    Reads ``trajectory.json`` (required — empty list when missing) and
    ``quality.json`` (optional; the ``health`` + ``participation_rate``
    fields are repeated on every row so a single row from the CSV is
    self-describing without a separate join).
    """
    quality = _safe_load_json(os.path.join(sim_dir, "quality.json")) or {}
    quality_health = (quality.get("health") or "").strip() if isinstance(quality, dict) else ""
    pr_raw = quality.get("participation_rate") if isinstance(quality, dict) else None
    if isinstance(pr_raw, (int, float)):
        participation_rate: Optional[float] = float(pr_raw)
    else:
        participation_rate = None

    trajectory = _safe_load_json(os.path.join(sim_dir, "trajectory.json")) or {}
    snapshots = trajectory.get("snapshots") if isinstance(trajectory, dict) else None
    if not isinstance(snapshots, list):
        return []

    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        row = _row_from_snapshot(snap, quality_health, participation_rate)
        if row is not None:
            rows.append(row)

    # Chronological order (snapshots are appended in round order on
    # disk; we re-sort defensively in case a runner ever writes them
    # out of order — the analyst pulling df.iloc[-1] expects the
    # final round at the bottom of the file).
    rows.sort(key=lambda r: r["round"])
    return rows


# ── Renderers ──────────────────────────────────────────────────────────────


def render_csv(rows: list[dict[str, Any]]) -> bytes:
    """Render the row list as RFC 4180 CSV with the locked header.

    Uses ``csv.DictWriter`` with ``QUOTE_MINIMAL`` so numeric columns
    stay unquoted (``pd.read_csv()`` infers dtype correctly without a
    converters argument). Empty trajectories still emit the header row
    so downstream consumers don't have to special-case them.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=list(CSV_COLUMNS),
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def render_jsonl(rows: list[dict[str, Any]]) -> bytes:
    """Render the row list as JSON-lines (newline-delimited JSON).

    One JSON object per line — the format ``pandas.read_json(lines=True)``,
    DuckDB ``read_json_auto``, and most stream-processing pipelines
    consume natively. Empty input yields zero bytes; the route handler
    still serves the right content type so a curl into a file produces
    an empty but well-formed JSONL document.
    """
    buf = io.StringIO()
    for row in rows:
        # Filter to the canonical column list so an upstream change to
        # ``_row_from_snapshot`` can't accidentally leak unstable keys
        # into the JSONL stream.
        ordered = {col: row.get(col, "") for col in CSV_COLUMNS}
        buf.write(json.dumps(ordered, ensure_ascii=False))
        buf.write("\n")
    return buf.getvalue().encode("utf-8")
