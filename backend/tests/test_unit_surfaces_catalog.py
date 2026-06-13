"""Unit tests for the machine-readable surface catalog service.

Pure offline — no Flask app context, no network, no on-disk state.
Cover the properties the ``GET /api/surfaces.json`` endpoint depends on:

  1. ``get_surfaces_catalog`` returns a non-empty list of dicts and
     every entry has the locked field set + valid types.
  2. ``catalog_count`` equals ``len(get_surfaces_catalog())``.
  3. ``catalog_etag`` is a deterministic short string keyed on the
     catalog length + schema version.
  4. ``build_response_payload`` returns the documented envelope shape
     (``schema_version`` + ``count`` + ``surfaces``).
  5. Every entry's ``type`` is one of the seven recognised category
     strings.
  6. Every entry's ``key`` is unique across the catalog — no two
     surfaces can claim the same key.
  7. Every entry's ``endpoint`` starts with ``/`` and every ``method``
     is ``GET`` or ``POST``.
  8. ``description`` is at most 120 chars and never empty.
  9. ``example_curl`` references the entry's endpoint path verbatim so
     a consumer copy-pasting the example actually hits the right URL.
 10. Per-sim share surfaces in the catalog stay in sync with
     ``surface_stats.SURFACE_KEYS`` — drift guard.
 11. ``get_surfaces_catalog`` returns fresh objects per call — mutating
     the result must not affect subsequent reads.
 12. The catalog includes a self-referential entry for
     ``surfaces_catalog`` so a consumer iterating the catalog discovers
     the endpoint they're currently calling.
 13. The catalog includes the platform-level entries (``platform_stats``
     and ``platform_stats_badge``) so an integrator can discover the
     ``/api/stats`` surfaces from the catalog alone.
 14. The catalog blueprint is registered in ``app/api/__init__.py`` and
     mounted on the Flask app — wiring guard so a future refactor that
     drops the blueprint also drops the test, not just the surface.
 15. The OpenAPI spec carries an entry for ``/api/surfaces.json`` so
     ``/api/docs`` lists the catalog endpoint.
 16. ``is_valid_surface_type`` accepts every recognised category and
     rejects unknown / non-string values.
 17. ``build_response_payload(type)`` returns only that category, the
     filtered counts partition the full catalog, and the no-filter call
     is unchanged (backward compatible).
 18. ``catalog_etag(type)`` is distinct per category and well-formed.
 19. The route reads ``?type=`` and 400s on an unknown value; the
     OpenAPI spec documents the ``type`` query parameter.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# Late import — keeps the suite collectable even if a future refactor
# moves the module.
from app.services import surfaces_catalog  # noqa: E402
from app.services import surface_stats  # noqa: E402


REQUIRED_FIELDS = {
    "key",
    "endpoint",
    "method",
    "type",
    "description",
    "added_in_pr",
    "example_curl",
}


VALID_METHODS = {"GET", "POST"}


# ── Schema invariants ──────────────────────────────────────────────────


def test_catalog_is_non_empty_list_of_dicts():
    catalog = surfaces_catalog.get_surfaces_catalog()
    assert isinstance(catalog, list)
    assert len(catalog) > 0
    for entry in catalog:
        assert isinstance(entry, dict)


def test_every_entry_has_locked_field_set():
    for entry in surfaces_catalog.get_surfaces_catalog():
        missing = REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"entry {entry.get('key')!r} missing: {missing}"


def test_catalog_count_matches_list_length():
    assert surfaces_catalog.catalog_count() == len(
        surfaces_catalog.get_surfaces_catalog()
    )


def test_keys_are_unique():
    keys = [entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()]
    assert len(keys) == len(set(keys)), f"duplicate keys: {keys}"


def test_every_entry_method_is_get_or_post():
    for entry in surfaces_catalog.get_surfaces_catalog():
        assert entry["method"] in VALID_METHODS, (
            f"entry {entry['key']!r} has invalid method {entry['method']!r}"
        )


def test_every_entry_endpoint_starts_with_slash():
    for entry in surfaces_catalog.get_surfaces_catalog():
        assert entry["endpoint"].startswith("/"), (
            f"entry {entry['key']!r} endpoint must start with '/'"
        )


def test_every_entry_type_is_recognised():
    for entry in surfaces_catalog.get_surfaces_catalog():
        assert entry["type"] in surfaces_catalog.SURFACE_TYPES, (
            f"entry {entry['key']!r} has unknown type {entry['type']!r}"
        )


def test_description_is_bounded_and_non_empty():
    for entry in surfaces_catalog.get_surfaces_catalog():
        desc = entry["description"]
        assert isinstance(desc, str)
        assert 0 < len(desc) <= 120, (
            f"entry {entry['key']!r} description length {len(desc)} out of bounds"
        )


def test_example_curl_references_the_entry_endpoint():
    """A consumer copy-pasting the example must hit the same path the
    catalog claims. Guards against a future refactor that renames a
    route but forgets to update ``example_curl``."""
    for entry in surfaces_catalog.get_surfaces_catalog():
        assert entry["endpoint"] in entry["example_curl"], (
            f"entry {entry['key']!r} example_curl does not reference its endpoint"
        )


def test_added_in_pr_is_nullable_positive_int():
    for entry in surfaces_catalog.get_surfaces_catalog():
        pr = entry["added_in_pr"]
        assert pr is None or (isinstance(pr, int) and pr > 0), (
            f"entry {entry['key']!r} added_in_pr {pr!r} must be None or positive int"
        )


# ── Cross-module invariants ────────────────────────────────────────────


def test_per_sim_tracked_keys_match_surface_keys():
    """The publish-gated per-sim subset of the catalog must stay in sync
    with ``surface_stats.SURFACE_KEYS``. A new per-sim surface ships in
    three places (handler, ``SURFACE_KEYS``, this catalog); this test
    enforces the third."""
    assert (
        surfaces_catalog._PER_SIM_TRACKED_KEYS
        == surface_stats.SURFACE_KEYS
    ), (
        "catalog per-sim tracked keys drifted from surface_stats.SURFACE_KEYS "
        f"— catalog only: {surfaces_catalog._PER_SIM_TRACKED_KEYS - surface_stats.SURFACE_KEYS}, "
        f"surface_stats only: {surface_stats.SURFACE_KEYS - surfaces_catalog._PER_SIM_TRACKED_KEYS}"
    )


def test_catalog_self_referential_entry_present():
    """A consumer iterating the catalog should discover the endpoint they
    are currently calling."""
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "surfaces_catalog" in keys


def test_catalog_includes_platform_stats_surfaces():
    """The platform-level aggregate surfaces (``/api/stats`` +
    ``/api/stats/badge.svg``) must appear in the catalog so an integrator
    can discover them without reading docs."""
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "platform_stats" in keys
    assert "platform_stats_badge" in keys
    # Per-project sibling — same discoverability requirement.
    assert "project_stats" in keys


def test_catalog_includes_polymarket_signal_and_volatility():
    """Three high-traffic per-sim surfaces are the integrator litmus
    test for the catalog being useful — if any are missing, the catalog
    is incomplete by definition."""
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "polymarket_json" in keys
    assert "signal_json" in keys
    assert "volatility" in keys


# ── ETag + envelope ────────────────────────────────────────────────────


def test_catalog_etag_is_deterministic_short_string():
    etag = surfaces_catalog.catalog_etag()
    assert isinstance(etag, str)
    assert len(etag) <= 32
    # Two calls inside the same process return the same string.
    assert surfaces_catalog.catalog_etag() == etag
    # ETag must change when the catalog length changes — encoded as
    # part of the literal so a regex covers it.
    assert re.fullmatch(r"surfaces-v\d+-\d+", etag), (
        f"etag {etag!r} does not match expected pattern"
    )


def test_build_response_payload_envelope_shape():
    payload = surfaces_catalog.build_response_payload()
    assert set(payload.keys()) == {"schema_version", "count", "surfaces"}
    assert payload["schema_version"] == surfaces_catalog.SCHEMA_VERSION
    assert payload["count"] == surfaces_catalog.catalog_count()
    assert isinstance(payload["surfaces"], list)
    assert len(payload["surfaces"]) == payload["count"]


def test_build_response_payload_is_json_serialisable():
    """The envelope is what the route handler hands to ``jsonify`` — a
    smoke test guards against a future entry whose value type doesn't
    survive ``json.dumps``."""
    payload = surfaces_catalog.build_response_payload()
    serialised = json.dumps(payload, sort_keys=True)
    assert serialised  # Non-empty after serialisation.
    # Round-trips back to the same shape.
    roundtripped = json.loads(serialised)
    assert roundtripped["count"] == payload["count"]


# ── Immutability ───────────────────────────────────────────────────────


def test_get_surfaces_catalog_returns_fresh_objects():
    """Mutating the returned list or its inner dicts must not affect
    subsequent calls. The catalog is module-level state; if the
    function handed out the live reference, a misbehaving caller could
    silently corrupt every future read."""
    catalog_a = surfaces_catalog.get_surfaces_catalog()
    catalog_a.clear()
    catalog_b = surfaces_catalog.get_surfaces_catalog()
    assert len(catalog_b) > 0, "outer list aliasing — clearing affected next call"

    catalog_c = surfaces_catalog.get_surfaces_catalog()
    catalog_c[0]["key"] = "MUTATED"
    catalog_d = surfaces_catalog.get_surfaces_catalog()
    assert catalog_d[0]["key"] != "MUTATED", (
        "inner dict aliasing — mutation affected next call"
    )


# ── Wiring guards ──────────────────────────────────────────────────────


def test_surfaces_blueprint_is_registered_in_api_module():
    """The blueprint must be importable from ``app.api`` so the app
    factory can register it. Drift guard for ``app/api/__init__.py``."""
    from app import api  # noqa: F401 — import side-effect populates symbols

    assert hasattr(api, "surfaces_bp"), (
        "surfaces_bp not exported from app.api — register it in app/api/__init__.py"
    )


def test_surfaces_blueprint_is_mounted_on_the_app():
    """The blueprint must be mounted at the ``/api`` prefix so
    ``GET /api/surfaces.json`` actually resolves. Static text check on
    the application factory rather than spinning up ``create_app`` —
    the factory initialises Neo4j and other side-effecting singletons
    so a static guard keeps the suite hermetic. Matches the posture of
    ``test_unit_sitemap.py``."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "surfaces_bp" in text, (
        "surfaces_bp not referenced in app/__init__.py — register it in create_app"
    )
    assert "app.register_blueprint(surfaces_bp, url_prefix='/api')" in text, (
        "surfaces_bp must be mounted at '/api' so GET /api/surfaces.json resolves"
    )


def test_surfaces_route_decorator_present():
    """The ``GET /surfaces.json`` route decorator must exist on the
    blueprint module. Drift guard for ``app/api/surfaces.py`` —
    catches the failure mode where the blueprint is registered but
    its route handler was deleted."""
    surfaces_path = _BACKEND / "app" / "api" / "surfaces.py"
    text = surfaces_path.read_text(encoding="utf-8")
    assert "@surfaces_bp.route(\"/surfaces.json\"" in text, (
        "surfaces blueprint missing @surfaces_bp.route('/surfaces.json', ...) decorator"
    )


# ── OpenAPI spec ───────────────────────────────────────────────────────


def test_openapi_spec_includes_surfaces_catalog_endpoint():
    """The catalog endpoint must be discoverable from the live OpenAPI
    document at ``/api/openapi.yaml`` — the same surface ``/api/docs``
    consumes."""
    spec_path = _BACKEND / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml missing at {spec_path}"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/surfaces.json:" in spec_text, (
        "openapi.yaml missing /api/surfaces.json path entry"
    )
    assert "SurfaceCatalogEntry" in spec_text, (
        "openapi.yaml missing SurfaceCatalogEntry schema"
    )


# ── ?type= category filter ─────────────────────────────────────────────


def test_is_valid_surface_type_accepts_every_category():
    """Every literal in ``SURFACE_TYPES`` is a valid filter value — the
    validator and the catalog can't disagree on what a category is."""
    for surface_type in surfaces_catalog.SURFACE_TYPES:
        assert surfaces_catalog.is_valid_surface_type(surface_type), (
            f"{surface_type!r} should validate"
        )


def test_is_valid_surface_type_rejects_unknown_and_non_string():
    """Unknown strings, empty string, wrong case, and non-strings all
    fail validation so the route can 400 them."""
    assert not surfaces_catalog.is_valid_surface_type("bogus")
    assert not surfaces_catalog.is_valid_surface_type("")
    # Case-sensitive — the route lower-cases before calling.
    assert not surfaces_catalog.is_valid_surface_type("ANALYTICS")
    assert not surfaces_catalog.is_valid_surface_type(None)
    assert not surfaces_catalog.is_valid_surface_type(7)


def test_filtered_payload_returns_only_that_type():
    """``build_response_payload(type)`` returns exactly the surfaces of
    that type, with ``count`` reflecting the filtered length and the
    envelope shape unchanged."""
    full = surfaces_catalog.get_surfaces_catalog()
    for surface_type in surfaces_catalog.SURFACE_TYPES:
        payload = surfaces_catalog.build_response_payload(surface_type)
        assert set(payload.keys()) == {"schema_version", "count", "surfaces"}
        expected = [e for e in full if e["type"] == surface_type]
        assert payload["count"] == len(expected)
        assert len(payload["surfaces"]) == payload["count"]
        assert all(e["type"] == surface_type for e in payload["surfaces"])


def test_filtered_counts_partition_the_full_catalog():
    """Every surface lands in exactly one category bucket — the filtered
    counts across all categories sum to the full catalog count, so the
    filter never drops or double-counts a surface."""
    total = sum(
        surfaces_catalog.build_response_payload(surface_type)["count"]
        for surface_type in surfaces_catalog.SURFACE_TYPES
    )
    assert total == surfaces_catalog.catalog_count()


def test_unfiltered_payload_is_backward_compatible():
    """No filter (or an explicit ``None``) returns the full catalog —
    every existing consumer sees the same response it always has."""
    assert surfaces_catalog.build_response_payload() == (
        surfaces_catalog.build_response_payload(None)
    )
    assert (
        surfaces_catalog.build_response_payload()["count"]
        == surfaces_catalog.catalog_count()
    )


def test_filtered_etag_is_distinct_and_well_formed():
    """A filtered request carries the category in its ETag so a filtered
    and an unfiltered response never collide in a shared cache."""
    base = surfaces_catalog.catalog_etag()
    assert surfaces_catalog.catalog_etag(None) == base
    for surface_type in surfaces_catalog.SURFACE_TYPES:
        filtered = surfaces_catalog.catalog_etag(surface_type)
        assert filtered == f"{base}-{surface_type}"
        assert filtered != base
        assert re.fullmatch(r"surfaces-v\d+-\d+-[a-z]+", filtered), (
            f"filtered etag {filtered!r} malformed"
        )


def test_route_reads_and_validates_type_param():
    """Static guard on ``app/api/surfaces.py`` — the route reads the
    ``?type=`` param, validates it through the service, and 400s an
    unknown value. Matches the suite's static-guard posture (no app
    spin-up, which would initialise Neo4j)."""
    text = (_BACKEND / "app" / "api" / "surfaces.py").read_text(encoding="utf-8")
    assert 'request.args.get("type")' in text, (
        "surfaces route does not read the ?type= query param"
    )
    assert "is_valid_surface_type" in text, (
        "surfaces route does not validate ?type= through the service"
    )
    assert "400" in text, "surfaces route does not 400 an invalid ?type="


def test_openapi_spec_documents_type_filter():
    """The ``?type=`` query parameter must be declared in the OpenAPI
    document so ``/api/docs`` advertises it."""
    spec_text = (_BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    assert "name: type" in spec_text, (
        "openapi.yaml does not declare the ?type= query parameter"
    )
    assert (
        "[analytics, visualization, export, embed, integration, platform, discovery]"
        in spec_text
    ), "openapi.yaml ?type= parameter missing the category enum"
