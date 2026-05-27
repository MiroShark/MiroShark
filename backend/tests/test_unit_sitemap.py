"""Unit tests for the search-engine sitemap renderer.

Pure offline — no Flask boot, no SimulationManager, no LLM. The
``GET /sitemap.xml`` and ``GET /robots.txt`` endpoints are pure
projections over the on-disk public-sim corpus, so the test surface
mirrors the on-disk contract:

  1. ``MAX_SITEMAP_URLS`` is the documented 50,000 cap (sitemap spec
     ceiling) — a future refactor must not silently lift it.
  2. ``SITEMAP_NAMESPACE`` matches the sitemap protocol 0.9 string.
  3. ``SHARE_PRIORITY`` and ``WATCH_PRIORITY`` are pinned so the
     relative ranking between the two surfaces stays stable.
  4. Empty corpus produces a valid (empty) ``<urlset>`` document
     rather than 500ing the route.
  5. A single public sim contributes two ``<url>`` blocks (share +
     watch), with absolute ``<loc>`` URLs derived from ``base_url``.
  6. Private sims are excluded from the sitemap.
  7. ``<lastmod>`` is rendered in W3C ``YYYY-MM-DD`` form.
  8. ``<changefreq>`` is ``always`` for in-progress sims, ``weekly``
     for completed share entries, ``daily`` for completed watch
     entries.
  9. The serialized document is byte-deterministic given the same
     corpus (sims sorted by id), which lets the route layer set a
     meaningful ``ETag`` if it ever wants to.
 10. ``MAX_SITEMAP_URLS`` cap is honored — extra sims past the cap
     are dropped without raising.
 11. ``robots.txt`` always emits the ``Disallow: /api/`` directive
     and the per-surface ``Allow:`` lines.
 12. ``robots.txt`` advertises the ``Sitemap:`` line when enabled
     and omits it when disabled.
 13. The XML round-trips via ``ET.fromstring`` (well-formed).
 14. Routes are registered on the sitemap blueprint
     (drift-detection guard against the route decorators going
     missing).
 15. The application factory mounts ``sitemap_bp`` at the root
     (catches the failure mode where the blueprint exists but
     wasn't wired into ``create_app``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from xml.etree import ElementTree as ET



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import sitemap as sitemap_service  # noqa: E402


SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


# ── Module-level invariants ────────────────────────────────────────────


def test_max_sitemap_urls_pinned_to_spec_ceiling():
    """50,000 is the sitemap-protocol ceiling per file."""
    assert sitemap_service.MAX_SITEMAP_URLS == 50_000


def test_sitemap_namespace_matches_protocol_0_9():
    """The namespace string is part of the spec — wrong value ⇒ ignored by Googlebot."""
    assert (
        sitemap_service.SITEMAP_NAMESPACE
        == "http://www.sitemaps.org/schemas/sitemap/0.9"
    )


def test_priorities_pinned():
    """Share is the canonical citation surface, watch is one notch lower."""
    assert sitemap_service.SHARE_PRIORITY == "0.8"
    assert sitemap_service.WATCH_PRIORITY == "0.7"


def test_changefreq_constants():
    """In-progress ⇒ always; completed ⇒ weekly (share)."""
    assert sitemap_service.RUNNING_CHANGEFREQ == "always"
    assert sitemap_service.COMPLETED_CHANGEFREQ == "weekly"


# ── Fixture helpers ────────────────────────────────────────────────────


class _StubStatus:
    """Mimics the .value attribute on the real SimulationStatus enum."""

    def __init__(self, value: str) -> None:
        self.value = value


class _StubSim:
    """Tiny stand-in for SimulationState — only the fields the sitemap reads."""

    def __init__(
        self,
        sim_id: str,
        *,
        is_public: bool = True,
        status: str = "completed",
        created_at: str = "2026-05-01T10:00:00",
        updated_at: str | None = None,
    ) -> None:
        self.simulation_id = sim_id
        self.is_public = is_public
        self.status = _StubStatus(status)
        self.created_at = created_at
        self.updated_at = updated_at


def _parse(body: bytes) -> ET.Element:
    """Verify the document round-trips through ElementTree."""
    return ET.fromstring(body.decode("utf-8"))


def _urls(root: ET.Element) -> list[ET.Element]:
    return list(root.findall(f"{SITEMAP_NS}url"))


def _child_text(url_el: ET.Element, name: str) -> str | None:
    el = url_el.find(f"{SITEMAP_NS}{name}")
    return el.text if el is not None else None


# ── Empty / one-sim cases ──────────────────────────────────────────────


def test_empty_corpus_produces_valid_empty_urlset():
    """No sims ⇒ valid (empty) ``<urlset>`` rather than 500."""
    body = sitemap_service.build_sitemap([], "https://miroshark.app")
    root = _parse(body)
    assert root.tag == f"{SITEMAP_NS}urlset"
    assert _urls(root) == []
    # Header guards
    assert body.startswith(b"<?xml")
    assert body.endswith(b"\n")


def test_single_public_sim_produces_share_plus_watch_blocks():
    """One sim ⇒ two ``<url>`` blocks (share + watch), absolute URLs."""
    body = sitemap_service.build_sitemap(
        [_StubSim("sim_alpha123")],
        "https://miroshark.app",
    )
    root = _parse(body)
    urls = _urls(root)
    assert len(urls) == 2
    locs = [_child_text(u, "loc") for u in urls]
    assert locs == [
        "https://miroshark.app/share/sim_alpha123",
        "https://miroshark.app/watch/sim_alpha123",
    ]


def test_private_sims_are_excluded():
    """Operators forking privately don't leak into search."""
    sims = [
        _StubSim("sim_publicA"),
        _StubSim("sim_privateB", is_public=False),
        _StubSim("sim_publicC"),
    ]
    body = sitemap_service.build_sitemap(sims, "https://miroshark.app")
    root = _parse(body)
    locs = {_child_text(u, "loc") for u in _urls(root)}
    assert "https://miroshark.app/share/sim_publicA" in locs
    assert "https://miroshark.app/share/sim_publicC" in locs
    assert not any("sim_privateB" in loc for loc in locs)


def test_sims_without_id_are_skipped():
    """A SimulationState with a missing id never produces a malformed loc."""
    sims = [
        _StubSim(""),
        _StubSim("sim_realID"),
    ]
    body = sitemap_service.build_sitemap(sims, "https://miroshark.app")
    root = _parse(body)
    locs = [_child_text(u, "loc") for u in _urls(root)]
    assert all("sim_realID" in loc for loc in locs)
    # Two entries (share + watch) for the one valid sim
    assert len(locs) == 2


# ── lastmod / changefreq semantics ─────────────────────────────────────


def test_lastmod_renders_w3c_date_form():
    """``YYYY-MM-DD`` matches the sitemap spec's day-precision norm."""
    sims = [_StubSim("sim_X", updated_at="2026-05-14T12:34:56Z")]
    body = sitemap_service.build_sitemap(sims, "https://miroshark.app")
    root = _parse(body)
    urls = _urls(root)
    for u in urls:
        assert _child_text(u, "lastmod") == "2026-05-14"


def test_lastmod_falls_back_to_created_at_then_state_mtime(tmp_path):
    """No updated_at ⇒ created_at ⇒ state.json mtime, in that order."""
    sims = [_StubSim("sim_create_only", updated_at=None, created_at="2026-04-15T08:00:00")]
    body = sitemap_service.build_sitemap(sims, "https://miroshark.app")
    root = _parse(body)
    urls = _urls(root)
    for u in urls:
        assert _child_text(u, "lastmod") == "2026-04-15"

    # Now strip both timestamps and rely on the state.json mtime.
    sim = _StubSim("sim_mtime", created_at="", updated_at=None)
    sim_dir = tmp_path / "sim_mtime"
    sim_dir.mkdir()
    state_json = sim_dir / "state.json"
    state_json.write_text("{}", encoding="utf-8")
    fixed_ts = 1715600000  # 2024-05-13T13:13:20Z
    os.utime(state_json, (fixed_ts, fixed_ts))

    body = sitemap_service.build_sitemap(
        [sim],
        "https://miroshark.app",
        sim_data_dir=str(tmp_path),
    )
    root = _parse(body)
    urls = _urls(root)
    # mtime falls back to a real date string; we don't assert the exact
    # day (it's tz-dependent) — just that the element is present and
    # well-formed.
    for u in urls:
        text = _child_text(u, "lastmod")
        assert text is not None
        assert len(text) == 10
        assert text[4] == "-" and text[7] == "-"


def test_changefreq_completed_sim_is_weekly_for_share_and_daily_for_watch():
    """Completed sims are stable artifacts — ``weekly`` for share, ``daily`` for watch."""
    body = sitemap_service.build_sitemap(
        [_StubSim("sim_done", status="completed")],
        "https://miroshark.app",
    )
    root = _parse(body)
    urls = _urls(root)
    assert _child_text(urls[0], "changefreq") == "weekly"
    assert _child_text(urls[1], "changefreq") == "daily"


def test_changefreq_in_progress_sim_is_always_for_both_surfaces():
    """In-progress sims change every round — ``always`` matches reality."""
    body = sitemap_service.build_sitemap(
        [_StubSim("sim_live", status="running")],
        "https://miroshark.app",
    )
    root = _parse(body)
    urls = _urls(root)
    assert _child_text(urls[0], "changefreq") == "always"
    assert _child_text(urls[1], "changefreq") == "always"


def test_priority_share_higher_than_watch():
    """Share is the canonical citation surface; watch is one notch below."""
    body = sitemap_service.build_sitemap(
        [_StubSim("sim_pri")],
        "https://miroshark.app",
    )
    root = _parse(body)
    urls = _urls(root)
    assert _child_text(urls[0], "priority") == "0.8"
    assert _child_text(urls[1], "priority") == "0.7"


# ── Determinism / cap ──────────────────────────────────────────────────


def test_serialization_is_deterministic_for_same_corpus():
    """Identical input ⇒ identical bytes (order is by simulation_id)."""
    sims = [
        _StubSim("sim_b"),
        _StubSim("sim_a"),
        _StubSim("sim_c"),
    ]
    body_one = sitemap_service.build_sitemap(sims, "https://miroshark.app")
    # Pass the sims in a different order — the renderer must still
    # produce identical bytes because it sorts internally.
    body_two = sitemap_service.build_sitemap(
        list(reversed(sims)),
        "https://miroshark.app",
    )
    assert body_one == body_two

    root = _parse(body_one)
    locs = [_child_text(u, "loc") for u in _urls(root)]
    # Sorted ascending by id ⇒ a, a, b, b, c, c
    expected = [
        "https://miroshark.app/share/sim_a",
        "https://miroshark.app/watch/sim_a",
        "https://miroshark.app/share/sim_b",
        "https://miroshark.app/watch/sim_b",
        "https://miroshark.app/share/sim_c",
        "https://miroshark.app/watch/sim_c",
    ]
    assert locs == expected


def test_max_urls_cap_is_honored():
    """Sims past the cap are dropped without raising."""
    # Cap at 4 ⇒ 2 sims (each contributes 2 url blocks).
    sims = [_StubSim(f"sim_{i:03d}") for i in range(10)]
    body = sitemap_service.build_sitemap(
        sims,
        "https://miroshark.app",
        max_urls=4,
    )
    root = _parse(body)
    urls = _urls(root)
    assert len(urls) == 4
    locs = [_child_text(u, "loc") for u in _urls(root)]
    # Sorted ascending ⇒ first two sims (000 and 001) make the cut.
    assert locs == [
        "https://miroshark.app/share/sim_000",
        "https://miroshark.app/watch/sim_000",
        "https://miroshark.app/share/sim_001",
        "https://miroshark.app/watch/sim_001",
    ]


# ── robots.txt ─────────────────────────────────────────────────────────


def test_robots_always_disallows_api_namespace():
    """Even with sitemap disabled, the API surface is gated from crawlers."""
    body = sitemap_service.build_robots_txt("https://miroshark.app", enabled=False)
    text = body.decode("utf-8")
    assert "User-agent: *" in text
    assert "Disallow: /api/" in text
    assert "Allow: /share/" in text
    assert "Allow: /watch/" in text


def test_robots_advertises_sitemap_when_enabled():
    """Compliant crawlers discover ``/sitemap.xml`` automatically when enabled."""
    body = sitemap_service.build_robots_txt(
        "https://miroshark.app", enabled=True
    )
    text = body.decode("utf-8")
    assert "Sitemap: https://miroshark.app/sitemap.xml" in text


def test_robots_omits_sitemap_when_disabled():
    """Private deployments don't leak the sitemap URL via robots.txt."""
    body = sitemap_service.build_robots_txt(
        "https://miroshark.app", enabled=False
    )
    text = body.decode("utf-8")
    assert "Sitemap:" not in text


def test_robots_omits_sitemap_when_base_url_blank_even_if_enabled():
    """A misconfigured deployment without PUBLIC_BASE_URL skips the line."""
    body = sitemap_service.build_robots_txt("", enabled=True)
    text = body.decode("utf-8")
    assert "Sitemap:" not in text
    assert "Disallow: /api/" in text


# ── XML well-formedness ────────────────────────────────────────────────


def test_sitemap_xml_is_well_formed_with_declaration_and_namespace():
    """The whole document round-trips and carries the spec declarations."""
    sims = [_StubSim("sim_one"), _StubSim("sim_two")]
    body = sitemap_service.build_sitemap(sims, "https://miroshark.app")

    text = body.decode("utf-8")
    assert text.startswith("<?xml")
    assert "encoding='utf-8'" in text or 'encoding="utf-8"' in text

    root = _parse(body)
    assert root.tag.endswith("urlset")
    assert "http://www.sitemaps.org/schemas/sitemap/0.9" in root.tag


# ── Wiring guards ──────────────────────────────────────────────────────


def test_sitemap_route_decorator_present():
    """``GET /sitemap.xml`` must be registered on sitemap_bp."""
    api_path = _BACKEND / "app" / "api" / "sitemap.py"
    text = api_path.read_text(encoding="utf-8")
    assert '@sitemap_bp.route("/sitemap.xml"' in text
    assert "def sitemap_xml(" in text


def test_robots_route_decorator_present():
    """``GET /robots.txt`` must be registered on sitemap_bp."""
    api_path = _BACKEND / "app" / "api" / "sitemap.py"
    text = api_path.read_text(encoding="utf-8")
    assert '@sitemap_bp.route("/robots.txt"' in text
    assert "def robots_txt(" in text


def test_sitemap_config_route_decorator_present():
    """``GET /api/config/sitemap`` exposes the flag to the SPA."""
    api_path = _BACKEND / "app" / "api" / "sitemap.py"
    text = api_path.read_text(encoding="utf-8")
    assert '@sitemap_bp.route("/api/config/sitemap"' in text
    assert "def sitemap_config(" in text


def test_app_factory_registers_sitemap_blueprint():
    """The blueprint must be mounted on ``create_app`` — catches the
    failure mode where the file exists but wasn't wired in."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "sitemap_bp" in text
    assert "app.register_blueprint(sitemap_bp)" in text


def test_blueprint_module_exports_sitemap_bp():
    """``app.api`` must re-export ``sitemap_bp`` for the factory import."""
    api_init = _BACKEND / "app" / "api" / "__init__.py"
    text = api_init.read_text(encoding="utf-8")
    assert "from .sitemap import sitemap_bp" in text


def test_config_exposes_enable_sitemap_flag():
    """``ENABLE_SITEMAP`` must be readable off the Config class so the
    routes can gate on it. Defaults to True."""
    config_path = _BACKEND / "app" / "config.py"
    text = config_path.read_text(encoding="utf-8")
    assert "ENABLE_SITEMAP" in text
    # The default must be true so the public-discovery posture is
    # opt-out rather than opt-in.
    assert "ENABLE_SITEMAP" in text and "'true'" in text
