"""Unit tests for the observability HTTP routes.

These pin down the contract that ``/api/observability/events`` and
``/api/observability/llm-calls`` accept malformed query-string integers
(``?from_line=abc``, ``?limit=null``, ``?agent_id=foo``) without
returning a 500.

Pre-fix the routes called ``int(request.args.get(...))`` directly, which
raises ``ValueError`` on any non-numeric value and propagates as a Flask
500. Now they use Flask's ``type=int`` coercion, which silently falls
back to the default on parse failure.

Pure offline tests — no Flask app boot, no Neo4j, no LLM. They mount the
``observability_bp`` blueprint on a stub Flask app and point
``Config.WONDERWALL_SIMULATION_DATA_DIR`` at a temp dir so file reads
succeed (returning empty results) instead of touching the host
filesystem.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture
def flask_app(tmp_path: Path, monkeypatch):
    """Tiny Flask app with the observability blueprint mounted.

    Importing ``app.api.observability`` is safe — it pulls in
    ``EventLogger``/``FileTailer`` but neither touches Neo4j or the LLM
    layer. Both ``LOG_DIR`` and the per-sim path key off
    ``Config.WONDERWALL_SIMULATION_DATA_DIR`` / ``LOG_DIR`` from
    ``event_logger``; we redirect both at temp dirs so the file reads
    succeed (no path) and return empty results.
    """
    from flask import Flask

    monkeypatch.setattr(
        'app.utils.event_logger.LOG_DIR', str(tmp_path / 'logs'),
        raising=False,
    )

    from app.config import Config
    monkeypatch.setattr(
        Config, 'WONDERWALL_SIMULATION_DATA_DIR', str(tmp_path / 'sims'),
        raising=False,
    )

    # Importing app.api triggers the side-effectful registration of routes
    # onto observability_bp via app.api.observability, so the blueprint is
    # ready to mount.
    from app.api import observability_bp

    flask_app = Flask(__name__)
    flask_app.register_blueprint(observability_bp, url_prefix='/api/observability')
    return flask_app


def test_events_accepts_garbage_from_line(flask_app):
    """``?from_line=abc`` falls back to the default 0 instead of 500-ing."""
    client = flask_app.test_client()
    resp = client.get('/api/observability/events?from_line=not-a-number')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['from_line'] == 0


def test_events_accepts_garbage_limit(flask_app):
    client = flask_app.test_client()
    resp = client.get('/api/observability/events?limit=null')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


def test_events_accepts_garbage_agent_and_round(flask_app):
    client = flask_app.test_client()
    resp = client.get(
        '/api/observability/events?agent_id=foo&round_num=bar'
    )
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True


def test_events_passes_through_valid_ints(flask_app):
    client = flask_app.test_client()
    resp = client.get(
        '/api/observability/events?from_line=10&limit=5&agent_id=42'
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['from_line'] == 10


def test_llm_calls_accepts_garbage_pagination(flask_app):
    """Pre-fix ``int(request.args.get('from_line', 0))`` 500'd on bad input."""
    client = flask_app.test_client()
    resp = client.get(
        '/api/observability/llm-calls?from_line=abc&limit=xyz'
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['from_line'] == 0
    assert body['count'] == 0
