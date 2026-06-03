"""Unit tests for the machine-readable ecosystem catalog service.

Pure offline — no Flask app context, no network, no on-disk state.
Cover the properties the ``GET /api/ecosystem.json`` endpoint depends
on:

  1. ``get_ecosystem_catalog`` returns a non-empty list of dicts and
     every entry has the locked field set + valid types.
  2. ``catalog_count`` equals ``len(get_ecosystem_catalog())``.
  3. ``catalog_etag`` is a deterministic short string keyed on the
     catalog length + schema version.
  4. ``build_response_payload`` returns the documented envelope shape
     (``schema_version`` + ``count`` + ``ecosystem``).
  5. Every entry's ``category`` is one of the five recognised strings.
  6. Every entry's ``name`` is unique across the catalog — no two
     integrators can claim the same project name.
  7. Every entry's ``url`` starts with ``http://`` or ``https://`` and
     ``description`` is non-empty + bounded at 160 chars.
  8. ``x_handle`` is ``None`` or a string without the leading ``@``;
     ``repo`` is ``None`` or a github.com URL.
  9. Entries are alphabetised by ``name`` (matches ECOSYSTEM.md
     ordering convention).
 10. The catalog stays in sync with ``ECOSYSTEM.md`` — drift guard.
 11. ``get_ecosystem_catalog`` returns fresh objects per call —
     mutating the result must not affect subsequent reads.
 12. ``build_response_payload`` is JSON-serialisable.
 13. The blueprint already registered for ``/api/surfaces.json``
     also serves ``/api/ecosystem.json`` — wiring guard.
 14. The OpenAPI spec carries an entry for ``/api/ecosystem.json`` so
     ``/api/docs`` lists the ecosystem endpoint.
 15. The surfaces catalog includes an ``ecosystem_catalog`` entry so
     a consumer iterating ``/api/surfaces.json`` discovers the
     ecosystem endpoint.
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
from app.services import ecosystem_catalog  # noqa: E402
from app.services import surfaces_catalog  # noqa: E402


REQUIRED_FIELDS = {
    "name",
    "url",
    "description",
    "category",
    "x_handle",
    "repo",
}


# ── Schema invariants ──────────────────────────────────────────────────


def test_catalog_is_non_empty_list_of_dicts():
    catalog = ecosystem_catalog.get_ecosystem_catalog()
    assert isinstance(catalog, list)
    assert len(catalog) > 0
    for entry in catalog:
        assert isinstance(entry, dict)


def test_every_entry_has_locked_field_set():
    for entry in ecosystem_catalog.get_ecosystem_catalog():
        missing = REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"entry {entry.get('name')!r} missing: {missing}"


def test_catalog_count_matches_list_length():
    assert ecosystem_catalog.catalog_count() == len(
        ecosystem_catalog.get_ecosystem_catalog()
    )


def test_names_are_unique():
    names = [entry["name"] for entry in ecosystem_catalog.get_ecosystem_catalog()]
    assert len(names) == len(set(names)), f"duplicate names: {names}"


def test_every_entry_category_is_recognised():
    for entry in ecosystem_catalog.get_ecosystem_catalog():
        assert entry["category"] in ecosystem_catalog.ECOSYSTEM_CATEGORIES, (
            f"entry {entry['name']!r} has unknown category {entry['category']!r}"
        )


def test_every_entry_url_is_http_or_https():
    for entry in ecosystem_catalog.get_ecosystem_catalog():
        url = entry["url"]
        assert isinstance(url, str)
        assert url.startswith("http://") or url.startswith("https://"), (
            f"entry {entry['name']!r} url {url!r} must be http(s)"
        )


def test_description_is_bounded_and_non_empty():
    for entry in ecosystem_catalog.get_ecosystem_catalog():
        desc = entry["description"]
        assert isinstance(desc, str)
        assert 0 < len(desc) <= 160, (
            f"entry {entry['name']!r} description length {len(desc)} out of bounds"
        )


def test_x_handle_is_nullable_string_without_at_prefix():
    for entry in ecosystem_catalog.get_ecosystem_catalog():
        handle = entry["x_handle"]
        if handle is None:
            continue
        assert isinstance(handle, str)
        assert handle, f"entry {entry['name']!r} has empty x_handle"
        assert not handle.startswith("@"), (
            f"entry {entry['name']!r} x_handle must not include the leading '@'"
        )


def test_repo_is_nullable_github_url():
    for entry in ecosystem_catalog.get_ecosystem_catalog():
        repo = entry["repo"]
        if repo is None:
            continue
        assert isinstance(repo, str)
        assert repo.startswith("https://github.com/"), (
            f"entry {entry['name']!r} repo {repo!r} must be a https://github.com/ URL"
        )


def test_entries_are_alphabetised_by_name():
    """Order matches the ECOSYSTEM.md alphabetised table. Reordering is
    a breaking change — guard so a future edit can't silently shuffle."""
    names = [entry["name"] for entry in ecosystem_catalog.get_ecosystem_catalog()]
    assert names == sorted(names, key=str.casefold), (
        f"catalog not alphabetised by name (case-insensitive): {names}"
    )


# ── Cross-source drift ─────────────────────────────────────────────────


def _ecosystem_md_names() -> set[str]:
    """Extract project names from the ECOSYSTEM.md project table.

    The Markdown table format is::

        | Logo | Project | Links |
        |------|---------|-------|
        | <img ...> | ProjectName | ... |

    The third column is the project name (second pipe-separated cell
    after the leading blank). Returns the set of project names —
    skips header and separator rows.
    """
    md_path = _BACKEND.parent / "ECOSYSTEM.md"
    text = md_path.read_text(encoding="utf-8")

    names: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        # Skip header + separator rows.
        if cells[1].lower() == "project":
            continue
        if set(cells[1]) <= {"-", ":", " "}:
            continue
        name = cells[1]
        if not name:
            continue
        names.add(name)
    return names


def test_catalog_names_match_ecosystem_md():
    """The catalog must list exactly the same project names as the
    ECOSYSTEM.md table. A new integrator ships in two places (the
    Markdown row + the catalog entry); this test enforces the second."""
    catalog_names = {
        entry["name"] for entry in ecosystem_catalog.get_ecosystem_catalog()
    }
    md_names = _ecosystem_md_names()
    assert catalog_names == md_names, (
        f"catalog drifted from ECOSYSTEM.md — "
        f"catalog only: {sorted(catalog_names - md_names)}, "
        f"markdown only: {sorted(md_names - catalog_names)}"
    )


def test_surfaces_catalog_includes_ecosystem_entry():
    """The surface catalog (``/api/surfaces.json``) must include the
    ecosystem endpoint so a consumer iterating the surface catalog
    discovers the ecosystem registry."""
    surface_keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "ecosystem_catalog" in surface_keys, (
        "surfaces_catalog missing ecosystem_catalog entry — a consumer "
        "iterating /api/surfaces.json must be able to discover /api/ecosystem.json"
    )


# ── ETag + envelope ────────────────────────────────────────────────────


def test_catalog_etag_is_deterministic_short_string():
    etag = ecosystem_catalog.catalog_etag()
    assert isinstance(etag, str)
    assert len(etag) <= 32
    # Two calls inside the same process return the same string.
    assert ecosystem_catalog.catalog_etag() == etag
    # ETag must change when the catalog length changes — encoded as
    # part of the literal so a regex covers it.
    assert re.fullmatch(r"ecosystem-v\d+-\d+", etag), (
        f"etag {etag!r} does not match expected pattern"
    )


def test_build_response_payload_envelope_shape():
    payload = ecosystem_catalog.build_response_payload()
    assert set(payload.keys()) == {"schema_version", "count", "ecosystem"}
    assert payload["schema_version"] == ecosystem_catalog.SCHEMA_VERSION
    assert payload["count"] == ecosystem_catalog.catalog_count()
    assert isinstance(payload["ecosystem"], list)
    assert len(payload["ecosystem"]) == payload["count"]


def test_build_response_payload_is_json_serialisable():
    """The envelope is what the route handler hands to ``jsonify`` — a
    smoke test guards against a future entry whose value type doesn't
    survive ``json.dumps``."""
    payload = ecosystem_catalog.build_response_payload()
    serialised = json.dumps(payload, sort_keys=True)
    assert serialised  # Non-empty after serialisation.
    # Round-trips back to the same shape.
    roundtripped = json.loads(serialised)
    assert roundtripped["count"] == payload["count"]


# ── Immutability ───────────────────────────────────────────────────────


def test_get_ecosystem_catalog_returns_fresh_objects():
    """Mutating the returned list or its inner dicts must not affect
    subsequent calls. The catalog is module-level state; if the
    function handed out the live reference, a misbehaving caller could
    silently corrupt every future read."""
    catalog_a = ecosystem_catalog.get_ecosystem_catalog()
    catalog_a.clear()
    catalog_b = ecosystem_catalog.get_ecosystem_catalog()
    assert len(catalog_b) > 0, "outer list aliasing — clearing affected next call"

    catalog_c = ecosystem_catalog.get_ecosystem_catalog()
    catalog_c[0]["name"] = "MUTATED"
    catalog_d = ecosystem_catalog.get_ecosystem_catalog()
    assert catalog_d[0]["name"] != "MUTATED", (
        "inner dict aliasing — mutation affected next call"
    )


# ── Wiring guards ──────────────────────────────────────────────────────


def test_ecosystem_route_decorator_present():
    """The ``GET /ecosystem.json`` route decorator must exist on the
    surfaces blueprint module. The catalog is mounted on the existing
    ``surfaces_bp`` so the wiring guard is a static check that the
    decorator is present in ``app/api/surfaces.py``."""
    surfaces_path = _BACKEND / "app" / "api" / "surfaces.py"
    text = surfaces_path.read_text(encoding="utf-8")
    assert "@surfaces_bp.route(\"/ecosystem.json\"" in text, (
        "surfaces blueprint missing @surfaces_bp.route('/ecosystem.json', ...) decorator"
    )


# ── OpenAPI spec ───────────────────────────────────────────────────────


def test_openapi_spec_includes_ecosystem_catalog_endpoint():
    """The ecosystem endpoint must be discoverable from the live
    OpenAPI document at ``/api/openapi.yaml`` — the same surface
    ``/api/docs`` consumes."""
    spec_path = _BACKEND / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml missing at {spec_path}"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/ecosystem.json:" in spec_text, (
        "openapi.yaml missing /api/ecosystem.json path entry"
    )
    assert "EcosystemEntry" in spec_text, (
        "openapi.yaml missing EcosystemEntry schema"
    )
    assert "EcosystemRegistry" in spec_text, (
        "openapi.yaml missing EcosystemRegistry schema"
    )
