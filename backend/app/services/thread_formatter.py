"""Twitter / X tweet thread formatter for a finished simulation.

Pairs with ``share_card`` (preview / PNG), ``replay_gif`` (motion),
``transcript`` (prose), and ``trajectory_export`` (data) as the **sixth**
share format over the same on-disk ``sim_dir/`` substrate. Where the
prior five surfaces are visual / motion / prose / data, this one covers
short-form text — the format Aaron's primary distribution channel
(X/Twitter) speaks natively.

Today, posting a simulation result to X means manually reading the
replay GIF and the transcript, then writing 8–12 tweets ≤280 chars each.
This service generates the thread automatically from data already on
disk: one intro tweet (scenario summary + consensus label), one tweet
per *belief inflection point* (rounds where the dominant stance crosses
the ±0.2 threshold in either direction — the dramatic moments), and one
closing tweet (final verdict + share link + watch link).

Pure stdlib (``json`` + ``os``). Reads the same artefacts the embed
summary, share card, replay GIF, gallery card, webhook, transcript,
trajectory export, and Atom/RSS feeds already share — same ±0.2 stance
threshold so a "bullish" pct in the thread matches a "bullish" pct
on every other surface for the same round.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from ..utils.belief import avg_position as _avg_position
from ..utils.json_io import safe_load_json as _safe_load_json


# Same threshold the embed-summary, share card, replay GIF, gallery
# card, webhook, transcript, trajectory CSV, and feed renderers all
# use. The inflection-point detection here applies the same rule —
# otherwise the thread's "stance shifted" tweets wouldn't line up with
# the bars a viewer sees on the share card unfurl moments earlier.
STANCE_THRESHOLD = 0.2

# X/Twitter's hard cap — every tweet in the thread must fit under this
# or the operator can't paste it directly. The composer kept just under
# at 270 chars so a paste-and-add-emoji edit doesn't blow the limit.
MAX_TWEET_CHARS = 280

# Soft cap on the thread length. A 200-round simulation might have
# dozens of inflection points; 15 is the practical limit for a thread
# someone will actually read on X. Past the cap, we keep the first 3
# and last 3 inflections with a single "… N more flips …" bridge.
MAX_THREAD_TWEETS = 15

# How many inflection points we keep at each end when truncating. The
# first ones tell the build-up story; the last ones tell how the
# resting consensus formed.
TRUNCATED_HEAD_TAIL = 3


# ── Stance computation ────────────────────────────────────────────────────


def _round_stance_split(snapshot: dict) -> dict[str, float]:
    """Compute a round's bullish / neutral / bearish percent split.

    Same algorithm the share card and trajectory CSV use, applied to a
    single snapshot. Empty snapshots return all-zero so a downstream
    consumer always gets a complete dict.
    """
    positions = snapshot.get("belief_positions") or {}
    stances: list[float] = []
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


def dominant_stance(split: dict[str, float]) -> Optional[str]:
    """Pick the dominant stance label from a split — or ``None``.

    Returns ``"bullish"`` / ``"neutral"`` / ``"bearish"`` when one stance
    leads the runner-up by ≥0.2pp (the same hysteresis ``gallery_filters``
    uses to suppress noise on near-ties). Returns ``None`` on a flat
    split so we don't emit "stance shifted to neutral" tweets for every
    round of a balanced simulation.
    """
    if not split:
        return None
    items = sorted(
        (("bullish", split.get("bullish", 0.0)),
         ("neutral", split.get("neutral", 0.0)),
         ("bearish", split.get("bearish", 0.0))),
        key=lambda kv: (-kv[1], kv[0]),
    )
    top_label, top_pct = items[0]
    runner_up_pct = items[1][1]
    if top_pct - runner_up_pct < 0.2:
        return None
    if top_pct <= 0.0:
        return None
    return top_label


def _build_round_series(sim_dir: str) -> list[dict]:
    """Project the on-disk trajectory into a per-round series.

    Each entry has ``round``, ``split`` (the bullish / neutral / bearish
    %), and ``dominant`` (the stance label or ``None`` on a flat
    distribution). The series is sorted by round number so a snapshot
    file written out-of-order still produces a stable inflection
    sequence.
    """
    trajectory = _safe_load_json(os.path.join(sim_dir, "trajectory.json")) or {}
    snapshots = trajectory.get("snapshots") or []

    rows: list[dict] = []
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        try:
            round_num = int(snap.get("round_num", 0) or 0)
        except (TypeError, ValueError):
            continue
        split = _round_stance_split(snap)
        rows.append(
            {
                "round": round_num,
                "split": split,
                "dominant": dominant_stance(split),
            }
        )

    rows.sort(key=lambda r: r["round"])
    return rows


def find_inflection_points(rows: list[dict]) -> list[dict]:
    """Return the rounds where the dominant stance changed.

    An inflection is a round whose ``dominant`` label differs from the
    most recent *non-None* dominant label seen in earlier rounds. The
    very first round with a non-None dominant is itself an inflection
    (it introduces the first stance), so the thread always opens with
    a labelled bar reading instead of an empty "neutral" tweet.

    Flat / no-dominant rounds are skipped — they're noise on a
    short-form text channel.
    """
    inflections: list[dict] = []
    last_label: Optional[str] = None
    for row in rows:
        label = row["dominant"]
        if label is None:
            continue
        if last_label is None or label != last_label:
            inflections.append(row)
            last_label = label
    return inflections


# ── Tweet composition ─────────────────────────────────────────────────────


_STANCE_GLYPH = {
    "bullish": "↑",
    "neutral": "→",
    "bearish": "↓",
}

_STANCE_LABEL = {
    "bullish": "Bullish",
    "neutral": "Neutral",
    "bearish": "Bearish",
}


def _format_pct(value: float) -> str:
    """Match the share card's percentage formatting — integer when the
    value rounds cleanly, one decimal otherwise. Keeps the thread's
    numbers aligned with what a reader sees on the share card image."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "0%"
    rounded = round(n)
    if abs(n - rounded) < 0.05:
        return f"{int(rounded)}%"
    return f"{n:.1f}".rstrip("0").rstrip(".") + "%"


def _format_stance_line(split: dict[str, float]) -> str:
    """One-line ``↑ Bullish X% · → Neutral Y% · ↓ Bearish Z%`` summary.

    ASCII arrows (no emoji) so the thread copy-pastes cleanly into
    research write-ups, Slack channels with limited emoji renderers,
    and accessibility tools.
    """
    return (
        f"{_STANCE_GLYPH['bullish']} Bullish {_format_pct(split.get('bullish', 0.0))} · "
        f"{_STANCE_GLYPH['neutral']} Neutral {_format_pct(split.get('neutral', 0.0))} · "
        f"{_STANCE_GLYPH['bearish']} Bearish {_format_pct(split.get('bearish', 0.0))}"
    )


def _truncate(text: str, max_chars: int) -> str:
    """Trim ``text`` so the result is at most ``max_chars`` characters,
    preferring a word boundary within the last 30 characters of the
    cap and ending with a single ``…``.
    """
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    cut = s[: max_chars - 1]
    space = cut.rfind(" ")
    if space >= max_chars - 30:
        cut = cut[:space]
    return cut.rstrip().rstrip(",.;:—-") + "…"


def _truncate_to_tweet(text: str) -> str:
    """Trim ``text`` to ``MAX_TWEET_CHARS`` with the ellipsis convention
    above. Public seam used by the composer + tested directly so
    drift on the cap is caught immediately.
    """
    return _truncate(text, MAX_TWEET_CHARS)


def _final_consensus_label(consensus: dict | None) -> str:
    """Plain-language label for the final consensus split.

    Prefers the ``label`` field already computed by the embed-summary
    pipeline; falls back to the dominant-stance computation when the
    label is missing (e.g. a corrupt artifact). Returns ``"split"`` for
    a flat distribution so the close-tweet copy doesn't read "Final:
    None".
    """
    if not isinstance(consensus, dict):
        return "split"
    label = (consensus.get("label") or "").strip().lower()
    if label in {"bullish", "neutral", "bearish"}:
        return label
    derived = dominant_stance(
        {
            "bullish": float(consensus.get("bullish") or 0.0),
            "neutral": float(consensus.get("neutral") or 0.0),
            "bearish": float(consensus.get("bearish") or 0.0),
        }
    )
    return derived or "split"


def _intro_tweet(
    scenario: str,
    total_rounds: int,
    agent_count: int,
    consensus_label: str,
) -> str:
    """Open the thread with the scenario, scale, and current consensus.

    The thread numbering ``1/`` is intentionally added at the end so the
    operator can paste each tweet 1:1 into X's compose box — X auto-
    threads when each tweet starts with the prior tweet's number, but
    the leading ``1/`` lets readers count even if they only see one
    tweet in their feed.
    """
    parts: list[str] = []
    if scenario:
        # Reserve room for the metadata footer + numbering — 280 minus
        # the longest possible footer keeps the scenario quote intact
        # for the common case.
        scenario_cap = MAX_TWEET_CHARS - 80
        parts.append(_truncate(scenario, scenario_cap))

    metadata_bits: list[str] = []
    if total_rounds > 0:
        metadata_bits.append(f"{total_rounds} rounds")
    if agent_count > 0:
        metadata_bits.append(f"{agent_count} agents")
    metadata = " · ".join(metadata_bits)

    consensus_line = (
        f"Consensus: {_STANCE_LABEL.get(consensus_label, consensus_label.capitalize())}"
        if consensus_label and consensus_label != "split"
        else "Consensus: split"
    )

    body_lines: list[str] = []
    if metadata:
        body_lines.append(metadata)
    body_lines.append(consensus_line)
    body_lines.append("1/")

    composed = "\n\n".join(parts + ["\n".join(body_lines)]) if parts else "\n".join(body_lines)
    return _truncate_to_tweet(composed)


def _inflection_tweet(row: dict) -> str:
    """One tweet per dominant-stance flip.

    Format: ``"Round N: stance shifted to <label>\n<stance line>"``.
    Stays well under 280 characters even with three-digit round numbers
    and the longest stance label.
    """
    label = row.get("dominant") or "neutral"
    line_a = f"Round {int(row['round'])}: stance shifted to {label}"
    line_b = _format_stance_line(row.get("split") or {})
    return _truncate_to_tweet(f"{line_a}\n{line_b}")


def _bridge_tweet(skipped_count: int) -> str:
    """Single-line bridge between the head and tail inflections when the
    thread would otherwise exceed ``MAX_THREAD_TWEETS``."""
    return f"… {int(skipped_count)} more flips between here and the close …"


def _close_tweet(
    consensus_label: str,
    quality_health: Optional[str],
    final_split: dict[str, float],
    watch_url: str,
    share_url: str,
) -> str:
    """Closing tweet — final verdict + the two URLs that anyone reading
    the thread should be able to act on (watch the replay; fork the
    scenario)."""
    lines: list[str] = []
    label_pretty = _STANCE_LABEL.get(consensus_label, consensus_label.capitalize() or "Split")
    lines.append(f"Final: {label_pretty} consensus")
    lines.append(_format_stance_line(final_split))
    if quality_health:
        lines.append(f"Quality: {quality_health}")
    if watch_url:
        lines.append(f"Watch the replay: {watch_url}")
    if share_url and share_url != watch_url:
        lines.append(f"Run this scenario: {share_url}")
    return _truncate_to_tweet("\n".join(lines))


# ── Top-level builder ─────────────────────────────────────────────────────


def build_thread(
    sim_dir: str,
    summary: dict,
    watch_url: str = "",
    share_url: str = "",
) -> dict:
    """Assemble the full tweet-thread payload for a finished simulation.

    Returns ``{"tweets": [...], "total": N, "inflections_recorded": M,
    "truncated": bool}``. The route handler emits this dict directly
    for the ``.json`` form and joins ``tweets`` for the ``.txt`` form.

    The ``summary`` argument is the same dict
    ``_build_embed_summary_payload`` returns; the caller is responsible
    for the ``is_public`` gate. ``watch_url`` and ``share_url`` are
    fully-qualified URLs the close tweet drops in — the caller is
    responsible for resolving them (X-Forwarded-Host honour, etc.) so
    this module stays Flask-free.
    """
    scenario = (summary.get("scenario") or "").strip()
    total_rounds = int(summary.get("total_rounds") or 0)
    agent_count = int(summary.get("profiles_count") or 0)

    belief = summary.get("belief") or {}
    final_block = belief.get("final") or {}
    final_split = {
        "bullish": float(final_block.get("bullish") or 0.0),
        "neutral": float(final_block.get("neutral") or 0.0),
        "bearish": float(final_block.get("bearish") or 0.0),
    }
    consensus_label = _final_consensus_label(
        {
            "label": belief.get("consensus_stance"),
            **final_split,
        }
    )

    quality_health = None
    quality = summary.get("quality") or {}
    if isinstance(quality, dict):
        health = quality.get("health")
        if health:
            quality_health = str(health)

    rows = _build_round_series(sim_dir)
    inflections = find_inflection_points(rows)

    tweets: list[str] = []
    tweets.append(_intro_tweet(scenario, total_rounds, agent_count, consensus_label))

    truncated = False
    inflections_recorded = len(inflections)

    # Reserve one slot at each end (intro + close), and one extra for the
    # bridge tweet when we need to truncate. Anything over the body
    # budget gets folded into the bridge.
    body_budget = MAX_THREAD_TWEETS - 2
    if inflections_recorded > body_budget:
        head = inflections[:TRUNCATED_HEAD_TAIL]
        tail = inflections[-TRUNCATED_HEAD_TAIL:]
        skipped = inflections_recorded - len(head) - len(tail)
        for row in head:
            tweets.append(_inflection_tweet(row))
        if skipped > 0:
            tweets.append(_bridge_tweet(skipped))
        for row in tail:
            tweets.append(_inflection_tweet(row))
        truncated = True
    else:
        for row in inflections:
            tweets.append(_inflection_tweet(row))

    tweets.append(
        _close_tweet(consensus_label, quality_health, final_split, watch_url, share_url)
    )

    return {
        "tweets": tweets,
        "total": len(tweets),
        "inflections_recorded": inflections_recorded,
        "truncated": truncated,
    }


# ── Renderers ─────────────────────────────────────────────────────────────


def render_thread_txt(thread: dict) -> bytes:
    """Render the thread as a plain-text document.

    Each tweet is its own block separated by ``\\n---\\n`` so the
    operator can scan visually and copy individual tweets cleanly.
    Trailing newline keeps the output POSIX-text-clean.
    """
    tweets = thread.get("tweets") or []
    body = "\n---\n".join(tweets)
    if body and not body.endswith("\n"):
        body += "\n"
    return body.encode("utf-8")


def render_thread_json(thread: dict) -> bytes:
    """Pretty-print the thread payload as JSON. Caller-friendly indent
    so a ``curl`` to a file is immediately readable."""
    return (
        json.dumps(thread, ensure_ascii=False, indent=2, sort_keys=False)
        .encode("utf-8")
    )
