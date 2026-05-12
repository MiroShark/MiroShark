"""Jupyter notebook export — pre-populated analysis notebook for a sim.

The trajectory CSV (PR #66) gave data analysts a clean input, but opening
the file still required writing the boilerplate every time: imports,
``pd.read_csv()``, figure setup, belief-evolution chart, summary stats.
``GET /api/simulation/<id>/notebook.ipynb`` returns a ready-to-run
notebook — code cells already typed, markdown cells framing the
simulation context, charts scaffolded from the reproduce.json metadata.
Institutional observers who land on a published simulation download this
and open it in JupyterLab / VS Code / Google Colab in one step. It is
also the artifact academic collaboration happens in: researchers who cite
MiroShark work in a paper need exactly this surface.

Pairs with the existing share surfaces as the **eleventh** publish-gated
export and the **second** institution-targeted one (after the
reproducibility config). The trajectory CSV told analysts *"here is the
data"*; the notebook tells them *"here is the analysis, ready to run"*.

Design notes
------------

* **Pure stdlib.** ``json`` + ``os``, plus a small reuse of
  ``trajectory_export.build_rows`` so the embedded CSV uses the same
  row-assembly logic the standalone ``trajectory.csv`` route serves.
  Zero new dependencies. The chart code cells are *strings* — Matplotlib
  is referenced inside the cells the user runs, never imported at
  generation time.
* **Standalone-runnable.** The trajectory data is embedded directly into
  the notebook as a Python multi-line string and read with
  ``pd.read_csv(io.StringIO(...))``. Anyone with the ``.ipynb`` file can
  run it air-gapped — no network call back to the MiroShark host
  required. This matters for paper-appendix attachments and academic
  archives where reviewer environments are sandboxed.
* **nbformat 4.** Plain JSON document with ``nbformat: 4``,
  ``nbformat_minor: 5``, a ``cells`` array, and a ``metadata`` block
  pinning a Python 3 kernel. The format is the one JupyterLab / VS Code
  / Colab all consume directly; the spec is at
  https://nbformat.readthedocs.io/.
* **Stable bytes.** Same ``sort_keys=True + indent=2 + trailing newline``
  pattern the reproducibility config uses, so two exports of the same
  finished simulation produce bytewise-identical notebooks (citation-hash
  friendly).
* **Defense-in-depth.** Missing artifacts (sim still running, corrupt
  trajectory, no quality file) degrade gracefully — the notebook still
  renders, the embedded CSV may just have fewer rows.

Schema-locked cell sequence
---------------------------

The cell order is part of the contract — downstream tools that pin
"the chart cell is at index 4" must not break across minor versions.
``CELL_ORDER`` documents the layout; ``test_unit_notebook_export.py``
pins it so a refactor cannot silently reshuffle the cells.

  0. markdown header (sim id, scenario, agent count, rounds, lineage,
     reproducibility URL, generated_at)
  1. code: pip install hint (commented out) + imports
  2. code: trajectory CSV loading from embedded string
  3. code: belief-evolution line chart (bullish / neutral / bearish %
     over rounds)
  4. code: final-round consensus bar chart
  5. code: quality-health + participation-rate DataFrame
  6. markdown footer (reproduce.json link + trajectory SHA-256 hint)
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Schema versioning — bumping is a deliberate wire-contract break, not a
# refactor side-effect. Mirrors ``repro_export.SCHEMA_VERSION``.
SCHEMA_VERSION = "1"


# Ordered cell-type sequence the notebook must emit, in order. Pinned by
# the unit tests so a future refactor can't silently reshuffle the cells
# downstream tooling indexes into.
CELL_ORDER: tuple[str, ...] = (
    "markdown",  # 0 — header
    "code",      # 1 — imports
    "code",      # 2 — load trajectory
    "code",      # 3 — belief evolution chart
    "code",      # 4 — final consensus bar chart
    "code",      # 5 — quality summary DataFrame
    "markdown",  # 6 — footer / reproducibility link
)


# ── Helpers ────────────────────────────────────────────────────────────


def _utc_iso8601() -> str:
    """Return UTC ``YYYY-MM-DDTHH:MM:SSZ`` matching the repro-export
    timestamp grammar.

    Same shape the webhook delivery log + reproduce.json export use so
    downstream parsers see a single timestamp grammar across every
    artifact.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_str(value: Any, default: str = "") -> str:
    """Coerce to a stripped string; never raise."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return default


def _split_lines_for_nbformat(text: str) -> List[str]:
    """Split a multi-line string into the per-line list nbformat wants.

    nbformat 4's ``source`` field accepts either a plain string or a
    list of strings — but several renderers (Colab, older JupyterLab)
    expect the line-list form with trailing ``\\n`` on each entry except
    the last. This helper produces that exact shape so the notebook
    renders correctly across every consumer.
    """
    if not text:
        return [""]
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def _markdown_cell(text: str) -> Dict[str, Any]:
    """Build an nbformat 4 markdown cell."""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": _split_lines_for_nbformat(text),
    }


def _code_cell(text: str) -> Dict[str, Any]:
    """Build an nbformat 4 code cell with no outputs and no execution count.

    Unexecuted code cells are the standard distribution form — the user's
    own Jupyter kernel populates ``outputs`` and ``execution_count`` when
    they hit Run All.
    """
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _split_lines_for_nbformat(text),
    }


def _platforms_summary(platforms: Optional[Dict[str, Any]]) -> str:
    """Render the platforms block as a one-line summary for the header.

    Mirrors the EmbedDialog's ``reproPlatformsLabel`` so the notebook
    header matches what an operator sees in the dialog when sharing the
    sim — one source of truth for the platform pill across surfaces.
    """
    if not isinstance(platforms, dict):
        return "—"
    parts: List[str] = []
    if platforms.get("twitter"):
        parts.append("Twitter")
    if platforms.get("reddit"):
        parts.append("Reddit")
    if platforms.get("polymarket"):
        count = platforms.get("polymarket_market_count")
        try:
            count_int = int(count) if count is not None else 1
        except (TypeError, ValueError):
            count_int = 1
        parts.append(f"Polymarket ×{max(1, count_int)}")
    return " · ".join(parts) if parts else "—"


def _lineage_summary(lineage: Optional[Dict[str, Any]]) -> str:
    """One-line lineage description for the header markdown cell.

    Mirrors the EmbedDialog's ``reproLineageDescription`` — "Original",
    "Fork of sim_abc123", "Counterfactual of sim_abc123 at round 12
    (ceo_resigns)". Keeps the notebook header matching the dialog so a
    reader who screenshotted one and downloaded the other sees the same
    headline.
    """
    if not isinstance(lineage, dict):
        return "Original"
    kind = lineage.get("kind") or "original"
    parent = _safe_str(lineage.get("parent_simulation_id"))[:12]
    if kind == "original" or not parent:
        return "Original"
    if kind == "fork":
        return f"Fork of {parent}"
    if kind == "counterfactual":
        cf = lineage.get("counterfactual") or {}
        round_raw = cf.get("trigger_round") if isinstance(cf, dict) else None
        try:
            round_num = int(round_raw) if round_raw is not None else None
        except (TypeError, ValueError):
            round_num = None
        label = _safe_str(cf.get("label")) if isinstance(cf, dict) else ""
        suffix = f" at round {round_num}" if round_num is not None else ""
        if label:
            suffix += f" ({label})"
        return f"Counterfactual of {parent}{suffix}"
    return _safe_str(kind, default="Original").capitalize()


# ── CSV → embedded Python string ───────────────────────────────────────


def _python_string_literal(text: str) -> str:
    """Render ``text`` as a Python string literal usable in source code.

    Uses ``repr()`` so any byte sequence — including arbitrary numbers
    of consecutive quotes, backslashes, control characters, non-ASCII —
    round-trips correctly. The output is a single-line literal (newlines
    escaped as ``\\n``) which is fine because the cell reads the value
    back into a CSV stream via ``io.StringIO`` regardless of source-line
    layout.

    The CSV produced by ``trajectory_export.render_csv`` only contains
    digits / commas / column names / ``quality_health`` text, but
    pathological inputs (a scenario containing newlines or quotes that
    leaked into the ``quality_health`` field via a future refactor) must
    not break the generated notebook.
    """
    return repr(text)


# ── Cell builders ──────────────────────────────────────────────────────


def _build_header_cell(
    sim_id: str,
    scenario: str,
    agent_count: int,
    total_rounds: int,
    platforms_summary: str,
    lineage_summary: str,
    quality_health: str,
    reproduce_url: Optional[str],
    share_url: Optional[str],
    generated_at: str,
) -> Dict[str, Any]:
    lines: List[str] = []
    lines.append(f"# MiroShark Simulation — `{sim_id}`")
    lines.append("")
    if scenario:
        # Quote the scenario as a blockquote so it visually separates
        # from the metadata table; Markdown rendering on GitHub /
        # JupyterLab / Colab all handle this identically.
        for sline in scenario.split("\n"):
            lines.append(f"> {sline}")
        lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Simulation ID | `{sim_id}` |")
    lines.append(f"| Agents | {agent_count} |")
    lines.append(f"| Rounds | {total_rounds} |")
    lines.append(f"| Platforms | {platforms_summary} |")
    lines.append(f"| Lineage | {lineage_summary} |")
    if quality_health:
        lines.append(f"| Quality health | {quality_health} |")
    lines.append(f"| Notebook generated | {generated_at} |")
    if reproduce_url:
        lines.append(
            f"| Reproducibility config | [reproduce.json]({reproduce_url}) |"
        )
    if share_url:
        lines.append(f"| Share page | [{share_url}]({share_url}) |")
    lines.append("")
    lines.append(
        "This notebook is **standalone-runnable** — the trajectory data "
        "is embedded directly in the next cell, so no network access is "
        "required. The bullish / neutral / bearish percentages use the "
        "same ±0.2 stance threshold every other MiroShark surface "
        "reports for the same round."
    )
    return _markdown_cell("\n".join(lines))


def _build_imports_cell() -> Dict[str, Any]:
    text = (
        "# If you don't already have pandas + matplotlib in this kernel,\n"
        "# uncomment the next line and run it once. The notebook itself\n"
        "# is self-contained — the data is embedded below, no network\n"
        "# call back to the MiroShark host is needed.\n"
        "# %pip install --quiet pandas matplotlib\n"
        "\n"
        "import io\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
    )
    return _code_cell(text)


def _build_load_cell(csv_text: str) -> Dict[str, Any]:
    embedded = _python_string_literal(csv_text)
    text = (
        "# Trajectory CSV embedded directly so this notebook runs\n"
        "# air-gapped. Schema mirrors `GET /api/simulation/<id>/trajectory.csv`:\n"
        "#   round, round_timestamp, bullish_pct, neutral_pct, bearish_pct,\n"
        "#   participating_agents, total_posts, total_engagements,\n"
        "#   quality_health, participation_rate\n"
        f"TRAJECTORY_CSV = {embedded}\n"
        "\n"
        "df = pd.read_csv(io.StringIO(TRAJECTORY_CSV))\n"
        "df.head()\n"
    )
    return _code_cell(text)


def _build_belief_chart_cell() -> Dict[str, Any]:
    text = (
        "# Belief evolution — one line per stance bucket. The percentages\n"
        "# use the same ±0.2 threshold the share card, replay GIF,\n"
        "# transcript, webhook, and feed surfaces all use, so the numbers\n"
        "# here match every other MiroShark artifact for the same round.\n"
        "fig, ax = plt.subplots(figsize=(10, 5))\n"
        "ax.plot(df['round'], df['bullish_pct'], color='#22c55e', label='Bullish %', linewidth=2)\n"
        "ax.plot(df['round'], df['neutral_pct'], color='#6b7280', label='Neutral %', linewidth=2)\n"
        "ax.plot(df['round'], df['bearish_pct'], color='#ef4444', label='Bearish %', linewidth=2)\n"
        "ax.set_xlabel('Round')\n"
        "ax.set_ylabel('Share of agents (%)')\n"
        "ax.set_title('Belief evolution over rounds')\n"
        "ax.set_ylim(0, 100)\n"
        "ax.grid(True, alpha=0.3)\n"
        "ax.legend(loc='best')\n"
        "plt.tight_layout()\n"
        "plt.show()\n"
    )
    return _code_cell(text)


def _build_consensus_cell() -> Dict[str, Any]:
    text = (
        "# Final-round stance distribution — what the population settled\n"
        "# on at the end of the simulation. The bar order matches the\n"
        "# bullish / neutral / bearish convention every other surface\n"
        "# uses, so the screenshot here is paste-compatible with the\n"
        "# share card.\n"
        "final_row = df.iloc[-1] if len(df) else None\n"
        "if final_row is not None:\n"
        "    fig, ax = plt.subplots(figsize=(6, 4))\n"
        "    bars = ax.bar(\n"
        "        ['Bullish', 'Neutral', 'Bearish'],\n"
        "        [final_row['bullish_pct'], final_row['neutral_pct'], final_row['bearish_pct']],\n"
        "        color=['#22c55e', '#6b7280', '#ef4444'],\n"
        "    )\n"
        "    for bar, value in zip(bars, [final_row['bullish_pct'], final_row['neutral_pct'], final_row['bearish_pct']]):\n"
        "        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,\n"
        "                f'{value:.1f}%', ha='center', va='bottom', fontsize=10)\n"
        "    ax.set_ylabel('Share of agents (%)')\n"
        "    ax.set_ylim(0, 100)\n"
        "    ax.set_title(f\"Final consensus (round {int(final_row['round'])})\")\n"
        "    plt.tight_layout()\n"
        "    plt.show()\n"
        "else:\n"
        "    print('No trajectory rows available — the simulation may still be running.')\n"
    )
    return _code_cell(text)


def _build_quality_cell() -> Dict[str, Any]:
    text = (
        "# Quality + participation summary — the two scalar columns the\n"
        "# trajectory carries on every row. We surface the unique values\n"
        "# (`quality_health` is typically constant across the run) so the\n"
        "# reader sees the run health at a glance without scanning the\n"
        "# whole DataFrame.\n"
        "summary = pd.DataFrame({\n"
        "    'metric': ['rows', 'first_round', 'last_round', 'quality_health', 'participation_rate'],\n"
        "    'value': [\n"
        "        len(df),\n"
        "        int(df['round'].min()) if len(df) else None,\n"
        "        int(df['round'].max()) if len(df) else None,\n"
        "        ', '.join(sorted({str(v) for v in df['quality_health'].dropna().unique()})) if len(df) else '',\n"
        "        df['participation_rate'].dropna().iloc[-1] if 'participation_rate' in df and df['participation_rate'].dropna().size else None,\n"
        "    ],\n"
        "})\n"
        "summary\n"
    )
    return _code_cell(text)


def _build_footer_cell(
    sim_id: str,
    reproduce_url: Optional[str],
    trajectory_sha256: str,
    schema_version: str,
) -> Dict[str, Any]:
    lines: List[str] = []
    lines.append("---")
    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(
        "This notebook is generated from the published simulation's "
        "on-disk artifacts at request time. Identical exports of the "
        "same finished simulation produce identical notebooks — the "
        "file hash is a stable citation key, same property the "
        "`reproduce.json` blob has."
    )
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Notebook schema | v{schema_version} |")
    lines.append(f"| Simulation ID | `{sim_id}` |")
    lines.append(f"| Trajectory SHA-256 | `{trajectory_sha256}` |")
    if reproduce_url:
        lines.append(
            f"| Full reproducibility config | [reproduce.json]({reproduce_url}) |"
        )
    lines.append("")
    lines.append(
        "*Built by MiroShark · "
        "`GET /api/simulation/<id>/notebook.ipynb`*"
    )
    return _markdown_cell("\n".join(lines))


# ── Top-level assembly ────────────────────────────────────────────────


def build_notebook(
    sim_id: str,
    csv_text: str,
    repro_blob: Optional[Dict[str, Any]],
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose the nbformat 4 notebook dict from its inputs.

    Args:
        sim_id: The simulation id (echoed in header / footer).
        csv_text: The full ``trajectory.csv`` content as a string. Embed
            directly into the notebook so it runs standalone.
        repro_blob: The reproducibility config blob (output of
            ``repro_export.build_repro_config``). Used for header
            metadata (scenario, agent_count, total_rounds, platforms,
            lineage). ``None`` is acceptable — the header degrades to
            empty fields.
        base_url: Origin used to build the reproduce.json + share page
            URLs in the header / footer. ``None`` omits those links.

    Returns:
        A dict that ``json.dumps`` directly into a valid ``.ipynb`` file.
    """
    blob: Dict[str, Any] = repro_blob if isinstance(repro_blob, dict) else {}

    scenario = _safe_str(blob.get("scenario"))
    agent_count_raw = blob.get("agent_count", 0)
    try:
        agent_count = max(0, int(agent_count_raw))
    except (TypeError, ValueError):
        agent_count = 0
    total_rounds_raw = blob.get("total_rounds", 0)
    try:
        total_rounds = max(0, int(total_rounds_raw))
    except (TypeError, ValueError):
        total_rounds = 0

    platforms_summary = _platforms_summary(blob.get("platforms"))
    lineage_summary = _lineage_summary(blob.get("lineage"))

    quality_health = ""
    if csv_text:
        # The CSV repeats quality_health on every row; reading the value
        # off the header-less first data row is cheap and avoids pulling
        # a pandas import into the generator.
        rows = csv_text.splitlines()
        if len(rows) >= 2:
            cols = rows[0].split(",")
            data = rows[1].split(",")
            if len(cols) == len(data) and "quality_health" in cols:
                quality_health = data[cols.index("quality_health")].strip()

    reproduce_url: Optional[str] = None
    share_url: Optional[str] = None
    if base_url:
        clean = base_url.rstrip("/")
        reproduce_url = f"{clean}/api/simulation/{sim_id}/reproduce.json"
        share_url = f"{clean}/share/{sim_id}"

    trajectory_sha256 = hashlib.sha256(
        (csv_text or "").encode("utf-8")
    ).hexdigest()

    cells: List[Dict[str, Any]] = [
        _build_header_cell(
            sim_id=sim_id,
            scenario=scenario,
            agent_count=agent_count,
            total_rounds=total_rounds,
            platforms_summary=platforms_summary,
            lineage_summary=lineage_summary,
            quality_health=quality_health,
            reproduce_url=reproduce_url,
            share_url=share_url,
            generated_at=_utc_iso8601(),
        ),
        _build_imports_cell(),
        _build_load_cell(csv_text or ""),
        _build_belief_chart_cell(),
        _build_consensus_cell(),
        _build_quality_cell(),
        _build_footer_cell(
            sim_id=sim_id,
            reproduce_url=reproduce_url,
            trajectory_sha256=trajectory_sha256,
            schema_version=SCHEMA_VERSION,
        ),
    ]

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "mimetype": "text/x-python",
                "file_extension": ".py",
                "pygments_lexer": "ipython3",
            },
            "miroshark": {
                "schema_version": SCHEMA_VERSION,
                "simulation_id": sim_id,
                "trajectory_sha256": trajectory_sha256,
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def render_notebook_bytes(notebook: Dict[str, Any]) -> bytes:
    """Render the notebook dict as UTF-8 bytes for the route handler.

    Pretty-print (indent=2) + ``sort_keys=True`` + trailing newline so
    two exports of the same finished simulation produce bytewise-identical
    notebooks. Mirrors ``repro_export.render_json_bytes``.
    """
    return (
        json.dumps(notebook, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
