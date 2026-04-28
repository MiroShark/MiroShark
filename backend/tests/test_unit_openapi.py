"""Unit tests for the interactive API documentation surface.

Same shape as ``test_unit_mcp_api.py``: pure offline checks against the
helpers in ``app/api/docs.py`` plus regex-based drift detection between
the handwritten OpenAPI spec and the actual Flask routes registered in
``app/api/*.py``.

A drifted spec is the worst failure mode here — it advertises endpoints
that no longer exist, or fails to mention ones that do — so the drift
test is the centerpiece of this suite.

We cover:

  1. ``backend/openapi.yaml`` exists, parses, and declares the minimum
     OpenAPI 3.x shape (``openapi``, ``info``, ``paths``).
  2. Every documented path corresponds to a real Flask route. The route
     scan reads ``app/api/*.py`` as text — no live Flask app, no Neo4j —
     so the test runs in the bare unit environment.
  3. Every Flask route either appears in the spec or is on the
     deliberately undocumented allow-list (e.g. internal / debug routes).
  4. The Swagger UI HTML renders, references the spec URL, and pulls
     ``swagger-ui-dist`` from a pinned CDN.
  5. The JSON variant of the spec parses and has the same top-level
     shape as the YAML.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ──────────────────────────────────────────────────────────────────────────
# Spec presence + parse
# ──────────────────────────────────────────────────────────────────────────


def _load_spec() -> dict:
    """Load openapi.yaml as a dict — pyyaml is in the unit-test workflow."""
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml missing at {spec_path}"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    assert isinstance(spec, dict), f"openapi.yaml did not parse as a mapping (got {type(spec).__name__})"
    return spec


def test_openapi_yaml_exists_and_parses():
    spec = _load_spec()
    # The bare minimum OpenAPI 3.x shape.
    assert "openapi" in spec, "spec missing top-level `openapi` version field"
    assert spec["openapi"].startswith("3."), f"unexpected openapi version: {spec['openapi']}"
    assert "info" in spec and isinstance(spec["info"], dict), "spec missing `info` block"
    assert spec["info"].get("title"), "spec `info.title` is empty"
    assert spec["info"].get("version"), "spec `info.version` is empty"
    assert "paths" in spec and isinstance(spec["paths"], dict), "spec missing `paths` block"
    assert spec["paths"], "spec declares no paths"


def test_openapi_yaml_has_every_required_tag():
    """Tags declared in operations must also be declared at the top level
    so Swagger UI groups operations under named, ordered sections."""
    spec = _load_spec()
    declared = {t["name"] for t in (spec.get("tags") or []) if isinstance(t, dict)}
    used: set[str] = set()
    for path_item in spec["paths"].values():
        for op in path_item.values():
            if isinstance(op, dict):
                for tag in op.get("tags") or []:
                    used.add(tag)
    missing = used - declared
    assert not missing, f"operations reference undeclared tags: {sorted(missing)}"


# ──────────────────────────────────────────────────────────────────────────
# Drift detection — documented paths vs. actual Flask routes
# ──────────────────────────────────────────────────────────────────────────


# Map blueprint name → URL prefix as registered in app/__init__.py.
_BLUEPRINT_PREFIXES = {
    "graph_bp":          "/api/graph",
    "simulation_bp":     "/api/simulation",
    "report_bp":         "/api/report",
    "templates_bp":      "/api/templates",
    "settings_bp":       "/api/settings",
    "observability_bp":  "/api/observability",
    "mcp_bp":            "/api/mcp",
    "docs_bp":           "/api",
    # share_bp is mounted at the root with no prefix — see app/__init__.py.
    "share_bp":          "",
}


# Routes that exist in the running app but are deliberately not part of
# the public OpenAPI surface (debug-only, hand-run scripts, internal
# helpers exposed at /api but not meant for third-party consumers).
# Adding to this list is fine; removing endpoints from the spec without
# adding them here will fail the drift test.
_UNDOCUMENTED_ALLOWLIST: set[str] = {
    # Internal config-management routes — used by the SPA's own setup
    # flow, not stable enough for third-party consumption.
    "/api/simulation/<simulation_id>/config",
    "/api/simulation/<simulation_id>/config/realtime",
    "/api/simulation/<simulation_id>/config/retry",
    "/api/simulation/<simulation_id>/config/download",
    "/api/simulation/script/<script_name>/download",
    "/api/simulation/project/<project_id>/files/<saved_filename>/download",
    "/api/simulation/generate-profiles",
    # Environment management — operator-facing only, not shipped to
    # third-party consumers.
    "/api/simulation/env-status",
    "/api/simulation/restart-env",
    "/api/simulation/close-env",
    # Internal report-status / debugging helpers — explicitly marked
    # "for debugging" in their docstrings.
    "/api/report/check/<simulation_id>",
    "/api/report/tools/search",
    "/api/report/tools/statistics",
}


_ROUTE_RE = re.compile(
    # ``path`` allows the empty string so we capture
    # ``@settings_bp.route('')`` — that's a real registration that
    # mounts at the blueprint's prefix (``/api/settings``).
    r"@(?P<bp>[a-z_]+_bp)\.route\(\s*(?P<quote>['\"])(?P<path>[^'\"]*)(?P=quote)",
)


def _extract_routes_for_bp(bp_name: str, file_path: Path) -> list[str]:
    """Find every ``@<bp_name>.route('...')`` declaration in ``file_path``.

    Returns the path component (e.g. ``"/<id>/run-status"``) — the caller
    is responsible for prefixing with the blueprint's URL prefix.
    """
    text = file_path.read_text(encoding="utf-8")
    paths: list[str] = []
    for match in _ROUTE_RE.finditer(text):
        if match.group("bp") != bp_name:
            continue
        paths.append(match.group("path"))
    return paths


def _collect_flask_routes() -> set[str]:
    """Static scan of every ``app/api/*.py`` and ``share.py`` for route
    decorators. Returns fully-qualified path templates (with ``<>``).
    """
    api_dir = _BACKEND / "app" / "api"
    routes: set[str] = set()

    for py_file in sorted(api_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        for match in _ROUTE_RE.finditer(text):
            bp_name = match.group("bp")
            raw_path = match.group("path")
            prefix = _BLUEPRINT_PREFIXES.get(bp_name)
            if prefix is None:
                # Unknown blueprint — skip rather than fail; new bps need
                # a deliberate addition to _BLUEPRINT_PREFIXES.
                continue
            full = f"{prefix}{raw_path}" if raw_path else prefix
            # Flask treats an empty path as the prefix itself
            # (e.g. @settings_bp.route('') ⇒ /api/settings).
            if raw_path == "":
                full = prefix
            routes.add(full)

    # The bare /health route lives in app/__init__.py — include it for
    # completeness so the drift test sees a single source-of-truth set.
    init_text = (_BACKEND / "app" / "__init__.py").read_text(encoding="utf-8")
    if "@app.route('/health')" in init_text:
        routes.add("/health")

    return routes


def _flask_to_openapi_path(path: str) -> str:
    """Convert ``"/api/simulation/<simulation_id>"`` → ``"/api/simulation/{simulation_id}"``.

    Handles Flask converters like ``<int:round_num>`` and
    ``<path:something>`` by stripping the converter prefix.
    """

    def _replace(match: re.Match[str]) -> str:
        inner = match.group(1)
        if ":" in inner:
            inner = inner.split(":", 1)[1]
        return "{" + inner + "}"

    return re.sub(r"<([^<>]+)>", _replace, path)


def _normalize_for_comparison(path: str) -> str:
    """Trim trailing slashes for comparison (Flask treats them equivalently)."""
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def test_documented_paths_exist_in_flask():
    """Every documented OpenAPI path must map to a real Flask route."""
    spec = _load_spec()
    flask_routes = {_normalize_for_comparison(_flask_to_openapi_path(r)) for r in _collect_flask_routes()}
    documented = {_normalize_for_comparison(p) for p in spec["paths"].keys()}

    phantom = documented - flask_routes
    assert not phantom, (
        f"OpenAPI spec advertises paths that do not exist as Flask routes:\n  "
        + "\n  ".join(sorted(phantom))
    )


def test_flask_routes_are_documented_or_allowlisted():
    """Every Flask route must either appear in the spec or be in the
    explicit undocumented allowlist."""
    spec = _load_spec()
    flask_paths_oai = {
        _normalize_for_comparison(_flask_to_openapi_path(r))
        for r in _collect_flask_routes()
    }
    documented = {_normalize_for_comparison(p) for p in spec["paths"].keys()}
    allowlisted = {
        _normalize_for_comparison(_flask_to_openapi_path(r))
        for r in _UNDOCUMENTED_ALLOWLIST
    }

    undocumented = flask_paths_oai - documented - allowlisted
    assert not undocumented, (
        f"Flask routes missing from openapi.yaml (add to spec OR allowlist):\n  "
        + "\n  ".join(sorted(undocumented))
    )


# ──────────────────────────────────────────────────────────────────────────
# Swagger UI rendering
# ──────────────────────────────────────────────────────────────────────────


def test_swagger_ui_html_references_spec_and_pinned_cdn():
    """The HTML page must point Swagger UI at the served spec URL and pull
    its assets from a pinned (versioned) CDN — pinning protects against
    upstream releases breaking the page."""
    from app.api.docs import _swagger_ui_html, _SWAGGER_UI_VERSION

    html = _swagger_ui_html("/api/openapi.yaml")

    # Spec wired in.
    assert '"/api/openapi.yaml"' in html, "spec URL not embedded in Swagger UI bootstrap"
    assert "SwaggerUIBundle" in html, "SwaggerUIBundle constructor missing"

    # Pinned CDN — version literal must appear in both the CSS and the JS
    # bundle URLs so an accidental unpinning is visible.
    assert _SWAGGER_UI_VERSION, "Swagger UI version pin must be set"
    css_url = f"swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui.css"
    js_url = f"swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui-bundle.js"
    assert css_url in html, f"Swagger UI CSS URL {css_url!r} missing from rendered page"
    assert js_url in html, f"Swagger UI JS URL {js_url!r} missing from rendered page"

    # MiroShark-branded banner — confirms we don't accidentally ship the
    # default Swagger UI top bar.
    assert "MiroShark · API Reference" in html


# ──────────────────────────────────────────────────────────────────────────
# Spec-serving helpers
# ──────────────────────────────────────────────────────────────────────────


def test_spec_as_dict_round_trips_top_level_shape():
    """The JSON variant served at /api/openapi.json should preserve the
    YAML's top-level shape — same openapi version, info block, paths."""
    from app.api.docs import _spec_as_dict

    spec_yaml = _load_spec()
    spec_json = _spec_as_dict()

    assert spec_json.get("openapi") == spec_yaml.get("openapi")
    assert spec_json.get("info", {}).get("title") == spec_yaml.get("info", {}).get("title")
    assert set(spec_json.get("paths", {}).keys()) == set(spec_yaml.get("paths", {}).keys()), (
        "JSON variant must serialize the same path set as the YAML source"
    )


def test_documented_paths_helper_lists_all_paths():
    """The ``documented_paths()`` helper used by the test infra must
    return the same list as the parsed spec — keeps the helper honest."""
    from app.api.docs import documented_paths

    spec = _load_spec()
    assert sorted(documented_paths()) == sorted(spec["paths"].keys())


def test_route_extractor_matches_known_endpoints():
    """Sanity check on the regex-based route scanner — it must find a
    handful of known-good routes from existing endpoints we did NOT
    introduce in this PR."""
    routes = _collect_flask_routes()
    known = [
        "/api/simulation/<simulation_id>/run-status",
        "/api/simulation/<simulation_id>/share-card.png",
        "/api/simulation/public",
        "/api/mcp/status",
        "/api/settings",
    ]
    for r in known:
        assert r in routes, f"route extractor missed known endpoint {r}"
