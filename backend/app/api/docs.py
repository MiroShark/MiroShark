"""Interactive API documentation — Swagger UI over `backend/openapi.yaml`.

The handwritten spec at ``backend/openapi.yaml`` is the source of truth.
This module just serves it in three ways:

  * ``GET /api/docs``         — Swagger UI HTML page (loads the bundle from
                                jsDelivr; no Python deps beyond stdlib +
                                pyyaml for the JSON variant).
  * ``GET /api/openapi.yaml`` — raw YAML, the canonical artifact.
  * ``GET /api/openapi.json`` — same content converted to JSON, handy for
                                ``openapi-generator`` and APIs.guru style
                                consumers that reach for ``.json`` first.

The docs surface is an informational endpoint — it never raises and it
never depends on Neo4j, the LLM, or any simulation state. The whole
purpose is to give MCP-onboarded developers (PR #44) a friendly answer
to "what REST endpoints can I hit?" without leaving the app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from flask import Response, jsonify

from . import docs_bp
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.docs")


# ──────────────────────────────────────────────────────────────────────────
# Spec loading — read the YAML once at import time, cache the parsed form
# for the JSON endpoint so we don't re-parse per request. The raw YAML
# bytes are also cached so we can serve them with a stable Content-Length.
# ──────────────────────────────────────────────────────────────────────────


_SPEC_PATH: Path = Path(__file__).resolve().parent.parent.parent / "openapi.yaml"


def _read_spec_bytes() -> bytes:
    """Return the YAML spec as bytes.

    Reads from disk every call (cheap — a few hundred KB at most) so an
    operator editing the spec in-place picks up changes without a server
    restart. Returns an empty placeholder if the file is missing rather
    than 500'ing the doc page.
    """
    try:
        return _SPEC_PATH.read_bytes()
    except FileNotFoundError:
        logger.warning("openapi.yaml not found at %s — docs endpoint will return a stub", _SPEC_PATH)
        return (
            b"openapi: 3.1.0\n"
            b"info:\n"
            b"  title: MiroShark HTTP API\n"
            b"  version: \"unknown\"\n"
            b"  description: openapi.yaml not found in this build.\n"
            b"paths: {}\n"
        )


def _spec_as_dict() -> dict:
    """Parse the YAML spec into a dict for the JSON endpoint.

    Imports pyyaml lazily because it's listed in ``backend/uv.lock`` and
    in the unit-test workflow but isn't a hard install requirement of
    the running backend yet — we don't want a missing dependency to break
    the rest of the docs surface.
    """
    raw = _read_spec_bytes()
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("PyYAML not installed — /api/openapi.json returns a placeholder")
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "MiroShark HTTP API",
                "version": "unknown",
                "description": "PyYAML is required to render the JSON form of this spec. "
                               "Install with `pip install pyyaml` or fetch /api/openapi.yaml instead.",
            },
            "paths": {},
        }

    try:
        parsed = yaml.safe_load(raw) or {}
        if not isinstance(parsed, dict):
            logger.warning("openapi.yaml did not parse as a mapping — got %s", type(parsed).__name__)
            return {}
        return parsed
    except yaml.YAMLError as exc:
        logger.error("Failed to parse openapi.yaml: %s", exc)
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "MiroShark HTTP API",
                "version": "unknown",
                "description": f"openapi.yaml failed to parse: {exc}. Fix the spec or fetch the YAML form.",
            },
            "paths": {},
        }


# ──────────────────────────────────────────────────────────────────────────
# Swagger UI HTML — pinned bundle from jsDelivr (immutable + CDN cached).
# Pinning the version keeps the rendered page stable across releases of
# Swagger UI; bump deliberately when there's a reason to.
# ──────────────────────────────────────────────────────────────────────────


_SWAGGER_UI_VERSION = "5.17.14"


def _swagger_ui_html(spec_url: str) -> str:
    """Render the Swagger UI HTML page that points at ``spec_url``.

    The page is fully static — Swagger UI fetches the spec on the client.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MiroShark · API Reference</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui.css">
  <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=">
  <style>
    html, body {{ margin: 0; padding: 0; background: #0a0a0a; }}
    /* Slim down the Swagger UI top bar so the page reads as part of MiroShark
       rather than a generic Swagger demo. */
    .swagger-ui .topbar {{ display: none; }}
    .miroshark-banner {{
      background: linear-gradient(180deg, #0a0a0a, #181818);
      color: #fafafa;
      padding: 18px 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      border-bottom: 1px solid #262626;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .miroshark-banner h1 {{
      font-size: 14px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin: 0;
      opacity: 0.7;
      font-weight: 700;
    }}
    .miroshark-banner a {{
      color: #ea580c;
      text-decoration: none;
      font-size: 13px;
      margin-left: 16px;
    }}
    .miroshark-banner a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <header class="miroshark-banner">
    <h1>MiroShark · API Reference</h1>
    <nav>
      <a href="/api/openapi.yaml">openapi.yaml</a>
      <a href="/api/openapi.json">openapi.json</a>
      <a href="https://github.com/aaronjmars/MiroShark/blob/main/docs/API.md" target="_blank" rel="noopener">docs/API.md</a>
      <a href="https://github.com/aaronjmars/MiroShark" target="_blank" rel="noopener">GitHub</a>
    </nav>
  </header>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{_SWAGGER_UI_VERSION}/swagger-ui-standalone-preset.js"></script>
  <script>
    window.addEventListener("load", function () {{
      window.ui = SwaggerUIBundle({{
        url: {json.dumps(spec_url)},
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        tryItOutEnabled: true,
        persistAuthorization: true,
        docExpansion: "list",
        defaultModelsExpandDepth: 0,
        syntaxHighlight: {{ activate: true, theme: "agate" }},
      }});
    }});
  </script>
</body>
</html>
"""


# ──────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────


@docs_bp.route("/docs", methods=["GET"])
def render_swagger_ui():
    """Render Swagger UI for the MiroShark HTTP API."""
    body = _swagger_ui_html(spec_url="/api/openapi.yaml")
    response = Response(body, mimetype="text/html; charset=utf-8")
    # Short cache so tweaks to the doc page (rare) propagate quickly while
    # absorbing repeat hits from refreshes.
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@docs_bp.route("/openapi.yaml", methods=["GET"])
def serve_openapi_yaml():
    """Serve the canonical OpenAPI 3.1 YAML spec.

    Content-Type follows the IETF draft media type for OpenAPI YAML
    (``application/yaml``) — both ``openapi-generator`` and Swagger UI
    accept it, and APIs.guru-style submissions key off the URL extension
    rather than the header.
    """
    body = _read_spec_bytes()
    response = Response(body, mimetype="application/yaml; charset=utf-8")
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["Content-Disposition"] = 'inline; filename="openapi.yaml"'
    return response


@docs_bp.route("/openapi.json", methods=["GET"])
def serve_openapi_json():
    """Serve the OpenAPI spec converted to JSON.

    Useful for tools that prefer JSON over YAML
    (e.g. ``openapi-generator`` with ``--input-spec=...openapi.json``).
    """
    spec = _spec_as_dict()
    response = jsonify(spec)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


# ──────────────────────────────────────────────────────────────────────────
# Test helper — exposed so the unit suite can introspect coverage without
# spinning up Flask. Not part of the HTTP surface.
# ──────────────────────────────────────────────────────────────────────────


def documented_paths() -> list[str]:
    """Return every path key declared in ``openapi.yaml``.

    Used by ``test_unit_openapi`` to verify documented paths line up with
    Flask routes registered on the live app.
    """
    spec = _spec_as_dict()
    paths = spec.get("paths", {}) or {}
    return list(paths.keys())


def get_spec_path() -> Optional[Path]:
    """Return the on-disk path to ``openapi.yaml`` if it exists."""
    return _SPEC_PATH if _SPEC_PATH.exists() else None
