"""Renderer for the public ``/watch/<simulation_id>`` spectator page.

The watch page is the seventh share surface over the same on-disk
``sim_dir/`` folder layout, alongside the share card (PNG), replay GIF,
transcript (Markdown + JSON), public-gallery feeds (Atom + RSS), and
trajectory export (CSV + JSONL). Where the existing surfaces are static
artefacts of a *finished* simulation, the watch page is the **live
broadcast** format — a minimal full-viewport view a spectator can keep
open while a run is in progress, intended for "watch live →" tweets and
Discord pins.

The page is served as fully self-contained SSR HTML. There is no SPA
build step on the rendered page itself — a vanilla-JS poller updates
the DOM in place from the existing ``/api/simulation/<id>/embed-summary``
and ``/api/simulation/<id>/run-status`` REST endpoints. Two consequences
fall out of that:

* It works regardless of how the SPA front-end is built or routed —
  the page is still meaningful even if the SPA has not loaded.
* OG / Twitter Card meta tags can be embedded directly in the response
  body without an SPA router intercept, so a tweet of ``/watch/<id>``
  unfurls as a 1200×630 image card the same way the existing share
  landing page does.

The rendered HTML has no external script or font dependencies. Only the
share-card PNG image is loaded cross-origin, so a deployment behind a
restrictive CSP only needs to allow ``img-src 'self'`` and the same
host the API runs on.

Pure stdlib (``html`` + ``json``). No new packages.
"""

from __future__ import annotations

import html
import json
from typing import Any, Mapping


# Matches the ±0.2 stance threshold every other surface uses (gallery
# card, share card, replay GIF, transcript, webhook, RSS / Atom feed,
# trajectory CSV / JSONL). Kept here as a constant so the watch page
# never disagrees with the share card a spectator might see in their
# Twitter / Discord client moments earlier.
STANCE_THRESHOLD = 0.2

_TITLE_MAX_LEN = 200
_DESC_MAX_LEN = 280
_SCENARIO_HEADER_MAX_LEN = 220


def _esc(value: str) -> str:
    """HTML-attribute escape — quotes are critical here since values land
    inside ``content="..."``."""
    return html.escape(value or "", quote=True)


def _truncate(value: str, max_len: int) -> str:
    """Single-byte ``…`` truncation that preserves a trailing ellipsis.

    Strips whitespace and trims with a one-character margin so the final
    string never exceeds ``max_len`` after the ellipsis is appended.
    """
    if not value:
        return ""
    cleaned = value.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _belief_summary(belief: Mapping[str, Any] | None) -> tuple[float, float, float]:
    """Pull the most recent (bullish, neutral, bearish) percentages from
    an ``_build_embed_summary_payload`` ``belief`` block.

    Returns ``(0.0, 0.0, 0.0)`` for an absent or malformed payload — the
    rendered page treats that as "no rounds recorded yet" rather than
    crashing.
    """
    if not isinstance(belief, Mapping):
        return (0.0, 0.0, 0.0)

    final = belief.get("final")
    if isinstance(final, Mapping):
        try:
            return (
                float(final.get("bullish") or 0.0),
                float(final.get("neutral") or 0.0),
                float(final.get("bearish") or 0.0),
            )
        except (TypeError, ValueError):
            return (0.0, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


def _build_meta_description(summary: Mapping[str, Any] | None) -> str:
    """Compose the ``<meta name="description">`` + ``og:description``
    string from an embed-summary payload.

    Goes ``"Round N · Bullish X% · Neutral Y% · Bearish Z% — watch
    live."`` for an in-flight run with belief data, falls through to
    the bare scenario text for an idle / pending run, and to a generic
    "watch live" string when nothing is published yet.
    """
    if not isinstance(summary, Mapping):
        return "Watch a MiroShark simulation update round-by-round in real time."

    scenario = (summary.get("scenario") or "").strip()
    belief = summary.get("belief")
    bull, neu, bear = _belief_summary(belief)
    has_belief = bool(isinstance(belief, Mapping) and (belief.get("rounds") or []))

    current_round = summary.get("current_round") or 0
    total_rounds = summary.get("total_rounds") or 0

    if has_belief:
        if total_rounds:
            head = f"Round {int(current_round)}/{int(total_rounds)}"
        else:
            head = f"Round {int(current_round)}"
        body = (
            f"Bullish {bull:g}% · Neutral {neu:g}% · Bearish {bear:g}% — watch live"
        )
        if scenario:
            return _truncate(f"{scenario} — {head} · {body}.", _DESC_MAX_LEN)
        return _truncate(f"{head} · {body}.", _DESC_MAX_LEN)

    if scenario:
        return _truncate(scenario, _DESC_MAX_LEN)

    return "Watch a MiroShark simulation update round-by-round in real time."


def _build_initial_state(
    simulation_id: str,
    summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """The bootstrap blob handed to the in-page poller as a JSON literal.

    Keeps the rendered page meaningful for users with JS disabled (the
    static body still shows a scenario + initial belief split) and lets
    JS-enabled clients render the first frame without a network round-
    trip. Subsequent updates come from the existing live REST endpoints.
    """
    if not isinstance(summary, Mapping):
        summary = {}

    belief = summary.get("belief") if isinstance(summary.get("belief"), Mapping) else {}
    bull, neu, bear = _belief_summary(belief)

    return {
        "simulation_id": simulation_id,
        "scenario": _truncate(
            (summary.get("scenario") or "").strip(), _SCENARIO_HEADER_MAX_LEN
        ),
        "is_public": bool(summary.get("is_public")),
        "status": (summary.get("status") or "idle"),
        "runner_status": (summary.get("runner_status") or "idle"),
        "current_round": int(summary.get("current_round") or 0),
        "total_rounds": int(summary.get("total_rounds") or 0),
        "profiles_count": int(summary.get("profiles_count") or 0),
        "bullish": bull,
        "neutral": neu,
        "bearish": bear,
        "stance_threshold": STANCE_THRESHOLD,
        "consensus_round": (
            belief.get("consensus_round") if isinstance(belief, Mapping) else None
        ),
        "consensus_stance": (
            belief.get("consensus_stance") if isinstance(belief, Mapping) else None
        ),
        "quality_health": (
            (summary.get("quality") or {}).get("health")
            if isinstance(summary.get("quality"), Mapping)
            else None
        ),
    }


_BROADCAST_CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
  background: radial-gradient(ellipse at top, #1a1a1a 0%, #0a0a0a 60%);
  color: #fafafa;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 20px;
}
a { color: #ea580c; text-decoration: none; }
a:hover { text-decoration: underline; }
.brand {
  font-size: 12px;
  letter-spacing: 0.32em;
  font-weight: 700;
  opacity: 0.55;
  text-transform: uppercase;
  margin-bottom: 14px;
}
.wrap {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.2em;
  font-weight: 700;
  text-transform: uppercase;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid rgba(239, 68, 68, 0.45);
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  align-self: flex-start;
}
.live-badge .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8);
  animation: pulse 1.6s ease-out infinite;
}
.live-badge.idle { border-color: rgba(148, 163, 184, 0.3); background: rgba(148, 163, 184, 0.08); color: #cbd5f5; }
.live-badge.idle .dot { background: #94a3b8; animation: none; }
.live-badge.done { border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.1); color: #6ee7b7; }
.live-badge.done .dot { background: #10b981; animation: none; }
.live-badge.failed { border-color: rgba(244, 114, 182, 0.4); background: rgba(244, 114, 182, 0.1); color: #f9a8d4; }
.live-badge.failed .dot { background: #f472b6; animation: none; }
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.55); }
  70%  { box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
@media (prefers-reduced-motion: reduce) {
  .live-badge .dot { animation: none; }
  .belief-bar { transition: none; }
  .progress-fill { transition: none; }
  .cta-row a { transition: none; }
}
.scenario {
  font-size: 22px;
  line-height: 1.35;
  font-weight: 600;
  margin: 0;
  color: #f8fafc;
}
.scenario.placeholder { color: #94a3b8; font-weight: 400; }
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 22px;
  font-size: 13px;
  color: #cbd5f5;
  opacity: 0.85;
}
.meta-row .meta-item { display: inline-flex; gap: 6px; align-items: baseline; }
.meta-row .meta-label { opacity: 0.6; }
.meta-row .meta-value { color: #f1f5f9; font-weight: 500; }
.belief-card {
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  backdrop-filter: blur(10px);
}
.belief-track {
  display: flex;
  height: 18px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.12);
  width: 100%;
}
.belief-bar {
  height: 100%;
  transition: width 600ms cubic-bezier(0.22, 1, 0.36, 1);
}
.belief-bar.bullish { background: #22c55e; }
.belief-bar.neutral { background: #94a3b8; }
.belief-bar.bearish { background: #ef4444; }
.belief-legend {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 13px;
}
.belief-legend .legend-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.belief-legend .legend-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  opacity: 0.7;
}
.belief-legend .legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}
.belief-legend .legend-swatch.bullish { background: #22c55e; }
.belief-legend .legend-swatch.neutral { background: #94a3b8; }
.belief-legend .legend-swatch.bearish { background: #ef4444; }
.belief-legend .legend-value {
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
}
.progress-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #94a3b8;
}
.progress-row .progress-label {
  display: flex;
  justify-content: space-between;
}
.progress-track {
  width: 100%;
  height: 5px;
  background: rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ea580c, #f59e0b);
  width: 0%;
  transition: width 600ms cubic-bezier(0.22, 1, 0.36, 1);
}
.consensus-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #fde68a;
  align-self: flex-start;
}
.cta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 4px;
}
.cta-row a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border: 1px solid rgba(234, 88, 12, 0.55);
  color: #fdba74;
  background: rgba(234, 88, 12, 0.08);
  transition: background 180ms ease, border-color 180ms ease;
}
.cta-row a:hover {
  background: rgba(234, 88, 12, 0.18);
  border-color: rgba(234, 88, 12, 0.85);
  text-decoration: none;
}
.cta-row a.secondary {
  border-color: rgba(148, 163, 184, 0.3);
  color: #e2e8f0;
  background: rgba(148, 163, 184, 0.08);
}
.cta-row a.secondary:hover {
  background: rgba(148, 163, 184, 0.18);
  border-color: rgba(148, 163, 184, 0.55);
}
.share-card-preview {
  display: block;
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.65);
}
.empty-note {
  font-size: 13px;
  color: #94a3b8;
  margin: 0;
}
.footer {
  margin-top: 24px;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  opacity: 0.45;
}
@media (max-width: 540px) {
  .scenario { font-size: 19px; }
  .belief-card { padding: 18px; }
  .belief-legend { gap: 8px; }
  .belief-legend .legend-value { font-size: 16px; }
}
"""


def _broadcast_js() -> str:
    """In-page poller. Pure vanilla JS — no framework dependency."""
    # Kept as a single triple-quoted string so the rendered page is a
    # bytewise constant aside from the bootstrap blob and OG values.
    return r"""
(function () {
  var POLL_MS = 15000;        // matches the run-status polling cadence used by the SPA
  var FAILED_BACKOFF_MS = 60000;
  var ABSOLUTE_TIMEOUT_MS = 6 * 60 * 60 * 1000;  // give up after 6h of polling — the runner caps far below this
  var TERMINAL = { completed: true, failed: true, stopped: true };

  var bootstrap = (function () {
    var node = document.getElementById('watch-bootstrap');
    if (!node) return {};
    try { return JSON.parse(node.textContent || '{}'); }
    catch (err) { return {}; }
  })();

  var simId = bootstrap.simulation_id;
  if (!simId) return;

  var els = {
    badge: document.getElementById('live-badge'),
    badgeText: document.getElementById('live-badge-text'),
    scenario: document.getElementById('scenario'),
    roundLabel: document.getElementById('round-label'),
    roundValue: document.getElementById('round-value'),
    agentLabel: document.getElementById('agent-label'),
    agentValue: document.getElementById('agent-value'),
    qualityLabel: document.getElementById('quality-label'),
    qualityValue: document.getElementById('quality-value'),
    barBullish: document.getElementById('bar-bullish'),
    barNeutral: document.getElementById('bar-neutral'),
    barBearish: document.getElementById('bar-bearish'),
    valBullish: document.getElementById('val-bullish'),
    valNeutral: document.getElementById('val-neutral'),
    valBearish: document.getElementById('val-bearish'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    consensus: document.getElementById('consensus-tag'),
    emptyNote: document.getElementById('empty-note'),
    cta: document.getElementById('cta-row'),
  };

  function fmt(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    var n = Number(num);
    if (Math.abs(n - Math.round(n)) < 0.05) return Math.round(n).toString();
    return n.toFixed(1).replace(/\.0$/, '');
  }

  function setBarWidths(b, n, br) {
    var total = (Number(b) || 0) + (Number(n) || 0) + (Number(br) || 0);
    if (total <= 0) {
      els.barBullish.style.width = '0%';
      els.barNeutral.style.width = '0%';
      els.barBearish.style.width = '0%';
    } else {
      els.barBullish.style.width = ((Number(b) || 0) / total * 100) + '%';
      els.barNeutral.style.width = ((Number(n) || 0) / total * 100) + '%';
      els.barBearish.style.width = ((Number(br) || 0) / total * 100) + '%';
    }
    els.valBullish.textContent = fmt(b) + '%';
    els.valNeutral.textContent = fmt(n) + '%';
    els.valBearish.textContent = fmt(br) + '%';
  }

  function setBadge(state) {
    if (!els.badge) return;
    els.badge.classList.remove('idle', 'done', 'failed');
    if (state.runner === 'completed' || state.status === 'completed') {
      els.badge.classList.add('done');
      els.badgeText.textContent = 'Final';
    } else if (state.runner === 'failed' || state.status === 'failed' || state.runner === 'stopped') {
      els.badge.classList.add('failed');
      els.badgeText.textContent = (state.runner === 'stopped') ? 'Stopped' : 'Failed';
    } else if (state.runner === 'running') {
      els.badgeText.textContent = 'Live';
    } else {
      els.badge.classList.add('idle');
      els.badgeText.textContent = state.runner === 'pending' ? 'Pending' : 'Idle';
    }
  }

  function setProgress(current, total) {
    var c = Math.max(0, Number(current) || 0);
    var t = Math.max(0, Number(total) || 0);
    if (t > 0) {
      var pct = Math.min(100, (c / t) * 100);
      els.progressFill.style.width = pct + '%';
      els.progressText.textContent = c + '/' + t;
    } else if (c > 0) {
      els.progressFill.style.width = '0%';
      els.progressText.textContent = c + ' / —';
    } else {
      els.progressFill.style.width = '0%';
      els.progressText.textContent = 'Awaiting first round';
    }
    if (els.roundValue) {
      els.roundValue.textContent = t > 0 ? (c + ' / ' + t) : (c > 0 ? String(c) : '—');
    }
  }

  function setQuality(health) {
    if (!els.qualityValue) return;
    if (health) {
      els.qualityValue.textContent = String(health);
      els.qualityLabel.style.display = '';
    } else {
      els.qualityValue.textContent = '—';
    }
  }

  function setConsensus(round, stance) {
    if (!els.consensus) return;
    if (stance && (round || round === 0)) {
      var icon = stance === 'bullish' ? '🟢' : (stance === 'bearish' ? '🔴' : '⚪');
      els.consensus.textContent = icon + ' Consensus reached round ' + round + ' (' + stance + ')';
      els.consensus.style.display = '';
    } else {
      els.consensus.style.display = 'none';
    }
  }

  function showCta() {
    if (els.cta) els.cta.style.display = '';
  }
  function hideEmpty() {
    if (els.emptyNote) els.emptyNote.style.display = 'none';
  }

  function applySnapshot(snapshot) {
    if (!snapshot) return;
    setBadge({ runner: snapshot.runner_status, status: snapshot.status });
    setBarWidths(snapshot.bullish, snapshot.neutral, snapshot.bearish);
    setProgress(snapshot.current_round, snapshot.total_rounds);
    setQuality(snapshot.quality_health);
    setConsensus(snapshot.consensus_round, snapshot.consensus_stance);
    if (snapshot.has_belief) hideEmpty();
    if (snapshot.runner_status === 'completed' || snapshot.status === 'completed') showCta();
  }

  function fetchJson(url) {
    return fetch(url, { credentials: 'omit', cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) return Promise.reject(new Error('http_' + r.status));
        return r.json();
      });
  }

  function pickFinal(belief) {
    if (!belief || typeof belief !== 'object') return null;
    var f = belief.final;
    if (!f || typeof f !== 'object') return null;
    return {
      bullish: Number(f.bullish) || 0,
      neutral: Number(f.neutral) || 0,
      bearish: Number(f.bearish) || 0,
    };
  }

  function refresh() {
    return Promise.all([
      fetchJson('/api/simulation/' + encodeURIComponent(simId) + '/embed-summary')
        .catch(function () { return null; }),
      fetchJson('/api/simulation/' + encodeURIComponent(simId) + '/run-status')
        .catch(function () { return null; }),
    ]).then(function (results) {
      var summaryRes = results[0];
      var runRes = results[1];
      var summary = (summaryRes && summaryRes.success) ? (summaryRes.data || {}) : null;
      var run = (runRes && runRes.success) ? (runRes.data || {}) : null;
      var snapshot = {
        runner_status: (run && run.runner_status) || (summary && summary.runner_status) || 'idle',
        status: (summary && summary.status) || 'idle',
        current_round: (run && Number(run.current_round)) || (summary && Number(summary.current_round)) || 0,
        total_rounds: (run && Number(run.total_rounds)) || (summary && Number(summary.total_rounds)) || 0,
        quality_health: (summary && summary.quality && summary.quality.health) || null,
        bullish: 0,
        neutral: 0,
        bearish: 0,
        consensus_round: null,
        consensus_stance: null,
        has_belief: false,
      };
      var final = pickFinal(summary && summary.belief);
      if (final) {
        snapshot.bullish = final.bullish;
        snapshot.neutral = final.neutral;
        snapshot.bearish = final.bearish;
        snapshot.has_belief = true;
      }
      if (summary && summary.belief && typeof summary.belief === 'object') {
        snapshot.consensus_round = summary.belief.consensus_round;
        snapshot.consensus_stance = summary.belief.consensus_stance;
      }
      applySnapshot(snapshot);
      return snapshot;
    });
  }

  // Render bootstrap state immediately so the first frame doesn't wait
  // on the network (matches what the SSR HTML already shows but pulls
  // the values through the same DOM updaters so there's only one source
  // of truth).
  applySnapshot({
    runner_status: bootstrap.runner_status,
    status: bootstrap.status,
    current_round: bootstrap.current_round,
    total_rounds: bootstrap.total_rounds,
    quality_health: bootstrap.quality_health,
    bullish: bootstrap.bullish,
    neutral: bootstrap.neutral,
    bearish: bootstrap.bearish,
    consensus_round: bootstrap.consensus_round,
    consensus_stance: bootstrap.consensus_stance,
    has_belief: (bootstrap.bullish + bootstrap.neutral + bootstrap.bearish) > 0,
  });

  function isHidden() {
    // Skip work when the tab is backgrounded — saves the user's battery
    // and the API's quota. The 'visibilitychange' listener below kicks
    // a fresh poll the moment the tab is foregrounded again.
    return (typeof document !== 'undefined') &&
      ((document.visibilityState && document.visibilityState !== 'visible') || document.hidden === true);
  }

  var startedAt = Date.now();
  var pendingTimer = null;
  function schedule(delay) {
    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(loop, delay);
  }
  function loop() {
    pendingTimer = null;
    if (Date.now() - startedAt > ABSOLUTE_TIMEOUT_MS) return;
    if (isHidden()) {
      // Re-check shortly; the visibilitychange handler will also
      // wake us as soon as the tab is foregrounded.
      schedule(POLL_MS);
      return;
    }
    refresh().then(function (snapshot) {
      if (snapshot && TERMINAL[snapshot.runner_status]) {
        // One trailing refresh after a brief delay to catch the final
        // belief snapshot the runner writes after status flips.
        setTimeout(function () { if (!isHidden()) refresh(); }, 4000);
        return;
      }
      var delay = (snapshot && snapshot.runner_status === 'failed') ? FAILED_BACKOFF_MS : POLL_MS;
      schedule(delay);
    }, function () {
      schedule(POLL_MS);
    });
  }
  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('visibilitychange', function () {
      if (!isHidden()) schedule(0);
    });
  }
  // Stagger the first poll so the page paints before the network call.
  schedule(1500);
})();
"""


def render_watch_html(
    simulation_id: str,
    summary: Mapping[str, Any] | None,
    spa_url: str,
    fork_url: str,
    card_url: str,
    explore_url: str,
) -> str:
    """Render the full ``text/html`` body for ``/watch/<simulation_id>``.

    ``summary`` is the same dict shape as ``_build_embed_summary_payload``
    returns. Pass ``None`` for "scenario unknown" or "private simulation".
    """
    if summary is None:
        summary = {}

    is_public = bool(summary.get("is_public"))
    scenario_full = (summary.get("scenario") or "").strip() if is_public else ""

    # Display values — the title carries the same scenario text the share
    # landing page uses so both surfaces produce consistent unfurls.
    page_title = (
        f"MiroShark · {_truncate(scenario_full, _TITLE_MAX_LEN)}"
        if scenario_full
        else "MiroShark · Live simulation"
    )
    description = _build_meta_description(summary if is_public else None)

    # JSON literal handed to the in-page poller. ``json.dumps`` is safe
    # to embed inside a ``<script>`` block as long as we close any
    # accidental ``</`` sequences, which the HTML escape below covers.
    bootstrap = _build_initial_state(simulation_id, summary if is_public else None)
    bootstrap_json = json.dumps(bootstrap, ensure_ascii=False, separators=(",", ":"))

    # The runner_status string controls the live badge wording — render
    # the initial value server-side so even a non-JS client sees the
    # right label.
    runner_status = bootstrap.get("runner_status") or "idle"
    if runner_status == "running":
        badge_class, badge_text = "", "Live"
    elif runner_status == "completed":
        badge_class, badge_text = "done", "Final"
    elif runner_status == "failed":
        badge_class, badge_text = "failed", "Failed"
    elif runner_status == "stopped":
        badge_class, badge_text = "failed", "Stopped"
    elif runner_status == "pending":
        badge_class, badge_text = "idle", "Pending"
    else:
        badge_class, badge_text = "idle", "Idle"

    title_e = _esc(page_title)
    desc_e = _esc(description)
    card_e = _esc(card_url)
    spa_e = _esc(spa_url)
    fork_e = _esc(fork_url)
    explore_e = _esc(explore_url)

    scenario_display = (
        _esc(_truncate(scenario_full, _SCENARIO_HEADER_MAX_LEN))
        if scenario_full
        else ""
    )
    quality_health = bootstrap.get("quality_health")

    bull = bootstrap.get("bullish", 0.0)
    neu = bootstrap.get("neutral", 0.0)
    bear = bootstrap.get("bearish", 0.0)
    total = (bull + neu + bear) or 0.0

    def _pct_width(val: float) -> str:
        return f"{(val / total * 100):.2f}%" if total > 0 else "0%"

    bull_w = _pct_width(bull)
    neu_w = _pct_width(neu)
    bear_w = _pct_width(bear)

    current_round = int(bootstrap.get("current_round") or 0)
    total_rounds = int(bootstrap.get("total_rounds") or 0)
    if total_rounds > 0:
        progress_pct = f"{min(100, current_round / total_rounds * 100):.2f}%"
        progress_text = f"{current_round}/{total_rounds}"
        round_value_text = f"{current_round} / {total_rounds}"
    elif current_round > 0:
        progress_pct = "0%"
        progress_text = f"{current_round} / —"
        round_value_text = str(current_round)
    else:
        progress_pct = "0%"
        progress_text = "Awaiting first round"
        round_value_text = "—"

    consensus_round = bootstrap.get("consensus_round")
    consensus_stance = bootstrap.get("consensus_stance")
    consensus_html = ""
    if consensus_stance and (consensus_round is not None):
        icon = (
            "🟢" if consensus_stance == "bullish"
            else "🔴" if consensus_stance == "bearish"
            else "⚪"
        )
        consensus_html = (
            f"<span id=\"consensus-tag\" class=\"consensus-tag\">"
            f"{icon} Consensus reached round {_esc(str(consensus_round))} "
            f"({_esc(consensus_stance)})</span>"
        )
    else:
        consensus_html = (
            "<span id=\"consensus-tag\" class=\"consensus-tag\" style=\"display:none\"></span>"
        )

    # CTA buttons hidden by default — surfaced once the simulation reaches a
    # terminal state. Server-renders visible when status is already terminal.
    cta_visible = runner_status in {"completed", "failed", "stopped"}
    cta_style = "" if cta_visible else "display:none"

    has_belief = total > 0
    empty_style = "display:none" if has_belief else ""

    profiles_count = int(bootstrap.get("profiles_count") or 0)
    agent_value = str(profiles_count) if profiles_count > 0 else "—"
    quality_value = str(quality_health) if quality_health else "—"

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title_e}</title>\n"
        f"<meta name=\"description\" content=\"{desc_e}\">\n"
        "\n"
        "<meta property=\"og:type\" content=\"website\">\n"
        f"<meta property=\"og:title\" content=\"{title_e}\">\n"
        f"<meta property=\"og:description\" content=\"{desc_e}\">\n"
        f"<meta property=\"og:image\" content=\"{card_e}\">\n"
        "<meta property=\"og:image:width\" content=\"1200\">\n"
        "<meta property=\"og:image:height\" content=\"630\">\n"
        f"<meta property=\"og:url\" content=\"{_esc(spa_url)}\">\n"
        "<meta property=\"og:site_name\" content=\"MiroShark\">\n"
        "\n"
        "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
        f"<meta name=\"twitter:title\" content=\"{title_e}\">\n"
        f"<meta name=\"twitter:description\" content=\"{desc_e}\">\n"
        f"<meta name=\"twitter:image\" content=\"{card_e}\">\n"
        "\n"
        f"<link rel=\"canonical\" href=\"{spa_e}\">\n"
        "<style>"
        + _BROADCAST_CSS
        + "</style>\n"
        "</head>\n"
        "<body>\n"
        "<div class=\"brand\">MiroShark</div>\n"
        "<div class=\"wrap\">\n"
        f"  <span id=\"live-badge\" class=\"live-badge {badge_class}\">"
        f"<span class=\"dot\"></span><span id=\"live-badge-text\">{_esc(badge_text)}</span>"
        "</span>\n"
        + (
            f"  <h1 id=\"scenario\" class=\"scenario\">{scenario_display}</h1>\n"
            if scenario_display
            else "  <h1 id=\"scenario\" class=\"scenario placeholder\">Live simulation</h1>\n"
        ) +
        "  <div class=\"meta-row\">\n"
        f"    <span class=\"meta-item\" id=\"round-label\">"
        f"<span class=\"meta-label\">Round</span>"
        f"<span class=\"meta-value\" id=\"round-value\">{_esc(round_value_text)}</span>"
        "</span>\n"
        f"    <span class=\"meta-item\" id=\"agent-label\">"
        f"<span class=\"meta-label\">Agents</span>"
        f"<span class=\"meta-value\" id=\"agent-value\">{_esc(agent_value)}</span>"
        "</span>\n"
        f"    <span class=\"meta-item\" id=\"quality-label\">"
        f"<span class=\"meta-label\">Quality</span>"
        f"<span class=\"meta-value\" id=\"quality-value\">{_esc(quality_value)}</span>"
        "</span>\n"
        "  </div>\n"
        "  <section class=\"belief-card\">\n"
        "    <div class=\"belief-track\">\n"
        f"      <div id=\"bar-bullish\" class=\"belief-bar bullish\" style=\"width:{bull_w}\"></div>\n"
        f"      <div id=\"bar-neutral\" class=\"belief-bar neutral\" style=\"width:{neu_w}\"></div>\n"
        f"      <div id=\"bar-bearish\" class=\"belief-bar bearish\" style=\"width:{bear_w}\"></div>\n"
        "    </div>\n"
        "    <div class=\"belief-legend\">\n"
        "      <div class=\"legend-item\">"
        "<span class=\"legend-label\"><span class=\"legend-swatch bullish\"></span>Bullish</span>"
        f"<span class=\"legend-value\" id=\"val-bullish\">{_esc(_format_pct(bull))}</span>"
        "</div>\n"
        "      <div class=\"legend-item\">"
        "<span class=\"legend-label\"><span class=\"legend-swatch neutral\"></span>Neutral</span>"
        f"<span class=\"legend-value\" id=\"val-neutral\">{_esc(_format_pct(neu))}</span>"
        "</div>\n"
        "      <div class=\"legend-item\">"
        "<span class=\"legend-label\"><span class=\"legend-swatch bearish\"></span>Bearish</span>"
        f"<span class=\"legend-value\" id=\"val-bearish\">{_esc(_format_pct(bear))}</span>"
        "</div>\n"
        "    </div>\n"
        "    <div class=\"progress-row\">\n"
        "      <div class=\"progress-label\">"
        "<span>Progress</span>"
        f"<span id=\"progress-text\">{_esc(progress_text)}</span>"
        "</div>\n"
        "      <div class=\"progress-track\">"
        f"<div id=\"progress-fill\" class=\"progress-fill\" style=\"width:{progress_pct}\"></div>"
        "</div>\n"
        "    </div>\n"
        f"    {consensus_html}\n"
        f"    <p id=\"empty-note\" class=\"empty-note\" style=\"{empty_style}\">"
        "Belief data appears once the runner records its first round."
        "</p>\n"
        "  </section>\n"
        f"  <div id=\"cta-row\" class=\"cta-row\" style=\"{cta_style}\">\n"
        f"    <a href=\"{spa_e}\">View full simulation →</a>\n"
        f"    <a class=\"secondary\" href=\"{fork_e}\">Fork this scenario →</a>\n"
        f"    <a class=\"secondary\" href=\"{explore_e}\">Explore gallery</a>\n"
        "  </div>\n"
        "</div>\n"
        "<div class=\"footer\">"
        f"<a href=\"{spa_e}\">Open in MiroShark ↗</a>"
        "</div>\n"
        "<script id=\"watch-bootstrap\" type=\"application/json\">"
        + html.escape(bootstrap_json, quote=False)
        + "</script>\n"
        "<script>"
        + _broadcast_js()
        + "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _format_pct(value: float) -> str:
    """Match the JS ``fmt`` helper so the static SSR markup and the
    polled JS updates render identical numbers for the same input."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "0%"
    rounded = round(n)
    if abs(n - rounded) < 0.05:
        return f"{int(rounded)}%"
    return f"{n:.1f}".rstrip("0").rstrip(".") + "%"
