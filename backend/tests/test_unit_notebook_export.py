"""Unit tests for the Jupyter notebook export service.

Pure offline — no Flask, no Wonderwall, no LLM, no Jupyter kernel. The
``GET /api/simulation/<id>/notebook.ipynb`` route hands the analysis-
ready surface to institutional observers (the Lorimer-tier audience),
so the service powering it is held to the same correctness bar as
``surface_stats`` / ``repro_export`` / ``trajectory_export``: every
shape promise + every degradation path covered.

Coverage:

  1. ``SCHEMA_VERSION`` constant pinned to ``"1"`` — bumps are
     deliberate wire-contract breaks.
  2. ``CELL_ORDER`` is a tuple of 7 entries in the documented sequence
     (markdown header → 5 code cells → markdown footer). Downstream
     tools that index into cells must not break across minor refactors.
  3. ``build_notebook`` emits a valid nbformat 4 document — top-level
     ``nbformat`` is 4, ``nbformat_minor`` is set, ``cells`` is a non-
     empty list, ``metadata`` carries kernelspec + miroshark block.
  4. Cell types match ``CELL_ORDER`` exactly.
  5. The header markdown cell carries the sim id, scenario, agent count,
     round count, and platforms summary.
  6. The CSV load cell embeds the trajectory CSV verbatim — anyone
     running the notebook gets the same bytes the ``trajectory.csv``
     endpoint serves.
  7. The chart cells reference matplotlib (`plt.show()`) and the colour
     codes used across every other surface (`#22c55e` / `#6b7280` /
     `#ef4444`).
  8. ``render_notebook_bytes`` produces deterministic output — running
     twice on the same notebook dict yields identical bytes (citation-
     hash friendly, same property as ``repro_export.render_json_bytes``).
  9. The rendered bytes round-trip through ``json.loads`` into an
     equivalent dict — defensive guard against accidental f-string
     interpolation that would break ``.ipynb`` parsing.
 10. The header includes a reproduce.json link when ``base_url`` is
     supplied.
 11. Missing reproduction blob degrades gracefully — header renders
     with empty / zero metadata rather than crashing.
 12. Counterfactual lineage surfaces in the header markdown
     (parent + round + label).
 13. Empty CSV (no trajectory rows) still produces a valid notebook —
     the load cell embeds an empty/header-only string without
     crashing the build.
 14. ``trajectory_sha256`` in the metadata matches the SHA-256 of the
     embedded CSV bytes — operators can verify the embedded data wasn't
     tampered with after the file was downloaded.
 15. Embedded CSV containing triple-quote sequences is safely escaped
     so the Python literal can't terminate early.
 16. Surface key ``notebook_ipynb`` is in ``surface_stats.SURFACE_KEYS``
     — the analytics layer counts notebook serves alongside every other
     share surface.
 17. ``GET /<simulation_id>/notebook.ipynb`` route decorator is
     registered in ``app/api/simulation.py`` so the OpenAPI drift test
     passes.
 18. The route handler imports the service module — catches the failure
     mode where the route was added but the body never got wired up.
 19. ``openapi.yaml`` declares the ``/notebook.ipynb`` path so Swagger
     UI documents the new endpoint.
 20. ``openapi.yaml`` declares the ``notebook_ipynb`` field on the
     ``SimulationSurfaceStats`` schema so the analytics envelope
     documents the new counter.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import notebook_export, surface_stats  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def trajectory_csv():
    """Mirror the shape ``trajectory_export.render_csv`` produces."""
    return (
        "round,round_timestamp,bullish_pct,neutral_pct,bearish_pct,"
        "participating_agents,total_posts,total_engagements,"
        "quality_health,participation_rate\n"
        "1,2026-05-08T12:00:00,40.0,40.0,20.0,12,18,42,excellent,0.85\n"
        "2,2026-05-08T13:00:00,50.0,30.0,20.0,14,22,55,excellent,0.85\n"
        "3,2026-05-08T14:00:00,65.0,20.0,15.0,18,28,71,excellent,0.85\n"
    )


@pytest.fixture
def repro_blob():
    return {
        "schema_version": "1",
        "simulation_id": "sim_abcdef123456",
        "scenario": "What if Aave's reserve factor doubled overnight?",
        "agent_count": 36,
        "total_rounds": 24,
        "platforms": {
            "twitter": True,
            "reddit": True,
            "polymarket": False,
            "polymarket_market_count": 1,
        },
        "time_config": {"minutes_per_round": 60, "total_simulation_hours": 24},
        "lineage": {
            "parent_simulation_id": None,
            "kind": "original",
            "counterfactual": None,
        },
        "director_events": None,
        "config_reasoning": "LLM balanced cost vs coverage.",
    }


# ── Module-level invariants ────────────────────────────────────────────


def test_schema_version_literal_one():
    """v1 is a stable wire contract — bumps must be deliberate."""
    assert notebook_export.SCHEMA_VERSION == "1"


def test_cell_order_pinned():
    """Pin the cell sequence so downstream tools indexing into cells
    don't break across minor refactors."""
    assert notebook_export.CELL_ORDER == (
        "markdown",
        "code",
        "code",
        "code",
        "code",
        "code",
        "markdown",
    )


# ── build_notebook ─────────────────────────────────────────────────────


def test_build_notebook_nbformat_4_shape(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
        base_url="https://miroshark.example",
    )
    assert nb["nbformat"] == 4
    assert nb["nbformat_minor"] >= 0
    assert isinstance(nb["cells"], list) and len(nb["cells"]) == len(
        notebook_export.CELL_ORDER
    )

    meta = nb["metadata"]
    assert meta["kernelspec"]["language"] == "python"
    assert meta["kernelspec"]["name"] == "python3"
    assert meta["miroshark"]["schema_version"] == "1"
    assert meta["miroshark"]["simulation_id"] == "sim_abcdef123456"
    # SHA-256 is 64 hex chars.
    assert len(meta["miroshark"]["trajectory_sha256"]) == 64


def test_cell_types_match_pinned_order(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
    )
    types = tuple(c["cell_type"] for c in nb["cells"])
    assert types == notebook_export.CELL_ORDER


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return source


def test_header_cell_carries_run_metadata(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
        base_url="https://miroshark.example",
    )
    header = _cell_text(nb["cells"][0])
    assert "sim_abcdef123456" in header
    assert repro_blob["scenario"] in header
    assert "| Agents | 36 |" in header
    assert "| Rounds | 24 |" in header
    assert "Twitter" in header and "Reddit" in header
    # reproduce.json link present when base_url is supplied.
    assert "reproduce.json" in header


def test_load_cell_embeds_csv_via_python_literal(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
    )
    load_cell = _cell_text(nb["cells"][2])
    # The notebook embeds the CSV as a Python string literal — anyone
    # running the cell gets the same bytes the trajectory.csv endpoint
    # serves. We verify by eval'ing the literal back to the original.
    marker = "TRAJECTORY_CSV = "
    start = load_cell.index(marker) + len(marker)
    end = load_cell.index("\n", start)
    literal = load_cell[start:end]
    # ``ast.literal_eval`` accepts any valid Python string literal
    # without executing arbitrary code.
    import ast
    decoded = ast.literal_eval(literal)
    assert decoded == trajectory_csv
    assert "pd.read_csv(io.StringIO(TRAJECTORY_CSV))" in load_cell


def test_chart_cells_reference_matplotlib_and_palette(
    trajectory_csv, repro_blob
):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
    )
    belief = _cell_text(nb["cells"][3])
    consensus = _cell_text(nb["cells"][4])
    # plt.show() in both chart cells — the standard inline-render call.
    assert "plt.show()" in belief
    assert "plt.show()" in consensus
    # The bullish/neutral/bearish palette is consistent across surfaces.
    for hex_code in ("#22c55e", "#6b7280", "#ef4444"):
        assert hex_code in belief
        assert hex_code in consensus


def test_render_bytes_is_deterministic(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
    )
    a = notebook_export.render_notebook_bytes(nb)
    b = notebook_export.render_notebook_bytes(nb)
    assert isinstance(a, bytes)
    assert a == b
    # Trailing newline matches the repro_export convention.
    assert a.endswith(b"\n")


def test_render_bytes_round_trips_through_json(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
    )
    payload = notebook_export.render_notebook_bytes(nb)
    parsed = json.loads(payload.decode("utf-8"))
    assert parsed["nbformat"] == 4
    assert parsed["metadata"]["miroshark"]["simulation_id"] == "sim_abcdef123456"
    assert len(parsed["cells"]) == len(notebook_export.CELL_ORDER)


def test_base_url_omitted_drops_link(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
        base_url=None,
    )
    header = _cell_text(nb["cells"][0])
    assert "reproduce.json" not in header
    assert "/share/" not in header


def test_missing_repro_blob_degrades_gracefully(trajectory_csv):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=None,
        base_url=None,
    )
    header = _cell_text(nb["cells"][0])
    assert "sim_abcdef123456" in header
    assert "| Agents | 0 |" in header
    assert "| Rounds | 0 |" in header


def test_counterfactual_lineage_surfaces_in_header(trajectory_csv):
    blob = {
        "simulation_id": "sim_child000000",
        "scenario": "Branch scenario",
        "agent_count": 36,
        "total_rounds": 24,
        "platforms": {"twitter": True, "reddit": False, "polymarket": False},
        "lineage": {
            "parent_simulation_id": "sim_parent12345",
            "kind": "counterfactual",
            "counterfactual": {
                "trigger_round": 12,
                "label": "ceo_resigns",
                "preview": "...",
            },
        },
    }
    nb = notebook_export.build_notebook(
        sim_id="sim_child000000",
        csv_text=trajectory_csv,
        repro_blob=blob,
    )
    header = _cell_text(nb["cells"][0])
    assert "Counterfactual" in header
    assert "sim_parent12" in header
    assert "round 12" in header
    assert "ceo_resigns" in header


def test_empty_csv_still_produces_valid_notebook(repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text="",
        repro_blob=repro_blob,
    )
    payload = notebook_export.render_notebook_bytes(nb)
    parsed = json.loads(payload.decode("utf-8"))
    assert parsed["nbformat"] == 4
    assert len(parsed["cells"]) == len(notebook_export.CELL_ORDER)
    # SHA-256 of the empty string is well-defined.
    expected = hashlib.sha256(b"").hexdigest()
    assert parsed["metadata"]["miroshark"]["trajectory_sha256"] == expected


def test_trajectory_sha256_matches_embedded_csv(trajectory_csv, repro_blob):
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=trajectory_csv,
        repro_blob=repro_blob,
    )
    expected = hashlib.sha256(trajectory_csv.encode("utf-8")).hexdigest()
    assert nb["metadata"]["miroshark"]["trajectory_sha256"] == expected
    # Footer markdown also exposes the hash for the reader.
    footer = _cell_text(nb["cells"][-1])
    assert expected in footer


def test_pathological_quotes_and_backslashes_survive_roundtrip(repro_blob):
    """Pathological CSV bytes (multiple consecutive quotes, backslashes,
    embedded newlines via CSV-quoted fields) must round-trip through the
    Python literal without breaking the source. ``repr()`` handles every
    byte; this test pins that property."""
    csv_pathological = (
        'round,quality_health\n'
        '1,"contains """ four"" quotes \\\\backslash"\n'
    )
    nb = notebook_export.build_notebook(
        sim_id="sim_abcdef123456",
        csv_text=csv_pathological,
        repro_blob=repro_blob,
    )
    payload = notebook_export.render_notebook_bytes(nb)
    parsed = json.loads(payload.decode("utf-8"))
    load_cell_text = "".join(parsed["cells"][2]["source"])

    marker = "TRAJECTORY_CSV = "
    start = load_cell_text.index(marker) + len(marker)
    end = load_cell_text.index("\n", start)
    literal = load_cell_text[start:end]
    import ast
    decoded = ast.literal_eval(literal)
    assert decoded == csv_pathological
    # And the load cell still ends with the expected DataFrame call.
    assert load_cell_text.rstrip().endswith('df.head()')


def test_notebook_surface_key_registered_in_surface_stats():
    """The analytics layer must count notebook serves alongside every
    other share surface."""
    assert "notebook_ipynb" in surface_stats.SURFACE_KEYS


# ── Wiring guards ──────────────────────────────────────────────────────


def test_route_decorator_present_in_simulation_api():
    """Ensure ``GET /<simulation_id>/notebook.ipynb`` is registered."""
    api_path = _BACKEND / "app" / "api" / "simulation.py"
    text = api_path.read_text(encoding="utf-8")
    assert "@simulation_bp.route('/<simulation_id>/notebook.ipynb'" in text
    assert "def get_notebook_ipynb(" in text


def test_router_module_imports_notebook_export():
    """The route handler must actually import the service we just shipped.

    Same guard pattern the reproduce.json and surface_stats tests use —
    catches the failure mode where the route decorator was added but
    the body never got wired up.
    """
    api_path = _BACKEND / "app" / "api" / "simulation.py"
    text = api_path.read_text(encoding="utf-8")
    assert "from ..services import notebook_export" in text


def test_openapi_path_declared():
    """Swagger UI must pick up the new endpoint."""
    spec_path = _BACKEND / "openapi.yaml"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/notebook.ipynb" in spec_text


def test_openapi_surface_stats_includes_notebook_counter():
    """``SimulationSurfaceStats`` must document the new counter so the
    analytics envelope stays in sync with ``SURFACE_KEYS``."""
    spec_path = _BACKEND / "openapi.yaml"
    spec_text = spec_path.read_text(encoding="utf-8")
    # The field name appears on both the schema definition and the
    # endpoint description — at minimum the schema definition has to
    # carry it.
    assert "notebook_ipynb:" in spec_text
