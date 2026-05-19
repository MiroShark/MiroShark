"""Machine-readable trading-signal derivation from a finished simulation.

The eleventh data surface alongside the share card (PNG verdict),
replay GIF (motion), transcript (prose), trajectory CSV / JSONL (raw
data), thread (text), watch page (live), reproduce.json (citation),
notebook.ipynb (analysis), chart.svg (vector visual), and DKG citation
(on-chain provenance). The previous ten describe *what happened* in a
simulation; this one collapses the same final-state numbers into a
single action primitive a quant tool, Zapier workflow, or alert
pipeline can consume directly — ``direction`` + ``confidence_pct`` +
``risk_tier`` + the three component percentages.

Design notes
------------

* **Pure derivation.** No new computation. ``compute_signal`` reads the
  same ``belief.final`` percentages the embed-summary endpoint already
  builds and the same ``quality.health`` string the gallery card and
  share card already display. A "bullish 62%" signal here matches what
  every other surface reports for the same simulation, byte-for-byte.
* **Three-stance plurality.** The leading stance among bullish /
  neutral / bearish wins. Ties (rare — the percentages are
  one-decimal-rounded) break in a stable order: bullish > bearish >
  neutral. This is documented so a consumer can predict the output for
  every input.
* **Confidence as distance from a three-way split.** A pure
  ``(33.3%, 33.3%, 33.3%)`` split produces ``confidence_pct=0``; an
  unanimous ``(100%, 0%, 0%)`` produces ``confidence_pct=100``. The
  formula is ``(leading_pct - 33.333) / 66.667 * 100`` clamped to
  ``[0, 100]`` — the same denominator a researcher would derive on
  paper, so the field is interpretable without reading docs.
* **Quality → risk_tier mapping.** ``quality_health`` is a one-word
  string (``"excellent" / "good" / "fair" / "poor"``). The four-tier
  health scale collapses to a three-tier risk scale that downstream
  trading systems already expect: ``excellent`` → ``low-risk``,
  ``good`` → ``medium-risk``, anything else (``fair`` / ``poor`` /
  missing / ``"N/A"``) → ``high-risk``. The default-to-high posture is
  deliberate — a quant tool that gets a signal with unknown quality
  should treat it cautiously, not optimistically.
* **Pure stdlib.** ``datetime`` for the ISO-8601 timestamp; no other
  imports. Same dependency posture as every other export module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


# ── Bucket thresholds ─────────────────────────────────────────────────────
#
# A perfectly even three-way split puts each stance at
# ``100 / 3 == 33.333...`` percent. We anchor the confidence formula
# against this value so an unanimous leading stance lands at 100 and a
# pure split lands at 0.

_EVEN_SPLIT_PCT = 100.0 / 3.0  # ≈ 33.333
_CONFIDENCE_DENOMINATOR = 100.0 - _EVEN_SPLIT_PCT  # ≈ 66.667


# Stance label → emitted ``direction`` string. Mapped via a small dict
# rather than the raw key so the API contract is one place to look.
_DIRECTION_LABELS: dict[str, str] = {
    "bullish": "Bullish",
    "neutral": "Neutral",
    "bearish": "Bearish",
}


# Quality health → emitted risk tier. ``excellent`` is the only health
# value that earns the low-risk badge; ``good`` earns medium; everything
# else (including missing / ``"N/A"``) defaults to high so an unknown
# quality is treated cautiously by downstream consumers.
_RISK_TIER_BY_HEALTH: dict[str, str] = {
    "excellent": "low-risk",
    "good": "medium-risk",
    "fair": "high-risk",
    "poor": "high-risk",
}
_DEFAULT_RISK_TIER = "high-risk"


def _coerce_pct(value: Any) -> Optional[float]:
    """Coerce a percentage-shaped value to ``float`` in ``[0, 100]``.

    Returns ``None`` when the input is missing or non-numeric so the
    caller can decide whether to fall through to ``compute_signal``
    returning ``None``. Negative values clamp to ``0``; values above
    ``100`` clamp to ``100`` — defensive against a future renderer that
    rounds 99.95 to 100.05.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    if pct != pct:
        return None
    if pct < 0.0:
        return 0.0
    if pct > 100.0:
        return 100.0
    return pct


def _resolve_risk_tier(quality_health: Any) -> str:
    """Map a quality-health string to one of the three risk tiers.

    Case-insensitive match on the leading word so ``"Excellent "`` and
    ``"excellent"`` produce the same tier. Unknown or empty input falls
    through to ``_DEFAULT_RISK_TIER`` (``"high-risk"``) so a missing
    quality file biases downstream consumers towards caution.
    """
    if not isinstance(quality_health, str):
        return _DEFAULT_RISK_TIER
    key = quality_health.strip().lower().split()[0] if quality_health.strip() else ""
    return _RISK_TIER_BY_HEALTH.get(key, _DEFAULT_RISK_TIER)


def _pick_leader(bullish: float, neutral: float, bearish: float) -> str:
    """Return the plurality stance key.

    Tie-breaks in a fixed order: ``bullish`` > ``bearish`` > ``neutral``.
    A live tie at one-decimal-rounded percentages is rare but possible
    (e.g. ``45.0 / 10.0 / 45.0``); the documented order means a quant
    consumer can predict the output even in that edge case.
    """
    candidates = (
        ("bullish", bullish),
        ("bearish", bearish),
        ("neutral", neutral),
    )
    leader_key, leader_pct = candidates[0]
    for key, pct in candidates[1:]:
        if pct > leader_pct:
            leader_key, leader_pct = key, pct
    return leader_key


def _compute_confidence(leading_pct: float) -> float:
    """Return ``confidence_pct`` in ``[0.0, 100.0]`` rounded to 1 dp.

    ``leading_pct == 33.333`` ⇒ ``0``;
    ``leading_pct == 100.0`` ⇒ ``100``;
    ``leading_pct == 66.666`` ⇒ ``50``.
    """
    distance = max(0.0, leading_pct - _EVEN_SPLIT_PCT)
    confidence = distance / _CONFIDENCE_DENOMINATOR * 100.0
    if confidence > 100.0:
        confidence = 100.0
    return round(confidence, 1)


def _iso_utc_now() -> str:
    """ISO-8601 UTC ``"YYYY-MM-DDTHH:MM:SSZ"`` for the response.

    Same shape as the webhook delivery log's ``timestamp`` field and
    the reproduce.json blob's ``exported_at`` field — every export
    surface that timestamps anything uses this format.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_signal(summary: Any) -> Optional[dict[str, Any]]:
    """Derive the trading-signal payload from an embed-summary dict.

    Returns ``None`` when the summary is missing the data required to
    produce a meaningful signal — typically a simulation that hasn't
    recorded any rounds yet (no ``belief.final`` block). The caller
    (route handler) is expected to translate ``None`` into a 404 so an
    embedding tool can tell a "not ready" sim apart from a "private"
    sim (which is a 403).

    The summary shape mirrors what ``_build_embed_summary_payload``
    returns:

      {
        "belief": {
          "final": {"bullish": <pct>, "neutral": <pct>, "bearish": <pct>},
          ...
        },
        "quality": {"health": <str>, "participation_rate": <float>}
        # may be None
      }

    Producing:

      {
        "schema_version": "1",
        "direction": "Bullish" | "Neutral" | "Bearish",
        "confidence_pct": <0.0 .. 100.0>,
        "risk_tier": "low-risk" | "medium-risk" | "high-risk",
        "bullish_pct": <pct>,
        "neutral_pct": <pct>,
        "bearish_pct": <pct>,
        "quality_health": <str | "N/A">,
        "signal_generated_at": "YYYY-MM-DDTHH:MM:SSZ"
      }
    """
    if not isinstance(summary, dict):
        return None

    belief = summary.get("belief")
    if not isinstance(belief, dict):
        return None

    final = belief.get("final")
    if not isinstance(final, dict):
        return None

    bullish = _coerce_pct(final.get("bullish"))
    neutral = _coerce_pct(final.get("neutral"))
    bearish = _coerce_pct(final.get("bearish"))
    if bullish is None or neutral is None or bearish is None:
        return None

    quality = summary.get("quality") if isinstance(summary.get("quality"), dict) else {}
    raw_health = quality.get("health") if isinstance(quality, dict) else None
    quality_health = raw_health if isinstance(raw_health, str) and raw_health.strip() else "N/A"

    leader_key = _pick_leader(bullish, neutral, bearish)
    leader_pct = {
        "bullish": bullish,
        "neutral": neutral,
        "bearish": bearish,
    }[leader_key]

    return {
        "schema_version": "1",
        "direction": _DIRECTION_LABELS[leader_key],
        "confidence_pct": _compute_confidence(leader_pct),
        "risk_tier": _resolve_risk_tier(quality_health),
        "bullish_pct": round(bullish, 1),
        "neutral_pct": round(neutral, 1),
        "bearish_pct": round(bearish, 1),
        "quality_health": quality_health,
        "signal_generated_at": _iso_utc_now(),
    }
