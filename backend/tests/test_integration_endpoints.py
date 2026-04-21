"""Integration tests that exercise new endpoints against a live backend.

Requires::

    export MIROSHARK_API_URL=http://localhost:5001
    pytest -m integration backend/tests/test_integration_endpoints.py

For endpoints that need a pre-existing simulation::

    export MIROSHARK_TEST_SIM_ID=sim_xxx

Tests are designed to be cheap (no long-running simulations); they validate
API contracts rather than full pipelines. For full-pipeline smoke tests see
``backend/scripts/test_e2e_api.py`` (unchanged, still a manual script).
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error

import pytest


def _post(url: str, body: dict, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body_raw)
        except Exception:
            data = {"success": False, "error": body_raw}
        data.setdefault("_http_status", e.code)
        return data


def _get(url: str, timeout: float = 15.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body_raw)
        except Exception:
            data = {"success": False, "error": body_raw}
        data.setdefault("_http_status", e.code)
        return data


@pytest.mark.integration
def test_health_reachable(live_backend):
    req = urllib.request.Request(f"{live_backend}/health")
    with urllib.request.urlopen(req, timeout=3) as r:
        body = json.loads(r.read().decode("utf-8"))
    assert body.get("status") == "ok"


@pytest.mark.integration
def test_template_list_includes_oracle_and_cf_flags(live_backend):
    res = _get(f"{live_backend}/api/templates/list")
    assert res.get("success")
    assert res.get("data"), "expected at least one template"
    sample = res["data"][0]
    for field in ("id", "name", "has_counterfactuals", "has_oracle_tools"):
        assert field in sample


@pytest.mark.integration
def test_template_capabilities_endpoint(live_backend):
    res = _get(f"{live_backend}/api/templates/capabilities")
    assert res.get("success")
    data = res.get("data") or {}
    assert "oracle_seed_enabled" in data
    assert "mcp_agent_tools_enabled" in data


@pytest.mark.integration
def test_ask_requires_question(live_backend):
    res = _post(f"{live_backend}/api/simulation/ask", {})
    assert res.get("success") is False
    assert res.get("_http_status") == 400


@pytest.mark.integration
def test_ask_rejects_too_short_question(live_backend):
    res = _post(f"{live_backend}/api/simulation/ask", {"question": "hi"})
    assert res.get("success") is False
    assert res.get("_http_status") == 400


@pytest.mark.integration
def test_branch_counterfactual_validates_inputs(live_backend):
    # Missing parent_simulation_id
    res = _post(f"{live_backend}/api/simulation/branch-counterfactual", {
        "injection_text": "x" * 20,
        "trigger_round": 1,
    })
    assert res.get("success") is False
    assert res.get("_http_status") == 400

    # Missing injection_text
    res = _post(f"{live_backend}/api/simulation/branch-counterfactual", {
        "parent_simulation_id": "sim_fake",
        "trigger_round": 1,
    })
    assert res.get("success") is False
    assert res.get("_http_status") == 400

    # Negative trigger_round
    res = _post(f"{live_backend}/api/simulation/branch-counterfactual", {
        "parent_simulation_id": "sim_fake",
        "injection_text": "something meaningful",
        "trigger_round": -1,
    })
    assert res.get("success") is False
    assert res.get("_http_status") == 400


@pytest.mark.integration
def test_embed_summary_requires_publish(live_backend, sample_simulation_id):
    res = _get(f"{live_backend}/api/simulation/{sample_simulation_id}/embed-summary")
    # Either the sim is already published (200) or it 403s with a clear message.
    status = res.get("_http_status", 200)
    assert status in (200, 403, 404)
    if status == 403:
        assert "publish" in (res.get("error") or "").lower()


@pytest.mark.integration
def test_frame_endpoint_returns_snapshot(live_backend, sample_simulation_id):
    res = _get(f"{live_backend}/api/simulation/{sample_simulation_id}/frame/0")
    assert res.get("success") is True
    data = res["data"]
    assert "actions" in data
    assert "action_counts" in data
    assert data["round_num"] == 0
