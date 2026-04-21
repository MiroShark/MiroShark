"""Shared pytest fixtures + markers for MiroShark.

Layout::

    backend/tests/
        conftest.py              ← this file: fixtures + skip logic
        test_unit_*.py           ← fast offline tests (run on every commit)
        test_integration_*.py    ← hit a live backend at $MIROSHARK_API_URL
                                   (opt in with `pytest -m integration`)

Existing hand-run scripts in ``backend/scripts/test_*.py`` stay as-is so
operators can still invoke them directly; the integration tests here wrap
them and register them for discovery.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import pytest


# Make ``import app`` / ``import scripts`` work regardless of where pytest
# is invoked from. Repo layout: ``backend/{app,scripts,tests}``.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _BACKEND_DIR / "scripts"
for p in (_BACKEND_DIR, _SCRIPTS_DIR):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def pytest_configure(config):
    """Register custom markers so ``-m integration`` doesn't emit warnings."""
    config.addinivalue_line(
        "markers",
        "integration: requires a live MiroShark backend at MIROSHARK_API_URL "
        "(default http://localhost:5001). Opt in with `pytest -m integration`.",
    )
    config.addinivalue_line(
        "markers",
        "slow: long-running tests (multi-minute E2E simulations).",
    )
    config.addinivalue_line(
        "markers",
        "neo4j: requires a running Neo4j at $NEO4J_URI.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip ``@pytest.mark.integration`` tests by default.

    Run them explicitly with ``pytest -m integration`` (or
    ``pytest -m "integration or not integration"`` for everything).
    """
    selected_marker = config.getoption("-m") or ""
    if "integration" in selected_marker:
        return  # user asked for integration — don't skip
    skip_marker = pytest.mark.skip(
        reason="integration test — run with `pytest -m integration`"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Base URL for the running MiroShark backend under test."""
    return os.environ.get("MIROSHARK_API_URL", "http://localhost:5001").rstrip("/")


@pytest.fixture(scope="session")
def live_backend(api_base_url: str) -> str:
    """Assert the backend is reachable before running integration tests.

    Skips the test (rather than failing) when /health is unreachable so CI
    without infra can still succeed on the unit suite.
    """
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{api_base_url}/health", timeout=3) as r:
            if r.status != 200:
                pytest.skip(f"backend /health returned {r.status}")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        pytest.skip(f"no backend at {api_base_url}: {e}")
    return api_base_url


@pytest.fixture(scope="session")
def sample_simulation_id() -> Optional[str]:
    """Opt-in: reuse an existing simulation id from $MIROSHARK_TEST_SIM_ID.

    Many integration tests need a simulation_id to exercise endpoints like
    /frame and /publish. Setting ``MIROSHARK_TEST_SIM_ID=sim_xxx`` lets the
    suite skip the expensive "run a full simulation" step.
    """
    sid = os.environ.get("MIROSHARK_TEST_SIM_ID") or None
    if not sid:
        pytest.skip("set MIROSHARK_TEST_SIM_ID=sim_xxx to run this test")
    return sid
