"""Farcaster Frame v2 metadata builder for published simulations.

Closes the **Base-chain audience gap** that none of the existing share
surfaces address. $MIROSHARK lives on Base; the Base-native social
network is Farcaster / Warpcast. When a token holder or researcher
pastes a ``/share/<sim_id>`` URL into a Farcaster cast today, the cast
shows a blank link card — every other paste context (Twitter/X,
Discord, Slack, LinkedIn, Notion, Ghost, Substack) gets a rich
unfurl, but Farcaster sees nothing.

Farcaster Frame v2 reads a handful of ``<meta property="fc:frame:*">``
tags from the URL's HTML head, then renders the named image as an
in-feed card with a configurable action button. Every Frame-aware
Farcaster client — Warpcast, Supercast, the in-app Farcaster Frame in
Coinbase Wallet — speaks the same tag schema. This module assembles
the per-simulation values those tags need:

* ``image_url`` — the per-round belief trajectory chart SVG (PR #85)
  at 800×400 (2:1 aspect ratio, matching the Frame spec recommendation).
  Falls back to the share-card PNG (1200×630, 1.91:1) when the
  simulation has no recorded rounds yet.
* ``image_aspect_ratio`` — ``"2:1"`` for chart-backed frames or
  ``"1.91:1"`` for share-card-backed frames.
* ``buttons`` — a single ``"View Simulation →"`` link-action that
  takes the reader to the SPA share landing.
* ``has_trajectory`` — signal flag the share-page renderer flips to
  decide whether to emit Frame tags at all. ``False`` suppresses tag
  injection so a sim with no chart data doesn't poison the cast with
  a blank Frame image.

Design notes
------------

* **Pure stdlib.** ``os`` + ``re`` + the existing
  ``chart_svg.load_trajectory_for_chart`` helper. No new deps. The
  share-page renderer ``app/api/share.py`` consumes the dict
  directly — no HTTP round-trip.
* **Aligned with the share-page proxy logic.** The ``base_url`` is
  passed in by the caller (the share blueprint already honours
  ``X-Forwarded-Proto`` / ``X-Forwarded-Host``) so deployments behind
  a TLS-terminating reverse proxy emit Frame tags with the public
  origin, not the WSGI ``SERVER_NAME``.
* **Title truncation.** Farcaster has no documented hard limit on the
  scenario title, but 80 chars matches the chart-SVG title cap (so
  the Frame image and the metadata title agree) and avoids excessive
  ``<meta>`` length when the share page is fetched by a Warpcast crawl.
* **No raw HTML escaping here.** Callers escape on injection — the
  share blueprint uses ``html.escape`` for OG tags and reuses that
  helper for Frame tags. Returning raw values keeps the API endpoint
  emitting clean JSON without double-encoding.

References
----------

* Farcaster Frame v2 spec: https://docs.farcaster.xyz/developers/frames/v2/spec
* Frame image aspect ratios: only ``1.91:1`` and ``2:1`` render
  predictably across clients (anything else letterboxes).
* Twitter Card / OG / oEmbed live as separate quadrants on the same
  share page — the share blueprint emits all four; Frame tags are
  silently ignored by non-Farcaster scrapers.
"""

from __future__ import annotations

import os
import re
from typing import Optional


# ── Constants ─────────────────────────────────────────────────────────────


# Maximum scenario-title length in the Frame metadata payload. Matches
# the chart-SVG title cap so the metadata title and the image title
# agree on truncation. Picked over 100 because the Warpcast feed view
# wraps very long titles awkwardly under the Frame image.
SIM_TITLE_MAX_CHARS = 80


# Frame v2 protocol version literal. The spec accepts both ``"vNext"``
# (legacy) and ``"next"`` (current); every Frame-aware Farcaster client
# in production reads ``"next"``, so that's what we emit.
FRAME_VERSION = "next"


# Button label — Frame buttons are capped at 256 bytes in the spec;
# the standard one-button "view simulation" CTA is a UX convention
# borrowed from the share-card unfurl across Twitter / Discord / Slack.
DEFAULT_BUTTON_LABEL = "View Simulation →"


# Frame image aspect ratios. The spec only honours these two values
# across every client — anything else letterboxes inside the cast feed.
ASPECT_CHART_SVG = "2:1"        # chart.svg viewBox 800×400 = 2:1
ASPECT_SHARE_CARD = "1.91:1"    # share-card.png 1200×630 ≈ 1.91:1


# ── Helpers ───────────────────────────────────────────────────────────────


def _truncate_title(text: str, limit: int = SIM_TITLE_MAX_CHARS) -> str:
    """Trim to ``limit`` characters with a trailing ellipsis on overflow.

    Empty / falsy values pass through as the empty string — callers
    treat that as "no scenario yet" and fall back to a generic title.
    """
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _has_trajectory_rows(sim_dir: str) -> bool:
    """Return ``True`` when the sim has at least one recorded round.

    Reuses ``chart_svg.load_trajectory_for_chart`` so the trajectory
    check stays consistent with what the chart-SVG renderer would
    actually have to draw. A sim mid-startup with no recorded rounds
    returns ``False`` and the share-page renderer falls back to the
    share-card PNG for the Frame image.
    """
    if not sim_dir or not os.path.isdir(sim_dir):
        return False
    # Local import — same pattern other renderers use to avoid a
    # circular import at package init time.
    from . import chart_svg

    rows = chart_svg.load_trajectory_for_chart(sim_dir)
    return bool(rows)


def _normalize_base_url(base_url: str) -> str:
    """Strip the trailing slash so we can append ``/share/<id>`` cleanly.

    The share blueprint already calls ``.rstrip("/")``; keeping the
    same normalization here means a caller that forgets matches what
    the URL builder elsewhere produces.
    """
    return (base_url or "").rstrip("/")


# ── Public API ────────────────────────────────────────────────────────────


def build_frame_metadata(
    sim_id: str,
    scenario: str,
    sim_dir: Optional[str],
    base_url: str,
    is_public: bool,
) -> dict:
    """Return the Farcaster Frame v2 metadata dict for a simulation.

    Returns a stable shape regardless of whether the sim has trajectory
    data — the ``has_trajectory`` flag and the ``image_url`` /
    ``image_aspect_ratio`` pair tell the caller what to do:

    * Published sim WITH trajectory → emit Frame tags pointing at
      ``chart.svg`` (2:1) — the bullish/neutral/bearish curve renders
      as the Frame image.
    * Published sim WITHOUT trajectory → emit Frame tags pointing at
      ``share-card.png`` (1.91:1) — the share-card preview renders
      instead, so a fresh sim still gets a Farcaster-ready unfurl
      while the trajectory accumulates.
    * Unpublished sim → ``is_publishable`` is ``False`` and the
      share-page renderer suppresses Frame tag injection entirely
      (private sims should not leak scenario detail through the cast).

    ``sim_dir`` may be ``None`` (sim exists but the data directory is
    not yet on disk) — the trajectory check just returns ``False`` and
    the caller falls back to the share-card image.
    """
    base = _normalize_base_url(base_url)
    title = _truncate_title(scenario)

    has_trajectory = _has_trajectory_rows(sim_dir or "")
    if has_trajectory:
        image_url = f"{base}/api/simulation/{sim_id}/chart.svg"
        image_aspect_ratio = ASPECT_CHART_SVG
    else:
        image_url = f"{base}/api/simulation/{sim_id}/share-card.png"
        image_aspect_ratio = ASPECT_SHARE_CARD

    share_target = f"{base}/share/{sim_id}"
    spa_target = f"{base}/simulation/{sim_id}/start"

    button = {
        "label": DEFAULT_BUTTON_LABEL,
        "action": "link",
        # Target the SPA route directly so the reader lands inside the
        # simulation viewer, not the OG-tag landing page (which would
        # immediately JS-redirect to the same destination — saving the
        # extra hop trims a frame of latency for the on-tap experience).
        "target": spa_target,
    }

    return {
        "sim_id": sim_id,
        "sim_title": title,
        "is_publishable": bool(is_public),
        "has_trajectory": has_trajectory,
        "frame_version": FRAME_VERSION,
        "image_url": image_url,
        "image_aspect_ratio": image_aspect_ratio,
        "share_url": share_target,
        "buttons": [button],
    }


def warpcast_compose_url(share_url: str) -> str:
    """Return a Warpcast compose URL that pre-fills the share link.

    Warpcast accepts a ``?embeds[]=`` query parameter on its compose
    endpoint — the operator clicks the link in the EmbedDialog, lands
    in the Warpcast composer with the share URL already populated, and
    can preview the Frame card before casting. The frontend uses this
    helper to build a "Compose on Warpcast" anchor next to the Frame
    metadata snippet.
    """
    from urllib.parse import quote

    if not share_url:
        return "https://warpcast.com/~/compose"
    return f"https://warpcast.com/~/compose?embeds[]={quote(share_url, safe='')}"


# Regex extracted as a module-level constant so the tests can re-import
# it for assertion without duplicating the pattern. Matches a Warpcast
# username with the same character set the Farcaster network enforces
# at registration (lowercase alphanumerics + dot + hyphen). Currently
# unused at runtime — kept here for the future "@operator on Farcaster"
# attribution surface that pairs with the Frame button.
_FARCASTER_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,15}$")
