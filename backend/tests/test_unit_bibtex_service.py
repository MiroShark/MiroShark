"""Unit tests for the BibTeX academic citation renderer.

Pure offline — no Flask, no network, no simulation runner, no on-disk
state. Covers the properties the ``/cite.bib`` endpoint depends on:

  1. Citation key has the ``miroshark-`` prefix + the first 16 chars
     of the simulation id, with non-``[A-Za-z0-9_-]`` chars stripped.
  2. Title escapes the seven BibTeX specials cleanly.
  3. Year + month derive from ISO-8601 ``created_at``; bad input
     falls back to the current UTC year + month rather than raising.
  4. SHA-256 in the ``note`` field comes from the DKG citation when
     present, falls back to a fresh hash of the passed-in reproduce
     bytes, and is omitted entirely when neither is available.
  5. ``annote`` carries the OriginTrail UAL when the DKG citation
     records one, and is omitted when not.
  6. URLs use the supplied ``base_url`` (with a trailing slash
     stripped) so concatenation produces valid absolute URLs.
  7. Author defaults to ``{MiroShark}`` (brace-wrapped so BibTeX
     treats it as a corporate author).
  8. Rendered bytes are bytewise-deterministic across calls with
     identical inputs — important so a citation chain anchored
     against the entry's bytes (a future ETag layer) is hash-stable.
  9. Route + content-type wiring on the served endpoint (static
     scan of the route file — the live integration belongs in the
     server-up suite).
 10. ``cite_bib`` is registered in the surface_stats schema and the
     handler references the counter key.
 11. Defensive fallbacks: missing scenario → ``"Untitled MiroShark
     simulation"``; missing / empty simulation_id → ``"miroshark-
     unknown"`` citation key; missing base_url → relative URLs;
     extremely long scenario → ellipsised at 200 chars.
"""

from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Property 1 — citation key shape ───────────────────────────────────────


def test_citation_key_prefixes_with_miroshark_and_uses_first_chars():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc123def456ghi789",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    # First 16 chars of the sim id post-prefix-strip, sanitized.
    assert "@misc{miroshark-sim_abc123def456," in body


def test_citation_key_strips_non_alphanumeric_chars():
    """BibTeX grammar only allows ``[A-Za-z0-9_-]`` in citation keys —
    a UUID containing dots or colons would otherwise break ``\\cite``."""
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim.abc:123/foo",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    m = re.search(r"@misc\{([^,]+),", body)
    assert m is not None
    key = m.group(1)
    assert key.startswith("miroshark-")
    # No punctuation other than dash / underscore inside the key.
    body_of_key = key.removeprefix("miroshark-")
    assert re.fullmatch(r"[A-Za-z0-9_-]+", body_of_key)


def test_citation_key_missing_id_falls_back_to_unknown():
    from app.services.bibtex_service import build_bibtex

    for bad_id in ("", "   ", None):
        body = build_bibtex(
            simulation_id=bad_id,  # type: ignore[arg-type]
            scenario="A scenario",
            created_at="2026-05-20T12:34:56Z",
            base_url="https://example.com",
        )
        assert "@misc{miroshark-unknown," in body


# ── Property 2 — title escapes BibTeX specials ────────────────────────────


def test_title_escapes_ampersand_percent_underscore():
    """Scenario with ``& % _`` must render as ``\\& \\% \\_`` so a
    LaTeX compile of the citing paper doesn't choke on the entry."""
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="100% APY & a flash_loan exploit",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert r"100\% APY \& a flash\_loan exploit" in body


def test_title_escapes_dollar_hash_caret_tilde():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="$AEON #1 token ^over ~approximately",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert r"\$AEON" in body
    assert r"\#1" in body
    assert r"\^{}over" in body
    assert r"\~{}approximately" in body


def test_title_escapes_braces_and_backslash():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario=r"a {risky} \trade",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert r"\{risky\}" in body
    assert r"\textbackslash{}trade" in body


def test_title_collapses_internal_whitespace():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="multi\n line\t  scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert "title        = {multi line scenario}" in body


# ── Property 3 — year + month derivation ──────────────────────────────────


@pytest.mark.parametrize(
    "iso, expected_year, expected_month",
    [
        ("2026-05-20T12:34:56Z", "2026", "may"),
        ("2026-01-01T00:00:00+00:00", "2026", "jan"),
        ("2025-12-31T23:59:59-08:00", "2025", "dec"),
        ("2024-07-04", "2024", "jul"),
        ("2026-05", "2026", "may"),
    ],
)
def test_year_month_from_well_formed_iso(iso, expected_year, expected_month):
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at=iso,
        base_url="https://example.com",
    )
    assert f"year         = {{{expected_year}}}" in body
    assert f"month        = {expected_month}" in body


def test_year_month_missing_falls_back_to_now_utc():
    """Missing / unparseable ``created_at`` must not raise; the entry
    is always well-formed."""
    from app.services.bibtex_service import build_bibtex

    now = datetime.now(timezone.utc)
    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at=None,
        base_url="https://example.com",
    )
    assert f"year         = {{{now.year}}}" in body

    body2 = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="not-a-date",
        base_url="https://example.com",
    )
    assert f"year         = {{{now.year}}}" in body2


# ── Property 4 — SHA-256 source precedence ────────────────────────────────


def test_sha256_from_dkg_citation_takes_precedence():
    """When a DKG citation is present, its on-chain hash beats the
    locally-computed hash of the reproduce.json bytes — the on-chain
    anchor is the source of truth once a sim has been published."""
    from app.services.bibtex_service import build_bibtex

    on_chain_hex = "a" * 64
    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        reproduce_json_bytes=b"{\"different\": true}",
        dkg_citation={"reproduce_config_sha256": f"sha256:{on_chain_hex}"},
    )
    assert f"note         = {{Reproducibility SHA-256: {on_chain_hex}}}," in body


def test_sha256_falls_back_to_fresh_hash_of_reproduce_bytes():
    from app.services.bibtex_service import build_bibtex

    payload = b'{"schema_version": "1", "simulation_id": "sim_abc"}'
    expected = hashlib.sha256(payload).hexdigest()
    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        reproduce_json_bytes=payload,
        dkg_citation=None,
    )
    assert f"note         = {{Reproducibility SHA-256: {expected}}}," in body


def test_sha256_omitted_when_neither_dkg_nor_reproduce_bytes_supplied():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        reproduce_json_bytes=None,
        dkg_citation=None,
    )
    assert "note" not in body


def test_dkg_sha_rejects_malformed_payload():
    """Non-hex / wrong-length DKG hash must fall back to the fresh
    computation rather than producing a corrupted entry."""
    from app.services.bibtex_service import build_bibtex

    payload = b'{"reproduce": "blob"}'
    expected = hashlib.sha256(payload).hexdigest()
    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        reproduce_json_bytes=payload,
        dkg_citation={"reproduce_config_sha256": "sha256:not-hex"},
    )
    assert f"note         = {{Reproducibility SHA-256: {expected}}}," in body


# ── Property 5 — annote carries UAL ───────────────────────────────────────


def test_annote_carries_ual_when_dkg_citation_records_one():
    from app.services.bibtex_service import build_bibtex

    ual = "did:dkg:base:8453/0xabc/12345"
    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        dkg_citation={"ual": ual, "reproduce_config_sha256": "sha256:" + "b" * 64},
    )
    # UAL contains a colon — must NOT be escaped, but it's never a
    # BibTeX special either, so the raw value passes through.
    assert f"annote       = {{OriginTrail DKG UAL: {ual}}}," in body


def test_annote_omitted_without_dkg_citation():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert "annote" not in body


# ── Property 6 — URL composition ──────────────────────────────────────────


def test_share_url_uses_base_url_without_trailing_slash():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://miroshark.example.com/",
    )
    assert "url          = {https://miroshark.example.com/share/sim_abc}," in body
    assert (
        "howpublished = {\\url{https://miroshark.example.com/api/simulation/sim_abc/reproduce.json}},"
        in body
    )


def test_missing_base_url_degrades_to_relative_paths():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="",
    )
    assert "url          = {/share/sim_abc}," in body


# ── Property 7 — author defaults ──────────────────────────────────────────


def test_author_defaults_to_brace_wrapped_miroshark():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert "author       = {MiroShark}," in body


def test_explicit_author_overrides_default():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        author="Aaron J. Mars",
    )
    assert "author       = {Aaron J. Mars}," in body


# ── Property 8 — bytewise determinism ─────────────────────────────────────


def test_rendered_bytes_are_deterministic_across_calls():
    from app.services.bibtex_service import render_bibtex_bytes

    kwargs = dict(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
        reproduce_json_bytes=b"{}",
        dkg_citation={"ual": "did:dkg:foo", "reproduce_config_sha256": "sha256:" + "c" * 64},
    )
    one = render_bibtex_bytes(**kwargs)
    two = render_bibtex_bytes(**kwargs)
    assert one == two
    assert one.endswith(b"}\n")


def test_render_bytes_is_valid_utf8_and_starts_with_misc():
    from app.services.bibtex_service import render_bibtex_bytes

    payload = render_bibtex_bytes(
        simulation_id="sim_abc",
        scenario="A scenario",
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    decoded = payload.decode("utf-8")
    assert decoded.startswith("@misc{")


# ── Property 9 — route + content-type wiring ──────────────────────────────


def test_cite_bib_route_decorator_exists():
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert "/<simulation_id>/cite.bib" in text
    assert "def get_cite_bib" in text


def test_cite_bib_route_sets_plain_text_mimetype_and_inline_disposition():
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    # text/plain so Zotero "Import from URL" picks the right parser.
    assert "text/plain; charset=utf-8" in text
    # Inline disposition with the .bib filename so curl -OJ names it.
    assert ".bib\"" in text


# ── Property 10 — surface_stats registration + counter ────────────────────


def test_cite_bib_registered_in_surface_stats():
    from app.services.surface_stats import SURFACE_KEYS, read_surface_stats

    assert "cite_bib" in SURFACE_KEYS
    stats = read_surface_stats(None)
    assert stats["cite_bib"] == 0
    assert "total" in stats


def test_cite_bib_handler_increments_counter():
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert '"cite_bib"' in text


# ── Property 11 — defensive fallbacks ─────────────────────────────────────


def test_missing_scenario_falls_back_to_untitled_label():
    from app.services.bibtex_service import build_bibtex

    body = build_bibtex(
        simulation_id="sim_abc",
        scenario=None,
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    assert "title        = {Untitled MiroShark simulation}," in body


def test_extremely_long_scenario_ellipsises_at_200_chars():
    from app.services.bibtex_service import build_bibtex

    long_scenario = "A" * 500
    body = build_bibtex(
        simulation_id="sim_abc",
        scenario=long_scenario,
        created_at="2026-05-20T12:34:56Z",
        base_url="https://example.com",
    )
    # Title body capped to 200 chars + ellipsis.
    m = re.search(r"title\s+=\s+\{([^}]+)\}", body)
    assert m is not None
    title_body = m.group(1)
    assert title_body.endswith("…")
    # 200 "A"s + one ellipsis = 201 chars; allow a single trailing
    # whitespace strip either side.
    assert len(title_body) <= 201
