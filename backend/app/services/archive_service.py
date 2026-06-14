"""Simulation archive bundle — one ZIP, every published surface inside.

The twelfth share surface on top of share-card (PNG verdict), replay
GIF (motion), transcript (Markdown + JSON prose), trajectory (CSV +
JSONL data), thread (TXT + JSON social), watch page (live HTML),
``reproduce.json`` (citation), ``notebook.ipynb`` (analysis),
``chart.svg`` (vector visual), DKG citation (on-chain provenance),
Farcaster Frame v2 (Base-native social), and ``signal.json`` (trading
signal).

The previous eleven describe a finished simulation in eleven separate
HTTP routes — a researcher who wants the *complete* artifact set has to
chain six to ten ``curl`` calls and stitch the results together. This
surface collapses every per-sim primitive into a single timestamped ZIP
download plus a ``manifest.json`` that pairs every contained file with
its source URL + SHA-256 + size. Operators can "take a sim offline" in
one request; citation workflows get a single canonical archive whose
manifest hash anchors the whole bundle.

Design notes
------------

* **Pure stdlib.** ``zipfile`` + ``hashlib`` + ``io`` + ``json`` +
  ``datetime``. Zero new dependencies — same posture as every other
  surface module in this package.
* **Compositional, not duplicative.** Every bundled file comes from the
  same renderer the standalone surface route already serves
  (``share_card.render_share_card``, ``chart_svg.render_chart_svg_bytes``,
  ``trajectory_export.render_csv``, ``repro_export.render_json_bytes``,
  ``notebook_export.render_notebook_bytes``, ``signal_service.compute_signal``,
  ``transcript.render_markdown_bytes``, ``thread_formatter.render_thread_txt``).
  A file inside ``archive.zip`` is byte-for-byte identical to the same
  file fetched from its standalone URL — citation hashes line up.
* **Best-effort assembly.** Every surface builder is wrapped in a
  ``try/except`` and a missing-or-corrupt artifact yields an omitted
  entry rather than a 500. The manifest enumerates exactly what landed
  in the ZIP, so a consumer who needs a specific file can tell whether
  it was excluded vs. simply missing.
* **Deterministic file timestamps.** Every ``ZipInfo`` carries the same
  fixed ``date_time`` so the per-file portion of the ZIP is bytewise
  stable across requests. The ``manifest.json`` itself carries
  ``archive_generated_at`` which is the only field that drifts —
  consumers who need bit-stable archives can ignore the manifest
  timestamp when computing hashes.
* **Bounded by what's published.** The publish gate lives in the route
  handler — this module is happy to bundle anything it is handed.

Schema (manifest.json)::

    {
      "schema_version": "1",
      "simulation_id": "sim_abc123…",
      "archive_generated_at": "2026-05-20T12:34:56Z",
      "base_url": "https://miroshark.example.com",
      "file_count": 8,
      "files": [
        {
          "filename": "share-card.png",
          "sha256": "<hex>",
          "size_bytes": 12345,
          "source_url": "https://…/api/simulation/sim_abc/share-card.png",
          "mime_type": "image/png"
        },
        …
      ]
    }
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..utils.timeutils import utc_iso8601 as _utc_iso8601


SCHEMA_VERSION = "1"

# Canonical filename ordering inside the manifest. The ZIP file order
# follows this list so two archives of the same sim with the same set
# of surfaces produce a deterministic layout (manifest entries sorted
# in the same order as the ZIP central directory).
_CANONICAL_ORDER: tuple[str, ...] = (
    "share-card.png",
    "chart.svg",
    "trajectory.csv",
    "trajectory.jsonl",
    "transcript.md",
    "thread.txt",
    "reproduce.json",
    "notebook.ipynb",
    "signal.json",
)


# Fixed timestamp baked into every ZIP entry so the per-file portion of
# the archive is bytewise reproducible. Identical surfaces in identical
# order will produce identical ZIP bytes apart from the manifest.
_FIXED_ZIP_DATETIME: tuple[int, int, int, int, int, int] = (
    1980, 1, 1, 0, 0, 0,
)


# MIME type per filename so the manifest tells a consumer how to handle
# each file without sniffing magic bytes. Keys match ``_CANONICAL_ORDER``;
# unknown filenames fall back to ``application/octet-stream``.
_MIME_BY_FILENAME: Dict[str, str] = {
    "share-card.png": "image/png",
    "chart.svg": "image/svg+xml",
    "trajectory.csv": "text/csv",
    "trajectory.jsonl": "application/x-ndjson",
    "transcript.md": "text/markdown",
    "thread.txt": "text/plain",
    "reproduce.json": "application/json",
    "notebook.ipynb": "application/x-ipynb+json",
    "signal.json": "application/json",
}


# Source-URL suffix per filename — appended to the per-simulation base
# URL (``{base_url}/api/simulation/{sim_id}``) so the manifest carries
# the same canonical URL the standalone surface routes serve.
_URL_PATH_BY_FILENAME: Dict[str, str] = {
    "share-card.png": "/share-card.png",
    "chart.svg": "/chart.svg",
    "trajectory.csv": "/trajectory.csv",
    "trajectory.jsonl": "/trajectory.jsonl",
    "transcript.md": "/transcript.md",
    "thread.txt": "/thread.txt",
    "reproduce.json": "/reproduce.json",
    "notebook.ipynb": "/notebook.ipynb",
    "signal.json": "/signal.json",
}


logger = logging.getLogger(__name__)


def _sha256_hex(content: bytes) -> str:
    """Hex SHA-256 of the given bytes — matches the citation-hash
    convention used in ``reproduce.json``'s anchored DKG record."""
    return hashlib.sha256(content).hexdigest()


def _source_url(base_url: str, sim_id: str, filename: str) -> str:
    """Compose the canonical standalone-surface URL for ``filename``.

    Returns the empty string when ``base_url`` is missing so the
    manifest carries ``"source_url": ""`` rather than a half-formed
    URL. ``base_url`` is expected with no trailing slash (matches the
    convention in ``_resolve_share_base_url``).
    """
    if not base_url or not sim_id:
        return ""
    path = _URL_PATH_BY_FILENAME.get(filename, "")
    if not path:
        return ""
    return f"{base_url.rstrip('/')}/api/simulation/{sim_id}{path}"


def _safe_call(
    label: str,
    builder: Callable[[], Optional[bytes]],
) -> Optional[bytes]:
    """Invoke ``builder()`` and return the bytes — never raise.

    A best-effort archive must survive a missing artifact, a corrupt
    artifact, or an upstream renderer raising. Logs at WARNING so an
    operator monitoring the archive surface can see which sub-renderer
    failed; the archive itself proceeds with the remaining surfaces.
    """
    try:
        result = builder()
    except Exception as exc:  # noqa: BLE001 — best-effort by design
        logger.warning(
            "archive_service: %s builder raised, omitting from archive: %s",
            label,
            exc,
        )
        return None
    if not isinstance(result, (bytes, bytearray)):
        return None
    if not result:
        # A renderer that returns ``b""`` is treated as "no content for
        # this surface" — the archive omits the file rather than
        # bundling a zero-byte placeholder a consumer would have to
        # special-case.
        return None
    return bytes(result)


def _build_surfaces(
    *,
    sim_id: str,
    sim_dir: str,
    summary: Dict[str, Any],
    state_dict: Optional[Dict[str, Any]],
    config_data: Optional[Dict[str, Any]],
    base_url: str,
) -> List[Tuple[str, bytes]]:
    """Collect every successfully-renderable share surface as raw bytes.

    Each entry is ``(filename, content_bytes)``. The list is returned
    in the canonical order (``_CANONICAL_ORDER``) so two archive builds
    with the same set of available surfaces produce the same on-disk
    ZIP layout. Surfaces that fail to render (missing artifact,
    corrupted state file, missing dependency) are simply absent from
    the returned list — the manifest then enumerates whatever did land.
    """
    # Local imports keep this module importable in unit tests that
    # stub out specific renderers, and avoid a circular import via the
    # ``signal_service`` ↔ ``archive_service`` ↔ ``surface_stats``
    # triangle when this module is loaded by the application factory.
    from . import chart_svg as _chart_svg
    from . import notebook_export as _notebook_export
    from . import repro_export as _repro_export
    from . import signal_service as _signal_service
    from . import thread_formatter as _thread_formatter
    from . import trajectory_export as _trajectory_export
    from . import transcript as _transcript

    state_for_repro: Dict[str, Any] = (
        state_dict if isinstance(state_dict, dict) else {}
    )
    config_for_repro: Dict[str, Any] = (
        config_data if isinstance(config_data, dict) else {}
    )
    scenario_text = ""
    if isinstance(summary, dict):
        raw_scenario = summary.get("scenario")
        if isinstance(raw_scenario, str):
            scenario_text = raw_scenario

    # Pre-compute the trajectory rows once — multiple downstream
    # surfaces consume the same row list (CSV, JSONL, and the notebook's
    # embedded CSV) so a single read keeps the archive cheap.
    try:
        rows = _trajectory_export.build_rows(sim_dir) if sim_dir else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("archive_service: trajectory rows failed: %s", exc)
        rows = []

    # Reproducibility blob — used both as a standalone surface and as
    # an input to the notebook builder.
    try:
        repro_blob = _repro_export.build_repro_config(
            state_for_repro, config_for_repro, sim_dir or ""
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("archive_service: repro blob failed: %s", exc)
        repro_blob = None

    def _build_share_card() -> Optional[bytes]:
        # ``share_card`` imports Pillow at module level — if Pillow is
        # unavailable (a stripped install) we still want the archive to
        # succeed with the remaining surfaces, so the import lives here.
        from . import share_card as _share_card
        return _share_card.render_share_card(summary)

    def _build_chart_svg() -> Optional[bytes]:
        return _chart_svg.render_chart_svg_bytes(sim_dir or "", scenario_text)

    def _build_trajectory_csv() -> Optional[bytes]:
        if not rows:
            return None
        return _trajectory_export.render_csv(rows)

    def _build_trajectory_jsonl() -> Optional[bytes]:
        if not rows:
            return None
        return _trajectory_export.render_jsonl(rows)

    def _build_transcript_md() -> Optional[bytes]:
        data = _transcript.build_transcript_data(summary, sim_dir or "")
        if not isinstance(data, dict):
            return None
        return _transcript.render_markdown_bytes(data)

    def _build_thread_txt() -> Optional[bytes]:
        watch_url = f"{base_url.rstrip('/')}/watch/{sim_id}" if base_url and sim_id else ""
        share_url = f"{base_url.rstrip('/')}/share/{sim_id}" if base_url and sim_id else ""
        thread = _thread_formatter.build_thread(
            sim_dir=sim_dir or "",
            summary=summary,
            watch_url=watch_url,
            share_url=share_url,
        )
        if not isinstance(thread, dict):
            return None
        return _thread_formatter.render_thread_txt(thread)

    def _build_reproduce_json() -> Optional[bytes]:
        if not isinstance(repro_blob, dict):
            return None
        return _repro_export.render_json_bytes(repro_blob)

    def _build_notebook_ipynb() -> Optional[bytes]:
        if not rows or not isinstance(repro_blob, dict):
            return None
        csv_bytes = _trajectory_export.render_csv(rows)
        csv_text = csv_bytes.decode("utf-8")
        notebook = _notebook_export.build_notebook(
            sim_id=sim_id,
            csv_text=csv_text,
            repro_blob=repro_blob,
            base_url=base_url or "",
        )
        return _notebook_export.render_notebook_bytes(notebook)

    def _build_signal_json() -> Optional[bytes]:
        signal = _signal_service.compute_signal(summary)
        if not isinstance(signal, dict):
            return None
        signal["simulation_id"] = sim_id
        return json.dumps(
            signal, indent=2, sort_keys=True, ensure_ascii=False
        ).encode("utf-8") + b"\n"

    # Builder table keyed by canonical filename — the order this dict
    # is iterated does not matter; the returned list is reordered to
    # ``_CANONICAL_ORDER`` below.
    builders: Dict[str, Callable[[], Optional[bytes]]] = {
        "share-card.png": _build_share_card,
        "chart.svg": _build_chart_svg,
        "trajectory.csv": _build_trajectory_csv,
        "trajectory.jsonl": _build_trajectory_jsonl,
        "transcript.md": _build_transcript_md,
        "thread.txt": _build_thread_txt,
        "reproduce.json": _build_reproduce_json,
        "notebook.ipynb": _build_notebook_ipynb,
        "signal.json": _build_signal_json,
    }

    out: List[Tuple[str, bytes]] = []
    for filename in _CANONICAL_ORDER:
        builder = builders.get(filename)
        if builder is None:
            continue
        content = _safe_call(filename, builder)
        if content is None:
            continue
        out.append((filename, content))
    return out


def build_manifest(
    *,
    sim_id: str,
    surfaces: List[Tuple[str, bytes]],
    base_url: str,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Compose the manifest dict from a list of ``(filename, bytes)``.

    ``generated_at`` overrides the timestamp on the returned manifest
    — exposed so the tests can pin a deterministic value. Production
    callers omit it and get the live UTC timestamp.

    Returns a dict matching the schema in the module docstring.
    """
    files: List[Dict[str, Any]] = []
    for filename, content in surfaces:
        files.append(
            {
                "filename": filename,
                "sha256": _sha256_hex(content),
                "size_bytes": len(content),
                "source_url": _source_url(base_url, sim_id, filename),
                "mime_type": _MIME_BY_FILENAME.get(
                    filename, "application/octet-stream"
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_id": sim_id,
        "archive_generated_at": generated_at or _utc_iso8601(),
        "base_url": base_url or "",
        "file_count": len(files),
        "files": files,
    }


def render_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    """Pretty-print the manifest as UTF-8 bytes for inclusion in the ZIP.

    ``sort_keys=True`` + ``indent=2`` + trailing newline — same shape
    as ``reproduce.json`` and ``notebook.ipynb`` so two consumers
    inspecting the archive see the same pretty-printed structure.
    """
    return (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def build_archive_zip(
    surfaces: List[Tuple[str, bytes]],
    manifest_bytes: bytes,
) -> bytes:
    """Encode ``surfaces`` + ``manifest.json`` as a single ZIP byte stream.

    The ZIP is built with ``ZIP_DEFLATED`` (default zlib compression)
    — share-card PNGs and chart SVGs compress well enough that the
    archive lands at ~30-60% of the sum of its inputs. Every
    ``ZipInfo`` entry carries the same ``_FIXED_ZIP_DATETIME`` so the
    per-file portion of the bytes is reproducible across two builds
    of the same input set. The manifest is always written last so a
    streaming consumer can find it at the end of the central directory.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in surfaces:
            info = zipfile.ZipInfo(filename=filename, date_time=_FIXED_ZIP_DATETIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Permissions: regular file, owner-read/write, group/other-
            # read. Matches what ``zipfile.write()`` would emit for a
            # 0644 file on disk.
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, content)

        # Manifest last so the central-directory order ends with it,
        # mirroring the on-disk layout a reader sees.
        manifest_info = zipfile.ZipInfo(
            filename="manifest.json", date_time=_FIXED_ZIP_DATETIME
        )
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        manifest_info.external_attr = (0o644 & 0xFFFF) << 16
        zf.writestr(manifest_info, manifest_bytes)

    return buf.getvalue()


def build_archive(
    *,
    sim_id: str,
    sim_dir: str,
    summary: Dict[str, Any],
    state_dict: Optional[Dict[str, Any]] = None,
    config_data: Optional[Dict[str, Any]] = None,
    base_url: str = "",
) -> Tuple[bytes, Dict[str, Any]]:
    """Top-level entry point: bundle a published simulation into a ZIP.

    Args:
        sim_id: The simulation identifier — used in the manifest and
            in every per-file source URL.
        sim_dir: Absolute path to the on-disk simulation directory.
            Used by the trajectory / transcript / thread / reproduce
            sub-renderers to locate per-round artifacts.
        summary: The same dict ``_build_embed_summary_payload`` returns
            — provides scenario text, the final-round belief split, the
            quality block, and the publish flag (the caller is expected
            to have already gated on ``summary["is_public"]``).
        state_dict: Optional serialized ``SimulationState.to_dict()``
            — feeds the reproducibility blob's platform toggles and
            lineage fields.
        config_data: Optional ``simulation_config.json`` dict — feeds
            the reproducibility blob's time-config knobs.
        base_url: Optional fully-qualified base URL (no trailing slash)
            — used to populate the ``source_url`` field on every
            manifest entry. Pass the same value as
            ``_resolve_share_base_url`` returns so the manifest URLs
            match what the standalone surfaces serve.

    Returns:
        ``(zip_bytes, manifest_dict)``. The route handler emits
        ``zip_bytes`` as the response body; the manifest is also
        returned so the caller can log or surface counts without
        re-parsing the ZIP.
    """
    summary_dict: Dict[str, Any] = summary if isinstance(summary, dict) else {}

    surfaces = _build_surfaces(
        sim_id=sim_id,
        sim_dir=sim_dir or "",
        summary=summary_dict,
        state_dict=state_dict,
        config_data=config_data,
        base_url=base_url or "",
    )

    manifest = build_manifest(
        sim_id=sim_id,
        surfaces=surfaces,
        base_url=base_url or "",
    )
    manifest_bytes = render_manifest_bytes(manifest)
    zip_bytes = build_archive_zip(surfaces, manifest_bytes)
    return zip_bytes, manifest


# Re-exported so the test suite can pin against the locked filename
# set without re-deriving it. Order matches ``_CANONICAL_ORDER``.
CANONICAL_FILENAMES: tuple[str, ...] = _CANONICAL_ORDER
