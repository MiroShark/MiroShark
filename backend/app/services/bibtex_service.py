"""BibTeX academic citation export — closes the citation arc.

The reproduce.json blob (PR #79) carries every parameter needed to
reproduce a finished simulation; the OriginTrail DKG citation (PR #84)
anchors the bytes of that blob on-chain as cryptographic provenance;
the notebook.ipynb (PR #80) lets a researcher analyse the trajectory
in their IDE. ``GET /api/simulation/<id>/cite.bib`` adds the missing
layer: a one-call BibTeX ``@misc{…}`` entry that drops into LaTeX
paper sources, imports cleanly into Zotero / Mendeley via URL (both
readers consume ``text/plain`` BibTeX at an HTTP URL directly via
"Import from URL"), and carries both the reproduce.json SHA-256 (in
``note``) and the DKG asset locator (in ``annote``, when available) so
a reviewer can verify the citation points to the same simulation
parameters the author cited.

Design notes
------------

* **Pure stdlib.** ``hashlib`` + ``datetime`` + ``re``. No new
  dependencies — same posture as ``signal_service`` / ``badge_service``
  / ``repro_export``.

* **Stable citation key.** ``miroshark-{simulation_id[:16]}`` with
  non-``[A-Za-z0-9_-]`` characters stripped — the BibTeX grammar
  allows only those in the citation key. A future ``\\cite{}``
  reference resolves to the same key across re-renders of the entry,
  so an author who pinned the key once doesn't see their references
  silently rewire on a re-export.

* **Escapes the seven BibTeX specials.** ``&``, ``%``, ``$``, ``#``,
  ``_`` get the canonical backslash escape; ``{`` and ``}`` get the
  backslash-bracket escape; backslashes themselves get
  ``\\textbackslash{}``; carets and tildes get ``\\^{}`` and
  ``\\~{}``. A scenario containing "100% APY & a flash loan" parses
  cleanly in LaTeX. Newlines collapse to spaces — BibTeX is one
  line per field.

* **Bytewise stable.** Two calls with identical inputs produce
  identical bytes — the only timestamp-driven field is the optional
  ``% Generated:`` comment at the top, and the route handler omits it
  by default so the served bytes are hash-stable for downstream
  citation chains.

* **Defensive.** A missing scenario falls back to ``"Untitled
  MiroShark simulation"``. A missing or unparseable ``created_at``
  falls back to the current UTC year + month. The route handler treats
  ``LookupError`` on the underlying simulation as 404 upstream; this
  module assumes the caller has already validated the sim exists.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


SCHEMA_VERSION = "1"


# ── Citation key sanitization ─────────────────────────────────────────────
#
# BibTeX citation keys must match ``[A-Za-z0-9_-]+`` to round-trip
# cleanly through every parser. We trim to 16 chars (long enough to
# disambiguate sim ids whose prefix collides at 12, short enough to fit
# in a ``\\cite{}`` reference without wrapping in a typeset page) and
# strip any character outside the safe set.

_KEY_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]")
_KEY_PREFIX = "miroshark-"
_KEY_FALLBACK = _KEY_PREFIX + "unknown"


def _build_citation_key(simulation_id: Any) -> str:
    """Return a BibTeX-safe citation key for ``simulation_id``.

    Stable across re-renders: same input → same key. Missing /
    empty input degrades to ``"miroshark-unknown"`` rather than
    raising so the BibTeX entry is always well-formed.
    """
    if not isinstance(simulation_id, str):
        return _KEY_FALLBACK
    trimmed = simulation_id.strip()
    if not trimmed:
        return _KEY_FALLBACK
    short = trimmed[:16]
    sanitized = _KEY_SAFE_RE.sub("", short)
    if not sanitized:
        return _KEY_FALLBACK
    return f"{_KEY_PREFIX}{sanitized}"


# ── BibTeX special-character escaping ─────────────────────────────────────
#
# Order matters: we hide ``\\`` behind a NUL-delimited sentinel before
# escaping ``{`` / ``}`` so the ``\\textbackslash{}`` replacement
# doesn't get re-escaped on the next pass. The sentinel uses control
# characters that cannot appear in BibTeX field values, so the round-trip
# is safe even on hostile input.

_BACKSLASH_SENTINEL = "\x00BIBTEX_BS\x00"
_SIMPLE_ESCAPES: Tuple[Tuple[str, str], ...] = (
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("^", r"\^{}"),
    ("~", r"\~{}"),
)


def _escape_bibtex(value: Any) -> str:
    """Escape a string for inclusion inside a BibTeX field value.

    Handles the seven BibTeX specials plus backslash, brace, caret,
    and tilde. Collapses runs of whitespace to a single space so a
    scenario with embedded newlines parses as one logical line.
    ``None`` / non-string input returns the empty string rather than
    raising — the caller decides whether an empty field is acceptable.
    """
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\\", _BACKSLASH_SENTINEL)
    s = s.replace("{", r"\{").replace("}", r"\}")
    s = s.replace(_BACKSLASH_SENTINEL, r"\textbackslash{}")
    for old, new in _SIMPLE_ESCAPES:
        s = s.replace(old, new)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── Date parsing ──────────────────────────────────────────────────────────
#
# BibTeX expects ``year = {YYYY}`` and ``month = jan`` (or another
# three-letter month macro the standard styles understand). We resolve
# both from the ``created_at`` ISO-8601 timestamp the SimulationState
# carries; a missing or malformed timestamp falls back to the current
# UTC year / month so the entry is always well-formed.

_MONTH_BIBTEX: Tuple[str, ...] = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)


def _now_year_month() -> Tuple[str, str]:
    now = datetime.now(timezone.utc)
    return str(now.year), _MONTH_BIBTEX[now.month - 1]


def _extract_year_month(iso_str: Any) -> Tuple[str, str]:
    """Pull ``(year, month_macro)`` from an ISO-8601 timestamp.

    Accepts the ``YYYY-MM-DDTHH:MM:SS[+-HH:MM|Z]`` shape ``datetime
    .isoformat()`` produces, and degrades to a ``YYYY-MM`` prefix
    parse for any other shape. Unparseable input falls back to the
    current UTC year / month.
    """
    if not isinstance(iso_str, str) or not iso_str.strip():
        return _now_year_month()
    s = iso_str.strip()
    normalized = s[:-1] if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(normalized)
        month_idx = dt.month - 1
        if 0 <= month_idx < 12:
            return str(dt.year), _MONTH_BIBTEX[month_idx]
    except ValueError:
        pass
    if len(s) >= 7 and s[4] == "-":
        year_part = s[:4]
        try:
            mm = int(s[5:7])
            if 1 <= mm <= 12 and year_part.isdigit():
                return year_part, _MONTH_BIBTEX[mm - 1]
        except ValueError:
            pass
    return _now_year_month()


# ── Title composition ─────────────────────────────────────────────────────


_TITLE_FALLBACK = "Untitled MiroShark simulation"
_TITLE_MAX_CHARS = 200


def _compose_title(scenario: Any, *, max_chars: int = _TITLE_MAX_CHARS) -> str:
    """Return a single-line citation title from the scenario text.

    Trims to ``max_chars`` with an ellipsis. Collapses internal
    whitespace. Empty / missing input falls back to the standard
    placeholder so the BibTeX entry always carries a title.
    """
    if not isinstance(scenario, str) or not scenario.strip():
        return _TITLE_FALLBACK
    cleaned = re.sub(r"\s+", " ", scenario).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "…"
    return cleaned


# ── SHA-256 helpers ───────────────────────────────────────────────────────


def _sha256_hex(payload: bytes) -> str:
    """Return the lower-case hex digest of the SHA-256 of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


def _extract_dkg_sha(dkg_citation: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the ``reproduce.json`` SHA-256 stored on a DKG citation.

    The DKG publisher persists the hash as ``"sha256:<hex>"`` to make
    the on-chain literal self-describing; we strip the prefix here so
    the BibTeX ``note`` field carries the bare hex digest a reviewer
    pastes into ``sha256sum --check``.
    """
    if not isinstance(dkg_citation, dict):
        return None
    raw = dkg_citation.get("reproduce_config_sha256")
    if not isinstance(raw, str) or not raw.strip():
        return None
    payload = raw.strip()
    if payload.lower().startswith("sha256:"):
        payload = payload.split(":", 1)[-1].strip()
    payload = payload.lower()
    if re.fullmatch(r"[0-9a-f]{64}", payload):
        return payload
    return None


def _extract_dkg_ual(dkg_citation: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the OriginTrail UAL stored on a DKG citation, if any."""
    if not isinstance(dkg_citation, dict):
        return None
    raw = dkg_citation.get("ual")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


# ── Public builder ────────────────────────────────────────────────────────


def build_bibtex(
    *,
    simulation_id: str,
    scenario: Any,
    created_at: Any,
    base_url: str,
    reproduce_json_bytes: Optional[bytes] = None,
    dkg_citation: Optional[Dict[str, Any]] = None,
    author: Any = None,
) -> str:
    """Render a single ``@misc{…}`` BibTeX entry for a published sim.

    Keyword args:
        simulation_id: The canonical sim id (``sim_…``). Drives the
            citation key + URL.
        scenario: The scenario / requirement text — the citation title.
        created_at: ISO-8601 timestamp from ``SimulationState.created_at``
            — drives ``year`` + ``month``.
        base_url: Absolute base URL of the deployment (no trailing
            slash). Used to build the share URL + reproduce.json URL.
            An empty / missing base degrades to relative paths.
        reproduce_json_bytes: The canonical reproduce.json bytes whose
            SHA-256 lands in the ``note`` field. Optional — when a
            DKG citation is also supplied, the DKG hash takes precedence
            (the on-chain anchor is the source of truth).
        dkg_citation: Optional persisted DKG citation dict (the shape
            ``dkg_publisher.read_citation`` returns). Drives the
            ``annote`` field's ``ual`` reference and overrides the
            SHA-256 source.
        author: Optional operator name. Defaults to ``{MiroShark}``
            (brace-wrapped so BibTeX treats it as a corporate author
            rather than parsing the string as ``last, first``).

    Returns:
        A complete BibTeX entry as a string ending with a trailing
        newline so concatenation with another entry produces a
        well-formed ``.bib`` library.
    """
    base = (base_url or "").rstrip("/")
    cite_key = _build_citation_key(simulation_id)
    title = _escape_bibtex(_compose_title(scenario))
    year, month = _extract_year_month(created_at)

    sim_id_for_url = simulation_id if isinstance(simulation_id, str) and simulation_id.strip() else ""
    share_url = f"{base}/share/{sim_id_for_url}" if base else f"/share/{sim_id_for_url}"
    reproduce_url = (
        f"{base}/api/simulation/{sim_id_for_url}/reproduce.json"
        if base
        else f"/api/simulation/{sim_id_for_url}/reproduce.json"
    )

    if author is None or not str(author).strip():
        author_field = "{MiroShark}"
    else:
        author_field = "{" + _escape_bibtex(author) + "}"

    sha256 = _extract_dkg_sha(dkg_citation)
    if not sha256 and isinstance(reproduce_json_bytes, (bytes, bytearray)):
        sha256 = _sha256_hex(bytes(reproduce_json_bytes))

    ual = _extract_dkg_ual(dkg_citation)

    lines = [
        f"@misc{{{cite_key},",
        f"  title        = {{{title}}},",
        f"  author       = {author_field},",
        f"  year         = {{{year}}},",
        f"  month        = {month},",
        f"  url          = {{{share_url}}},",
        f"  howpublished = {{\\url{{{reproduce_url}}}}},",
    ]
    if sha256:
        lines.append(f"  note         = {{Reproducibility SHA-256: {sha256}}},")
    if ual:
        ual_escaped = _escape_bibtex(ual)
        lines.append(f"  annote       = {{OriginTrail DKG UAL: {ual_escaped}}},")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def render_bibtex_bytes(**kwargs: Any) -> bytes:
    """UTF-8-encoded form of :func:`build_bibtex` for the route handler.

    Same posture as ``repro_export.render_json_bytes`` /
    ``badge_service.render_badge_svg_bytes`` — the route hands the
    bytes straight to Flask's ``Response`` constructor and the bytes
    are cite-hash-stable across calls with identical inputs.
    """
    return build_bibtex(**kwargs).encode("utf-8")
