"""Simulation transcript renderer.

Turns a simulation's on-disk artifacts (``simulation_config.json``,
``trajectory.json``, ``quality.json``, ``resolution.json``,
``outcome.json``, ``reddit_profiles.json``) into a citable, readable
transcript in either Markdown (for Notion / Obsidian / Substack /
research papers) or JSON (for SDKs / pipelines).

Pairs with the share card and replay GIF as the third quote-friendly
share format — the static PNG covers preview, the animated GIF covers
motion, the transcript covers text. Until now the only way to quote a
simulation in prose was a screenshot.

Pure stdlib (json + io). Reads the same artifacts the embed summary,
share card, and gallery card already share, with the same ±0.2 stance
threshold so consensus labels stay consistent across the four surfaces.
"""

from __future__ import annotations

import io
import json
import os
from typing import Any, Optional


# Same threshold the embed-summary, share card, replay GIF, gallery
# card, and webhook all use — keep these surfaces in sync so an agent
# tagged "bullish" on the gallery is the same agent tagged "bullish"
# in the transcript.
STANCE_THRESHOLD = 0.2

# Per-post excerpt cap. Agent posts in MiroShark can be a few hundred
# characters. 400 keeps the round sections quotable as pull-quotes
# without truncating most posts; longer ones get the ellipsis.
POST_EXCERPT_CHARS = 400

# Cap rounds rendered in the markdown body. A 200-round simulation
# would produce a transcript no one reads. Past the cap, the rendered
# md keeps the first/last set + a "skipped N rounds" note so the
# document still reads cleanly. The JSON form keeps every round.
MAX_MD_ROUNDS = 80


# ── Stance helpers ─────────────────────────────────────────────────────────


def _classify_stance(value: float) -> str:
    """Bucket a continuous belief position into bullish/neutral/bearish.

    Mirrors the ±0.2 threshold used elsewhere — keeps the transcript's
    per-agent labels consistent with the gallery, share card, and
    webhook payloads.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if v > STANCE_THRESHOLD:
        return "bullish"
    if v < -STANCE_THRESHOLD:
        return "bearish"
    return "neutral"


def _avg_position(positions: dict | None) -> Optional[float]:
    """Mean of an agent's per-topic belief positions for one round.

    ``positions`` is a ``{topic: float}`` dict; we collapse to one
    scalar so the transcript can label the agent's stance without
    listing every topic.
    """
    if not positions:
        return None
    values = [float(v) for v in positions.values() if isinstance(v, (int, float))]
    if not values:
        return None
    return sum(values) / len(values)


# ── On-disk artifact loaders ──────────────────────────────────────────────


def _safe_load_json(path: str) -> Any:
    """Read a JSON file, returning ``None`` on missing/corrupt input.

    Never raises — every artifact except ``trajectory.json`` is
    optional, and a corrupt artifact must degrade the transcript
    rather than 500 the endpoint.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _load_profile_names(sim_dir: str) -> dict[int, str]:
    """``user_id → display name`` lookup for the simulation's agents.

    Reads ``reddit_profiles.json`` first (every run produces it), then
    ``polymarket_profiles.json`` as a secondary source (some runs add
    polymarket-only personas). Each profile has ``user_id`` (int) and a
    ``name`` field; we coerce both, skip malformed rows, and merge
    additively so a polymarket-only id can resolve even when the same
    ``user_id`` is missing from reddit_profiles.
    """
    out: dict[int, str] = {}
    for filename in ("reddit_profiles.json", "polymarket_profiles.json"):
        data = _safe_load_json(os.path.join(sim_dir, filename))
        if not isinstance(data, list):
            continue
        for row in data:
            if not isinstance(row, dict):
                continue
            uid_raw = row.get("user_id")
            try:
                uid = int(uid_raw)
            except (TypeError, ValueError):
                continue
            name = (row.get("name") or row.get("username") or "").strip()
            if not name:
                continue
            # First-write wins so reddit_profiles takes precedence — it
            # carries the canonical display name on every run.
            out.setdefault(uid, name)
    return out


def _excerpt(text: str, limit: int = POST_EXCERPT_CHARS) -> str:
    """Trim a post to ``limit`` chars with a single-character ellipsis.

    Trims at a word boundary when one is within 30 chars of the cap so
    we don't end mid-word; falls back to a hard cut otherwise.
    """
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    space = cut.rfind(" ")
    if space >= limit - 30:
        cut = cut[:space]
    return cut.rstrip().rstrip(",.;:—-") + "…"


# ── Round assembly ────────────────────────────────────────────────────────


def _round_stance_split(snapshot: dict) -> dict:
    """Compute the round's bullish/neutral/bearish percent split.

    Same algorithm the embed-summary endpoint runs over the full
    trajectory — average each agent's per-topic positions, bucket on
    ±0.2, return percentages.
    """
    positions = snapshot.get("belief_positions") or {}
    stances = []
    for agent_positions in positions.values():
        avg = _avg_position(agent_positions)
        if avg is not None:
            stances.append(avg)
    total = len(stances)
    if total == 0:
        return {"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}
    n_bull = sum(1 for s in stances if s > STANCE_THRESHOLD)
    n_bear = sum(1 for s in stances if s < -STANCE_THRESHOLD)
    n_neut = total - n_bull - n_bear
    return {
        "bullish": round(n_bull / total * 100, 1),
        "neutral": round(n_neut / total * 100, 1),
        "bearish": round(n_bear / total * 100, 1),
    }


def _build_round(snapshot: dict, profile_names: dict[int, str]) -> dict:
    """Project one trajectory snapshot into a transcript round entry."""
    round_num = int(snapshot.get("round_num", 0) or 0)
    positions = snapshot.get("belief_positions") or {}

    # Per-agent stance map — keyed by str so it lines up with the
    # ``user_id`` on viral_posts (which json.load deserializes as int).
    agent_stance: dict[int, tuple[str, float]] = {}
    for agent_id_str, agent_positions in positions.items():
        try:
            agent_id = int(agent_id_str)
        except (TypeError, ValueError):
            continue
        avg = _avg_position(agent_positions)
        if avg is None:
            continue
        agent_stance[agent_id] = (_classify_stance(avg), round(avg, 3))

    posts: list[dict] = []
    for vp in snapshot.get("viral_posts") or []:
        if not isinstance(vp, dict):
            continue
        try:
            user_id = int(vp.get("user_id"))
        except (TypeError, ValueError):
            continue
        content = (vp.get("content") or "").strip()
        if not content:
            continue
        stance, stance_val = agent_stance.get(user_id, ("neutral", 0.0))
        posts.append(
            {
                "post_id": vp.get("post_id"),
                "agent_id": user_id,
                "agent_name": profile_names.get(user_id, f"Agent {user_id}"),
                "stance": stance,
                "stance_value": stance_val,
                "content": _excerpt(content),
                "likes": int(vp.get("num_likes") or 0),
                "dislikes": int(vp.get("num_dislikes") or 0),
            }
        )

    return {
        "round": round_num,
        "timestamp": (snapshot.get("timestamp") or "").strip(),
        "total_posts": int(snapshot.get("total_posts_created") or 0),
        "total_engagements": int(snapshot.get("total_engagements") or 0),
        "active_agent_count": int(snapshot.get("active_agent_count") or 0),
        "stance_split": _round_stance_split(snapshot),
        "posts": posts,
    }


# ── Outcome helpers (mirrors api/simulation._read_outcome_file) ───────────


_VALID_OUTCOME_LABELS = ("correct", "incorrect", "partial")


def _load_outcome(sim_dir: str) -> Optional[dict]:
    """Load + sanitize ``outcome.json`` exactly like the gallery does.

    Re-implemented (rather than imported) so the transcript service
    has no dependency on ``api/simulation``; keeps the import graph
    one-way (api → service, never the other way).
    """
    data = _safe_load_json(os.path.join(sim_dir, "outcome.json"))
    if not isinstance(data, dict):
        return None
    label = (data.get("label") or "").strip().lower()
    if label not in _VALID_OUTCOME_LABELS:
        return None
    summary = (data.get("outcome_summary") or "").strip()
    if len(summary) > 280:
        summary = summary[:277].rstrip() + "…"
    url = (data.get("outcome_url") or "").strip()
    if url and not (url.startswith("http://") or url.startswith("https://")):
        url = ""
    return {
        "label": label,
        "outcome_url": url,
        "outcome_summary": summary,
        "submitted_at": data.get("submitted_at") or "",
    }


# ── Top-level builders ────────────────────────────────────────────────────


def build_transcript_data(summary: dict, sim_dir: str) -> dict:
    """Assemble the full transcript payload from the embed summary +
    on-disk artifacts.

    The ``summary`` arg is the same dict ``_build_embed_summary_payload``
    produces — caller is responsible for the ``is_public`` gate before
    invoking this. ``sim_dir`` is the canonical simulation directory
    (``WONDERWALL_SIMULATION_DATA_DIR/<simulation_id>``).

    Returns a JSON-serializable dict — the markdown renderer reads from
    it directly, and the JSON endpoint emits it as-is.
    """
    profile_names = _load_profile_names(sim_dir)

    rounds: list[dict] = []
    trajectory = _safe_load_json(os.path.join(sim_dir, "trajectory.json")) or {}
    snapshots = trajectory.get("snapshots") or []
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        rounds.append(_build_round(snap, profile_names))

    belief = summary.get("belief") or {}
    final = belief.get("final") or {}
    consensus = {
        "bullish": float(final.get("bullish") or 0.0),
        "neutral": float(final.get("neutral") or 0.0),
        "bearish": float(final.get("bearish") or 0.0),
        "round": belief.get("consensus_round"),
        "label": belief.get("consensus_stance"),
    }
    # Derive a final-stance label even when no >50% threshold was
    # crossed, so the transcript header always carries a one-word call.
    if not consensus["label"]:
        if consensus["bullish"] >= consensus["bearish"] and consensus["bullish"] >= consensus["neutral"]:
            consensus["label"] = "bullish"
        elif consensus["bearish"] >= consensus["bullish"] and consensus["bearish"] >= consensus["neutral"]:
            consensus["label"] = "bearish"
        else:
            consensus["label"] = "neutral"

    quality = summary.get("quality") or {}
    resolution = summary.get("resolution") or {}
    outcome = _load_outcome(sim_dir)

    return {
        "sim_id": summary.get("simulation_id") or "",
        "scenario": (summary.get("scenario") or "").strip(),
        "created_date": summary.get("created_date") or "",
        "agent_count": int(summary.get("profiles_count") or 0),
        "total_rounds": int(summary.get("total_rounds") or len(rounds)),
        "rounds_recorded": len(rounds),
        "consensus": consensus,
        "quality": {
            "health": quality.get("health"),
            "participation_rate": quality.get("participation_rate"),
        },
        "resolution": resolution if any(resolution.values()) else None,
        "outcome": outcome,
        "rounds": rounds,
    }


# ── Markdown renderer ─────────────────────────────────────────────────────


_LABEL_ICON = {
    "correct": "📍",
    "partial": "◑",
    "incorrect": "⚠",
}


def _md_yaml_value(value: Any) -> str:
    """Quote-safe, single-line YAML scalar for the front-matter block.

    Wraps strings in double quotes (escaping internal double quotes +
    backslashes) and falls through scalars unchanged.
    """
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    # YAML scalars in our output are always single-line — strip newlines
    # so an embedded one in scenario doesn't break the front matter.
    s = s.replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


def _md_pct_line(split: dict) -> str:
    return (
        f"🔵 {split.get('bullish', 0.0):.1f}% Bullish · "
        f"⚪ {split.get('neutral', 0.0):.1f}% Neutral · "
        f"🔴 {split.get('bearish', 0.0):.1f}% Bearish"
    )


def _md_outcome_line(outcome: Optional[dict]) -> Optional[str]:
    if not outcome:
        return None
    icon = _LABEL_ICON.get(outcome["label"], "•")
    pieces = [f"{icon} **{outcome['label'].capitalize()}**"]
    if outcome.get("outcome_summary"):
        pieces.append(f"— {outcome['outcome_summary']}")
    if outcome.get("outcome_url"):
        pieces.append(f"([source]({outcome['outcome_url']}))")
    return " ".join(pieces)


def _md_resolution_line(resolution: Optional[dict]) -> Optional[str]:
    if not resolution:
        return None
    actual = resolution.get("actual_outcome")
    predicted = resolution.get("predicted_consensus")
    score = resolution.get("accuracy_score")
    if actual is None and predicted is None and score is None:
        return None
    bits = []
    if predicted:
        bits.append(f"predicted **{predicted}**")
    if actual:
        bits.append(f"actual **{actual}**")
    if isinstance(score, (int, float)):
        bits.append(f"accuracy **{score:.2f}**")
    return "Polymarket resolution: " + " · ".join(bits) if bits else None


def _select_md_rounds(rounds: list[dict]) -> tuple[list[dict], int]:
    """Pick which rounds to render in the markdown body.

    Returns ``(rounds_to_render, skipped_count)``. Under the cap we
    render every round; over the cap we keep the first 20 and last 20
    so the header build-up and the resting consensus both stay legible,
    and the gap is annotated in the body.
    """
    if len(rounds) <= MAX_MD_ROUNDS:
        return rounds, 0
    head = rounds[:20]
    tail = rounds[-20:]
    skipped = len(rounds) - len(head) - len(tail)
    return head + tail, skipped


def _render_markdown_round(round_data: dict, lines: list[str]) -> None:
    """Append a `## Round N` block to ``lines``."""
    rn = round_data["round"]
    split = round_data.get("stance_split") or {}
    lines.append(f"## Round {rn}")
    meta_bits = []
    if round_data.get("active_agent_count"):
        meta_bits.append(f"{round_data['active_agent_count']} agents active")
    if round_data.get("total_posts"):
        meta_bits.append(f"{round_data['total_posts']} posts")
    if round_data.get("total_engagements"):
        meta_bits.append(f"{round_data['total_engagements']} engagements")
    if meta_bits:
        lines.append(f"*{' · '.join(meta_bits)}*")
    lines.append("")
    lines.append(f"**Stance split:** {_md_pct_line(split)}")
    lines.append("")

    posts = round_data.get("posts") or []
    if not posts:
        lines.append("*No notable posts this round.*")
        lines.append("")
        return

    for post in posts:
        stance = post.get("stance", "neutral")
        name = post.get("agent_name") or f"Agent {post.get('agent_id', '?')}"
        lines.append(f"### {name} — *{stance}*")
        # Block-quote each line of the post so multi-line content stays
        # in the quote. Single-line posts are the common case but agents
        # do occasionally produce paragraph breaks.
        body = (post.get("content") or "").strip() or "*(empty post)*"
        for body_line in body.splitlines() or [body]:
            lines.append(f"> {body_line}")
        engagement = []
        if post.get("likes"):
            engagement.append(f"❤ {post['likes']}")
        if post.get("dislikes"):
            engagement.append(f"✗ {post['dislikes']}")
        if engagement:
            lines.append(f"> *— {' · '.join(engagement)}*")
        lines.append("")


def render_markdown(data: dict) -> str:
    """Render the transcript payload as Markdown.

    Layout:

      - YAML front-matter so Notion / Obsidian / Bear pick up the
        scenario, sim_id, agent count, etc. as metadata.
      - Header (scenario, run summary, consensus, outcome, resolution).
      - One ``## Round N`` block per round.
      - Trailing ``## Consensus`` block restating the final state +
        ``--- ` separator + footer link back to the SPA.
    """
    sim_id = data.get("sim_id") or ""
    scenario = data.get("scenario") or ""
    rounds = data.get("rounds") or []
    consensus = data.get("consensus") or {}
    outcome = data.get("outcome")
    resolution = data.get("resolution")
    quality = data.get("quality") or {}

    lines: list[str] = []

    # ── Front matter ────────────────────────────────────────────────
    lines.append("---")
    lines.append(f"sim_id: {_md_yaml_value(sim_id)}")
    lines.append(f"scenario: {_md_yaml_value(scenario)}")
    lines.append(f"agent_count: {_md_yaml_value(data.get('agent_count') or 0)}")
    lines.append(f"total_rounds: {_md_yaml_value(data.get('total_rounds') or 0)}")
    lines.append(f"rounds_recorded: {_md_yaml_value(data.get('rounds_recorded') or 0)}")
    lines.append(f"created_date: {_md_yaml_value(data.get('created_date') or '')}")
    lines.append(f"consensus_label: {_md_yaml_value(consensus.get('label') or '')}")
    if consensus.get("round") is not None:
        lines.append(f"consensus_round: {_md_yaml_value(consensus['round'])}")
    if quality.get("health"):
        lines.append(f"quality_health: {_md_yaml_value(quality['health'])}")
    if outcome and outcome.get("label"):
        lines.append(f"outcome_label: {_md_yaml_value(outcome['label'])}")
    lines.append("source: MiroShark")
    lines.append("---")
    lines.append("")

    # ── Header ──────────────────────────────────────────────────────
    lines.append("# MiroShark Simulation Transcript")
    lines.append("")
    if scenario:
        lines.append(f"**Scenario.** {scenario}")
        lines.append("")

    run_bits: list[str] = []
    ac = data.get("agent_count") or 0
    if ac:
        run_bits.append(f"{ac} agents")
    tr = data.get("total_rounds") or 0
    if tr:
        run_bits.append(f"{tr} rounds")
    if data.get("created_date"):
        run_bits.append(f"created {data['created_date']}")
    if run_bits:
        lines.append(f"**Run.** {' · '.join(run_bits)}")
        lines.append("")

    lines.append(
        f"**Final consensus.** {_md_pct_line(consensus)}"
        + (f" — **{consensus['label']}**" if consensus.get("label") else "")
    )
    if consensus.get("round") is not None:
        lines.append("")
        lines.append(f"*Threshold crossed at round {consensus['round']}.*")
    lines.append("")

    if quality.get("health"):
        q_pieces = [f"**{quality['health']}**"]
        pr = quality.get("participation_rate")
        if isinstance(pr, (int, float)):
            q_pieces.append(f"({pr * 100:.0f}% participation)")
        lines.append(f"**Quality.** {' '.join(q_pieces)}")
        lines.append("")

    res_line = _md_resolution_line(resolution)
    if res_line:
        lines.append(f"**{res_line}**")
        lines.append("")

    out_line = _md_outcome_line(outcome)
    if out_line:
        lines.append(f"**Verified outcome.** {out_line}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── Rounds ──────────────────────────────────────────────────────
    if not rounds:
        lines.append("*No round snapshots recorded yet — the simulation has")
        lines.append("been published but the runner hasn't completed any rounds.*")
        lines.append("")
    else:
        rendered_rounds, skipped = _select_md_rounds(rounds)
        head_count = min(20, len(rendered_rounds)) if skipped else len(rendered_rounds)
        for idx, rd in enumerate(rendered_rounds):
            if skipped and idx == head_count:
                lines.append("---")
                lines.append("")
                lines.append(
                    f"*({skipped} middle rounds omitted from this Markdown view "
                    f"to keep the document readable. The full per-round series "
                    f"is available in the JSON form: ``GET /api/simulation/{sim_id}/transcript.json``)*"
                )
                lines.append("")
                lines.append("---")
                lines.append("")
            _render_markdown_round(rd, lines)

    # ── Footer ──────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## Consensus")
    lines.append("")
    lines.append(
        f"**Final split:** {_md_pct_line(consensus)}"
        + (f" — **{consensus['label']}**" if consensus.get("label") else "")
    )
    lines.append("")
    if consensus.get("round") is not None:
        lines.append(f"**Threshold crossed:** round {consensus['round']}.")
        lines.append("")
    if quality.get("health"):
        lines.append(f"**Quality health:** {quality['health']}.")
        lines.append("")
    if res_line:
        lines.append(res_line + ".")
        lines.append("")
    if out_line:
        lines.append(f"**Verified outcome.** {out_line}")
        lines.append("")
    if sim_id:
        lines.append(f"*Source: [`/share/{sim_id}`](/share/{sim_id}) · "
                     f"[gallery](/explore) · [verified](/verified) · "
                     f"transcript built from MiroShark on-disk artifacts.*")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ── Encoded byte-output helpers (route layer expects bytes) ───────────────


def render_markdown_bytes(data: dict) -> bytes:
    return render_markdown(data).encode("utf-8")


def render_json_bytes(data: dict) -> bytes:
    """JSON form — pretty-printed (indent=2) so a curl into a file is
    immediately readable. Sorting is left in payload order so rounds
    stay chronological."""
    buf = io.StringIO()
    json.dump(data, buf, ensure_ascii=False, indent=2)
    return buf.getvalue().encode("utf-8")
