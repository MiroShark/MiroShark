"""Filter / sort / paginate helpers for the public simulation gallery.

The ``GET /api/simulation/public`` endpoint started life as "newest 50
public sims." Once the gallery grew past a few dozen entries, an analyst
hunting for "every bearish-consensus DeFi sim" or "all excellent-quality
runs about Aave" had no path — the only surface was a reverse-chronological
scroll.

This module turns the public listing into a small queryable corpus:

* keyword search over ``scenario`` (case-insensitive substring, optional)
* dominant-stance filter — ``bullish`` / ``bearish`` / ``neutral``
* quality filter — ``excellent`` / ``good`` / ``fair`` / ``poor``
* outcome filter — ``correct`` / ``incorrect`` / ``partial`` (the
  ``verified=1`` toggle stays for backward compatibility)
* sort by ``date`` (default, newest first), ``rounds`` (highest
  agent/round count first), or ``agents``

The helpers are pure-stdlib and operate on plain dicts (the gallery card
payload returned by ``_build_gallery_card_payload``) so they're testable
without booting Flask.

The same payload shape backs the ``/api/feed.atom`` and ``/api/feed.rss``
renderers — anyone wiring those endpoints into the filter set can call
``select_filtered_cards`` with the same arguments and get a consistent
selection.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


# ── Public constants ──────────────────────────────────────────────────────

#: Hard cap on the per-page size — the same envelope ``GET /api/simulation/public``
#: has always advertised. Larger pulls should paginate, not raise the cap.
MAX_LIMIT = 100

#: Default page size when the caller omits ``limit``. Matches the
#: pre-existing default so legacy clients keep their prior behaviour.
DEFAULT_LIMIT = 50

#: Hard cap on ``q`` — long, free-text search strings are almost always
#: a paste-error or a probe; truncate so the substring match stays cheap.
MAX_QUERY_CHARS = 200

#: Allowed dominant-stance filter values.
CONSENSUS_VALUES: frozenset[str] = frozenset({"bullish", "neutral", "bearish"})

#: Allowed quality-tier filter values. Compared case-insensitively against
#: the ``quality_health`` string MiroShark stores in ``quality.json``
#: (e.g. ``"Excellent"`` / ``"Good"`` / ``"Fair"`` / ``"Poor"``).
QUALITY_VALUES: frozenset[str] = frozenset({"excellent", "good", "fair", "poor"})

#: Allowed outcome-label filter values — mirrors the labels accepted by
#: ``POST /api/simulation/<id>/outcome``.
OUTCOME_VALUES: frozenset[str] = frozenset({"correct", "incorrect", "partial"})

#: Allowed sort keys.
SORT_VALUES: frozenset[str] = frozenset({"date", "rounds", "agents"})


# ── Param normalisation ───────────────────────────────────────────────────


def normalise_query(value: Optional[str]) -> str:
    """Trim + cap a raw ``q`` query string. Never returns ``None``.

    Callers downstream of this can substring-compare directly without
    re-checking for None / huge inputs.
    """
    if not value:
        return ""
    s = str(value).strip()
    if len(s) > MAX_QUERY_CHARS:
        s = s[:MAX_QUERY_CHARS]
    return s


def _normalise_enum(value: Optional[str], allowed: frozenset[str]) -> Optional[str]:
    """Lowercase + validate. Returns ``None`` when the value is empty or
    not in ``allowed`` so a caller passing ``?consensus=`` (empty) gets
    the same behaviour as omitting the param entirely."""
    if not value:
        return None
    s = str(value).strip().lower()
    return s if s in allowed else None


def normalise_consensus(value: Optional[str]) -> Optional[str]:
    return _normalise_enum(value, CONSENSUS_VALUES)


def normalise_quality(value: Optional[str]) -> Optional[str]:
    return _normalise_enum(value, QUALITY_VALUES)


def normalise_outcome(value: Optional[str]) -> Optional[str]:
    return _normalise_enum(value, OUTCOME_VALUES)


def normalise_sort(value: Optional[str]) -> str:
    """Default to ``date`` for any unrecognised input."""
    s = (value or "").strip().lower()
    return s if s in SORT_VALUES else "date"


def normalise_limit(value: Any, *, default: int = DEFAULT_LIMIT) -> int:
    """Clamp ``limit`` into ``[1, MAX_LIMIT]``. Non-numeric → default."""
    try:
        n = int(value if value is not None else default)
    except (TypeError, ValueError):
        n = default
    return max(1, min(MAX_LIMIT, n))


def normalise_offset(value: Any) -> int:
    """Floor at zero. Non-numeric → 0."""
    try:
        n = int(value if value is not None else 0)
    except (TypeError, ValueError):
        n = 0
    return max(0, n)


def page_to_offset(page: Any, limit: int) -> int:
    """Convert a 1-based ``page`` query parameter to an ``offset``.

    ``page=1`` → offset 0. ``page=0`` and negative pages coerce to page 1.
    Non-numeric input is treated as page 1.
    """
    try:
        p = int(page) if page is not None else 1
    except (TypeError, ValueError):
        p = 1
    if p < 1:
        p = 1
    return (p - 1) * limit


# ── Card-level inspectors ─────────────────────────────────────────────────


#: Minimum percentage-point gap between the top and runner-up stance
#: required to call a card "dominant" in that direction. Mirrors the
#: ±0.2 stance threshold the share card / replay GIF / transcript /
#: webhook / feed / trajectory CSV all share — a card whose top stance
#: doesn't clear the runner-up by this margin is treated as a near-tie
#: (no dominant stance) and falls out of any ``consensus=...`` filter.
DOMINANCE_THRESHOLD = 0.2


def dominant_stance(card: dict) -> Optional[str]:
    """Return ``"bullish" | "neutral" | "bearish"`` for the card, or
    ``None`` when no consensus is computable yet (in-progress sims, empty
    trajectory) **or** when the top stance fails to clear the runner-up
    by at least ``DOMINANCE_THRESHOLD`` percentage points.

    The ±0.2 margin keeps the gallery's ``consensus=bullish`` filter
    consistent with the share card, replay GIF, transcript, webhook,
    and feed renderers — a 33.4 / 33.3 / 33.3 split has no dominant
    stance on any of those surfaces, so it can't leak into a consensus
    bucket here either.

    An exact tie at the top (e.g. 40 / 40 / 20) is broken lexically so
    the result stays deterministic across calls.
    """
    consensus = card.get("final_consensus") if isinstance(card, dict) else None
    if not isinstance(consensus, dict):
        return None

    pcts: list[tuple[str, float]] = []
    for label in ("bullish", "neutral", "bearish"):
        try:
            v = float(consensus.get(label, 0) or 0)
        except (TypeError, ValueError):
            v = 0.0
        pcts.append((label, v))

    pcts.sort(key=lambda kv: (-kv[1], kv[0]))
    top_label, top_value = pcts[0]
    _, runner_up_value = pcts[1]
    if top_value <= 0:
        return None
    # An exact tie at the top falls back to the lexical winner so the
    # result is deterministic; a non-zero but sub-threshold lead is a
    # near-tie and gets filtered out, matching how every other surface
    # treats split consensus.
    gap = top_value - runner_up_value
    if gap > 0 and gap < DOMINANCE_THRESHOLD:
        return None
    return top_label


def _quality_tier(card: dict) -> Optional[str]:
    """Lowercased first-word of ``quality_health`` so ``"Excellent"`` →
    ``"excellent"`` and ``"Good with caveats"`` → ``"good"`` for matching.

    Returns ``None`` when the card has no quality info or the value
    doesn't start with one of the four known tiers.
    """
    raw = card.get("quality_health") if isinstance(card, dict) else None
    if not raw:
        return None
    head = str(raw).strip().lower().split()
    if not head:
        return None
    word = head[0]
    return word if word in QUALITY_VALUES else None


def _scenario_text(card: dict) -> str:
    """Lowercased scenario for case-insensitive substring matching."""
    s = card.get("scenario") if isinstance(card, dict) else ""
    return str(s or "").lower()


def _outcome_label(card: dict) -> Optional[str]:
    outcome = card.get("outcome") if isinstance(card, dict) else None
    if not isinstance(outcome, dict):
        return None
    label = outcome.get("label")
    if not label:
        return None
    s = str(label).strip().lower()
    return s if s in OUTCOME_VALUES else None


# ── Filter + sort ─────────────────────────────────────────────────────────


def filter_cards(
    cards: Iterable[dict],
    *,
    q: str = "",
    consensus: Optional[str] = None,
    quality: Optional[str] = None,
    outcome: Optional[str] = None,
    verified_only: bool = False,
) -> list[dict]:
    """Return the subset of ``cards`` that satisfy every supplied filter.

    All filters combine with logical AND. An empty / ``None`` filter is
    a no-op (the card always matches that dimension). The input iterable
    is consumed once — order is preserved so ``sort_cards`` can be
    chained or skipped.
    """
    needle = q.lower() if q else ""

    out: list[dict] = []
    for card in cards:
        if not isinstance(card, dict):
            continue

        if needle and needle not in _scenario_text(card):
            continue

        if consensus and dominant_stance(card) != consensus:
            continue

        if quality and _quality_tier(card) != quality:
            continue

        if outcome and _outcome_label(card) != outcome:
            continue

        if verified_only and _outcome_label(card) is None:
            continue

        out.append(card)

    return out


def _date_key(card: dict) -> str:
    """Sort key for ``date`` — empty strings sort last (oldest)."""
    return str(card.get("created_at") or "")


def _rounds_key(card: dict) -> tuple[int, int, str]:
    """Sort key for ``rounds`` — highest current_round first, breaks ties
    on agent_count then created_at."""
    try:
        cr = int(card.get("current_round") or 0)
    except (TypeError, ValueError):
        cr = 0
    try:
        ac = int(card.get("agent_count") or 0)
    except (TypeError, ValueError):
        ac = 0
    return (cr, ac, _date_key(card))


def _agents_key(card: dict) -> tuple[int, str]:
    try:
        ac = int(card.get("agent_count") or 0)
    except (TypeError, ValueError):
        ac = 0
    return (ac, _date_key(card))


def sort_cards(cards: list[dict], *, sort: str = "date") -> list[dict]:
    """Return a new list sorted by the requested key, newest/largest first."""
    key = normalise_sort(sort)
    if key == "rounds":
        return sorted(cards, key=_rounds_key, reverse=True)
    if key == "agents":
        return sorted(cards, key=_agents_key, reverse=True)
    return sorted(cards, key=_date_key, reverse=True)


# ── End-to-end selection ──────────────────────────────────────────────────


def select_filtered_cards(
    cards: Iterable[dict],
    *,
    q: str = "",
    consensus: Optional[str] = None,
    quality: Optional[str] = None,
    outcome: Optional[str] = None,
    verified_only: bool = False,
    sort: str = "date",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Filter → sort → paginate. Returns ``(page_items, total_filtered)``.

    ``total_filtered`` is the count after filters but before pagination,
    so the caller can compute ``has_more`` and render an "X results"
    summary that reflects the filter set rather than the full corpus.
    """
    filtered = filter_cards(
        cards,
        q=q,
        consensus=consensus,
        quality=quality,
        outcome=outcome,
        verified_only=verified_only,
    )
    sorted_cards = sort_cards(filtered, sort=sort)
    total = len(sorted_cards)
    page = sorted_cards[offset:offset + max(0, int(limit))] if limit > 0 else []
    return page, total
