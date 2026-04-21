"""Wraps the hand-run ``backend/scripts/test_*.py`` scripts for pytest.

Each legacy script was written as a standalone program with a ``main()``
function. These tests invoke them as subprocesses and assert a zero exit
code — pragmatic, preserves the scripts (operators still run them directly),
and gets them into the suite.

Legacy scripts are all marked ``@pytest.mark.integration`` + ``@pytest.mark.slow``
because most require a running backend and/or Neo4j; they're opt-in via::

    pytest -m "integration and slow"

Individual scripts can be targeted by test ID::

    pytest -m "integration and slow" -k test_profile_format
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# (script_name, needs_backend, needs_neo4j)
_LEGACY_SCRIPTS = [
    ("test_profile_format.py",             False, False),
    ("test_polymarket.py",                 False, False),
    ("test_market_generation.py",          False, True),
    ("test_3platform_interconnected.py",   False, True),
    ("test_report_generation.py",          False, True),
    ("test_full_pipeline.py",              False, True),
    ("test_pipeline_phase5_6.py",          False, True),
    ("test_pipeline_twitter_polymarket.py", False, True),
    ("test_e2e_api.py",                    True,  True),
]


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize(
    "script_name,needs_backend,needs_neo4j",
    _LEGACY_SCRIPTS,
    ids=[s[0].removeprefix("test_").removesuffix(".py") for s in _LEGACY_SCRIPTS],
)
def test_legacy_script(script_name: str, needs_backend: bool, needs_neo4j: bool, live_backend: str):
    """Run a legacy script and assert exit 0.

    ``live_backend`` fixture ensures the server is up. The legacy scripts
    themselves check for Neo4j and will skip / fail fast if it's missing.
    """
    script_path = _SCRIPTS_DIR / script_name
    if not script_path.exists():
        pytest.skip(f"legacy script missing: {script_path}")

    # Bound wall time — some of these run 10+ minutes. CI should use shorter
    # timeouts per-script; here we cap at 30 min to prevent hangs.
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"{script_name} timed out after {e.timeout}s")

    if result.returncode != 0:
        tail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-40:])
        pytest.fail(f"{script_name} exited {result.returncode}\n---tail---\n{tail}")
