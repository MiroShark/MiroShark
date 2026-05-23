"""Polymarket-ready prediction-JSON adapter for a finished simulation.

The fifteenth machine-readable share surface, and the first one shaped
for a specific external integrator. ``signal.json`` (PR #91) collapses
the final-round belief split into a generic action primitive
(``direction`` + ``confidence_pct`` + ``risk_tier``). This module maps
that same primitive into Polymarket's binary YES / NO probability
shape — the exact field set a Polymarket trading bot expects between
"simulation result" and "actionable market signal".

Design notes
------------

* **Pure derivation, layered on signal_service.** ``compute_polymarket``
  calls ``signal_service.compute_signal`` and re-shapes its output.
  Every property the signal payload guarantees (tie-break order,
  one-decimal rounding, ISO-8601 timestamp format) carries through.
  A "Bullish 62%" signal here matches what ``signal.json``,
  ``badge.svg``, the gallery card, and the share card report for the
  same simulation — the only new information is the Polymarket-
  shaped *envelope*, not the data.

* **Direction-aware YES probability.** Polymarket's YES side
  represents *"the proposition is true"*. We mirror that semantically:

    - ``Bullish`` simulation → the bullish-staked agents are predicting
      YES, so ``yes_probability = bullish_pct / 100``.
    - ``Bearish`` simulation → the bearish-staked agents are predicting
      NO, so ``yes_probability = 1 - bearish_pct / 100`` (the residual
      probability the proposition is true).
    - ``Neutral`` simulation → the swarm has no opinion, so
      ``yes_probability = 0.5`` exactly. A consumer treating this as a
      coin flip is doing the correct thing.

  ``no_probability`` is always ``1 - yes_probability``; the pair sums
  to ``1.0`` within floating-point tolerance, the invariant a
  Polymarket order-book consumer expects.

* **Confidence tier as a four-bucket scale.** ``signal.json``'s
  ``confidence_pct`` is a continuous ``[0, 100]`` number. Polymarket
  bots typically gate on a discrete risk tier (different position
  sizes for "speculative" vs. "high-conviction" signals); we expose
  both. The four-bucket scale:

    - ``<25`` → ``"speculative"``
    - ``25-50`` → ``"moderate"``
    - ``50-75`` → ``"confident"``
    - ``≥75`` → ``"high-conviction"``

  The upper bound of each bucket is *exclusive* (a ``confidence_pct``
  of exactly ``25.0`` is ``"moderate"``, not ``"speculative"``) so the
  bucket boundaries are easy to verify and the scale is monotone in
  the obvious direction.

* **Polymarket title shape.** A market title on Polymarket starts with
  ``"Will "`` and ends with ``"?"`` — the human-readable framing for a
  YES/NO outcome. We synthesise ``suggested_market_title`` by prefix-
  matching ``"Will "`` and ensuring a single trailing ``"?"``. The
  scenario is truncated at 120 characters (with an ellipsis if cut) so
  the title fits inside Polymarket's display rail. The bot author is
  expected to massage this string — it's a *suggested* title, not a
  market-creation primary key.

* **Completed sims only.** Unlike ``signal.json`` (which returns a
  payload as soon as the simulation has a final belief block, even if
  it's still running), ``compute_polymarket`` returns ``None`` for any
  non-``completed`` status. A Polymarket bot acting on a mid-run
  signal would size positions against numbers that can still flip; the
  publish-gate + completed-only posture prevents that footgun.

* **Pure stdlib.** ``datetime`` for the ISO-8601 timestamp; the
  ``signal_service`` import for the underlying derivation. No
  third-party dependency added. Continues the 30-PR zero-new-deps
  streak.
"""

from __future__ import annotations

from typing import Any, Optional

from . import signal_service


_MAX_TITLE_SCENARIO_LEN = 120


def _confidence_tier(confidence_pct: float) -> str:
    """Map a continuous ``confidence_pct`` into the four-bucket tier scale.

    Upper bounds are exclusive: ``25.0`` is ``"moderate"`` (not
    ``"speculative"``), ``50.0`` is ``"confident"``, ``75.0`` is
    ``"high-conviction"``. Values outside ``[0, 100]`` clamp into the
    nearest bucket — ``compute_signal`` already returns a value in
    range, but the defensive read keeps this module callable from any
    future caller that passes a raw belief percentage by accident.
    """
    if confidence_pct >= 75.0:
        return "high-conviction"
    if confidence_pct >= 50.0:
        return "confident"
    if confidence_pct >= 25.0:
        return "moderate"
    return "speculative"


def _yes_probability(
    direction: str, bullish_pct: float, bearish_pct: float
) -> float:
    """Return the YES-side probability for a Polymarket binary market.

    Direction-aware: a Bullish swarm predicts YES with the bullish
    cohort's strength; a Bearish swarm predicts NO with the bearish
    cohort's strength (so YES is the residual); a Neutral swarm has no
    opinion (``0.5`` exactly — the coin-flip prior). Rounded to 4
    decimal places — same precision Polymarket's UI displays.
    """
    if direction == "Bullish":
        raw = bullish_pct / 100.0
    elif direction == "Bearish":
        raw = 1.0 - bearish_pct / 100.0
    else:
        raw = 0.5
    if raw < 0.0:
        raw = 0.0
    elif raw > 1.0:
        raw = 1.0
    return round(raw, 4)


def _suggested_market_title(scenario: Any) -> str:
    """Synthesise a Polymarket-shaped market title from the sim scenario.

    Polymarket titles start with ``"Will "`` and end with a single
    ``"?"``. We coerce the scenario into that shape:

    * Strip surrounding whitespace.
    * Drop a redundant ``"Will "`` prefix if the scenario already has
      one (case-insensitive) so we don't emit ``"Will Will the…"``.
    * Strip trailing punctuation (``.``, ``?``, ``!``, ``…``) before
      truncating, so we don't end on ``"Will the merger close…?"``.
    * Truncate at ``_MAX_TITLE_SCENARIO_LEN`` characters and append an
      ellipsis when the input was actually cut.
    * Prefix ``"Will "`` and append a single ``"?"``.

    Returns ``"Will resolve YES?"`` for a missing / empty / non-string
    scenario — a safe placeholder a bot author can detect and
    override, rather than an empty market title that would round-trip
    through Polymarket as garbage.
    """
    if not isinstance(scenario, str) or not scenario.strip():
        return "Will resolve YES?"

    body = scenario.strip()
    # Drop a redundant "Will " prefix.
    if body[:5].lower() == "will ":
        body = body[5:].strip()
    # Strip trailing punctuation we'd otherwise duplicate against the "?".
    body = body.rstrip(" .?!…")
    if not body:
        return "Will resolve YES?"

    truncated = False
    if len(body) > _MAX_TITLE_SCENARIO_LEN:
        body = body[:_MAX_TITLE_SCENARIO_LEN].rstrip()
        truncated = True

    suffix = "…?" if truncated else "?"
    return f"Will {body}{suffix}"


def compute_polymarket(
    summary: Any, simulation_id: Any
) -> Optional[dict[str, Any]]:
    """Derive the Polymarket-shaped prediction payload from an embed summary.

    Returns ``None`` when:

    * ``summary`` is not a dict.
    * The simulation status is not ``"completed"`` (a Polymarket bot
      sizing positions against a mid-run signal would chase numbers
      that can still flip).
    * The underlying ``compute_signal`` call returns ``None`` (no
      ``belief.final`` block — the sim has no recorded rounds).

    A 404 from the caller route covers all three branches; a Polymarket
    bot reading a 404 should treat the simulation as "not ready"
    rather than retry.

    Payload shape::

        {
          "schema_version": "1",
          "simulation_id": "<sim_id>",
          "direction": "Bullish" | "Neutral" | "Bearish",
          "yes_probability": <0.0 .. 1.0>,
          "no_probability": <0.0 .. 1.0>,
          "confidence_pct": <0.0 .. 100.0>,
          "confidence_tier": "speculative" | "moderate" |
                             "confident" | "high-conviction",
          "risk_tier": "low-risk" | "medium-risk" | "high-risk",
          "bullish_pct": <pct>,
          "neutral_pct": <pct>,
          "bearish_pct": <pct>,
          "quality_health": <str | "N/A">,
          "suggested_market_title": "Will …?",
          "source_sim_id": "<sim_id>",
          "polymarket_generated_at": "YYYY-MM-DDTHH:MM:SSZ"
        }

    ``simulation_id`` is echoed twice — once as ``simulation_id`` (the
    canonical key used across every other share surface) and once as
    ``source_sim_id`` (the field a Polymarket bot expects when writing
    back to its own audit log).
    """
    if not isinstance(summary, dict):
        return None

    status = summary.get("status")
    if not isinstance(status, str) or status.lower() != "completed":
        return None

    signal = signal_service.compute_signal(summary)
    if signal is None:
        return None

    sim_id = simulation_id if isinstance(simulation_id, str) and simulation_id else summary.get("simulation_id", "")
    if not isinstance(sim_id, str):
        sim_id = ""

    yes_prob = _yes_probability(
        signal["direction"],
        signal["bullish_pct"],
        signal["bearish_pct"],
    )
    no_prob = round(1.0 - yes_prob, 4)

    return {
        "schema_version": "1",
        "simulation_id": sim_id,
        "direction": signal["direction"],
        "yes_probability": yes_prob,
        "no_probability": no_prob,
        "confidence_pct": signal["confidence_pct"],
        "confidence_tier": _confidence_tier(signal["confidence_pct"]),
        "risk_tier": signal["risk_tier"],
        "bullish_pct": signal["bullish_pct"],
        "neutral_pct": signal["neutral_pct"],
        "bearish_pct": signal["bearish_pct"],
        "quality_health": signal["quality_health"],
        "suggested_market_title": _suggested_market_title(summary.get("scenario")),
        "source_sim_id": sim_id,
        "polymarket_generated_at": signal["signal_generated_at"],
    }
