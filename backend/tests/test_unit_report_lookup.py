"""Unit tests for ``ReportManager.get_report_by_simulation`` (issue #323).

A simulation can own several reports: ``force_regenerate`` writes a new
``report_<hex>`` folder and keeps the old one. The lookup used to return
the first match in ``os.listdir`` order, so an old completed report could
shadow the newer one. These tests pin the newest-by-created_at behaviour
and the ``prefer_completed`` option.

Pure offline: a temp ``REPORTS_DIR``, no Flask app, no Neo4j, no LLM.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services.report_agent import (  # noqa: E402
    Report,
    ReportManager,
    ReportStatus,
)


SIM = "sim_lookup323"


@pytest.fixture
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    return tmp_path


def _save(report_id, status, created_at, simulation_id=SIM):
    ReportManager.save_report(Report(
        report_id=report_id,
        simulation_id=simulation_id,
        graph_id="graph_x",
        simulation_requirement="req",
        status=status,
        markdown_content=f"# {report_id}",
        created_at=created_at,
    ))


def _write_legacy(reports_dir, report_id, status, created_at):
    """Old storage form: ``<reports_dir>/<report_id>.json`` with no folder."""
    (reports_dir / f"{report_id}.json").write_text(json.dumps({
        "report_id": report_id,
        "simulation_id": SIM,
        "graph_id": "graph_x",
        "simulation_requirement": "req",
        "status": status.value,
        "created_at": created_at,
    }), encoding="utf-8")


def _lookup(**kwargs):
    report = ReportManager.get_report_by_simulation(SIM, **kwargs)
    return report.report_id if report else None


OLD = "2026-10-01T10:00:00.000001"
NEW = "2026-10-08T10:00:00.000001"


@pytest.mark.parametrize("newer_id,older_id", [
    ("report_ffffffffffff", "report_aaaaaaaaaaaa"),
    ("report_aaaaaaaaaaaa", "report_ffffffffffff"),
])
def test_newer_completed_report_wins(reports_dir, newer_id, older_id):
    # Run with both name orders (and save orders) so the result can't
    # depend on os.listdir order.
    _save(newer_id, ReportStatus.COMPLETED, NEW)
    _save(older_id, ReportStatus.COMPLETED, OLD)

    assert _lookup() == newer_id
    assert _lookup(prefer_completed=True) == newer_id


def test_newer_generating_report_wins_by_default(reports_dir):
    """The force_regenerate case: status pollers must see the new report."""
    _save("report_old000000000", ReportStatus.COMPLETED, OLD)
    _save("report_new000000000", ReportStatus.GENERATING, NEW)

    assert _lookup() == "report_new000000000"


def test_prefer_completed_skips_newer_unfinished_reports(reports_dir):
    _save("report_old000000000", ReportStatus.COMPLETED, OLD)
    _save("report_gen000000000", ReportStatus.GENERATING, NEW)
    _save("report_bad000000000", ReportStatus.FAILED, "2026-10-09T10:00:00")

    assert _lookup(prefer_completed=True) == "report_old000000000"
    assert _lookup() == "report_bad000000000"


def test_prefer_completed_falls_back_to_newest_when_none_completed(reports_dir):
    _save("report_bad000000000", ReportStatus.FAILED, OLD)
    _save("report_gen000000000", ReportStatus.GENERATING, NEW)

    assert _lookup(prefer_completed=True) == "report_gen000000000"


def test_legacy_json_reports_are_ranked_with_folders(reports_dir):
    _write_legacy(reports_dir, "report_legacy000000", ReportStatus.COMPLETED, OLD)
    _save("report_folder000000", ReportStatus.COMPLETED, NEW)
    assert _lookup() == "report_folder000000"

    _write_legacy(reports_dir, "report_legacy111111", ReportStatus.COMPLETED,
                  "2026-10-10T10:00:00")
    assert _lookup() == "report_legacy111111"


def test_missing_or_null_created_at_sorts_oldest(reports_dir):
    _save("report_dated0000000", ReportStatus.COMPLETED, OLD)
    _save("report_empty0000000", ReportStatus.COMPLETED, "")
    _write_legacy(reports_dir, "report_null00000000", ReportStatus.COMPLETED, None)

    assert _lookup() == "report_dated0000000"


def test_unreadable_report_is_skipped(reports_dir):
    _save("report_good0000000", ReportStatus.COMPLETED, OLD)
    broken = reports_dir / "report_broken000000"
    broken.mkdir()
    # Half-written meta.json, as seen mid-save by a concurrent reader.
    (broken / "meta.json").write_text('{"report_id": "report_brok', encoding="utf-8")

    assert _lookup() == "report_good0000000"


def test_other_simulations_and_empty_dir(reports_dir):
    assert _lookup() is None

    _save("report_other000000", ReportStatus.COMPLETED, NEW, simulation_id="sim_other")
    assert _lookup() is None

    _save("report_mine0000000", ReportStatus.COMPLETED, OLD)
    assert _lookup() == "report_mine0000000"
