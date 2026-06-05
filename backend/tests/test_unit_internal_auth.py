"""
Unit tests for internal API authentication guard
"""
import os
import pytest
from app import create_app
from app.config import Config

_PLATFORM_ENV_VARS = (
    'RAILWAY_ENVIRONMENT',
    'RAILWAY_PROJECT_ID',
    'RAILWAY_SERVICE_ID',
    'K_SERVICE',
)


@pytest.fixture(autouse=True)
def _restore_auth_env():
    """Snapshot and restore the global auth state these tests mutate.

    The guard reads MIROSHARK_INTERNAL_KEY, the deploy-platform env vars, and
    Config.DEBUG from process-global state, so without this fixture a test that
    sets one of them would leak into unrelated tests depending on run order.
    """
    saved_key = os.environ.get('MIROSHARK_INTERNAL_KEY')
    saved_platform = {var: os.environ.get(var) for var in _PLATFORM_ENV_VARS}
    saved_debug = Config.DEBUG
    try:
        yield
    finally:
        for var, val in {'MIROSHARK_INTERNAL_KEY': saved_key, **saved_platform}.items():
            if val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = val
        Config.DEBUG = saved_debug


def test_health_endpoint_without_auth():
    """Test that /health endpoint is accessible without authentication"""
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json['status'] == 'ok'
        assert response.json['service'] == 'MiroShark Backend'


def test_protected_api_without_internal_key():
    """Test that protected API routes return 401 without internal key"""
    # Set internal key to enable auth guard
    os.environ['MIROSHARK_INTERNAL_KEY'] = 'test-secret-key'
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Test a protected API route (graph ontology generate)
        response = client.post('/api/graph/ontology/generate')
        assert response.status_code == 401


def test_protected_api_with_correct_internal_key():
    """Test that protected API routes succeed with correct internal key"""
    # Set internal key to enable auth guard
    os.environ['MIROSHARK_INTERNAL_KEY'] = 'test-secret-key'
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Test a protected API route with correct header
        response = client.post(
            '/api/graph/ontology/generate',
            headers={'x-miroshark-internal-key': 'test-secret-key'}
        )
        # Should return 400 (bad request) or 422 (validation error) rather than 401
        # because the request is missing required fields, but auth passed
        assert response.status_code != 401


def test_protected_api_with_wrong_internal_key():
    """Test that protected API routes return 401 with wrong internal key"""
    # Set internal key to enable auth guard
    os.environ['MIROSHARK_INTERNAL_KEY'] = 'test-secret-key'
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Test a protected API route with wrong header
        response = client.post(
            '/api/graph/ontology/generate',
            headers={'x-miroshark-internal-key': 'wrong-key'}
        )
        assert response.status_code == 401


def test_protected_api_without_internal_key_env():
    """Test that protected API routes fail-closed in production when internal key is not set"""
    # Ensure internal key is not set
    if 'MIROSHARK_INTERNAL_KEY' in os.environ:
        del os.environ['MIROSHARK_INTERNAL_KEY']
    
    # Mock Config.DEBUG to simulate production/staging mode
    original_debug = Config.DEBUG
    Config.DEBUG = False
    
    try:
        app = create_app()
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            # Test a protected API route when key is not configured
            # In production mode without key, should return 503
            response = client.post('/api/graph/ontology/generate')
            # Should return 503 (service unavailable) when key not configured in production
            assert response.status_code == 503
    finally:
        Config.DEBUG = original_debug


def test_protected_api_without_internal_key_env_debug():
    """Test that protected API routes fail-open in debug mode when internal key is not set"""
    # Ensure internal key is not set
    if 'MIROSHARK_INTERNAL_KEY' in os.environ:
        del os.environ['MIROSHARK_INTERNAL_KEY']
    # Ensure no deploy-platform signal is present — fail-open is only for local dev.
    for var in _PLATFORM_ENV_VARS:
        os.environ.pop(var, None)

    # Simulate development mode
    Config.DEBUG = True

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Test a protected API route when key is not configured in debug mode
        # In debug mode without key, auth guard is disabled (fail-open for development)
        # Request will fail with 400 due to missing required fields, not 401/503
        response = client.post('/api/graph/ontology/generate')
        # Should return 400 (bad request) because auth guard is disabled
        assert response.status_code == 400


def test_protected_api_fail_closed_on_deploy_platform_without_key():
    """Without a key, a Railway/Cloud Run deploy must fail closed even if DEBUG is True.

    Regression test: FLASK_DEBUG defaults to "True", so a deploy that forgets to
    set both the key and FLASK_DEBUG=false must not serve the protected API openly.
    """
    os.environ.pop('MIROSHARK_INTERNAL_KEY', None)
    os.environ['RAILWAY_ENVIRONMENT'] = 'staging'
    # DEBUG left True on purpose, to prove the platform signal overrides it.
    Config.DEBUG = True

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        response = client.post('/api/graph/ontology/generate')
        assert response.status_code == 503


def test_openapi_docs_without_internal_key():
    """Test that OpenAPI docs are accessible without authentication (if configured)"""
    # Set internal key to enable auth guard
    os.environ['MIROSHARK_INTERNAL_KEY'] = 'test-secret-key'
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Test OpenAPI docs endpoint
        response = client.get('/api/openapi.json')
        # May be 200 (if exempt) or 401 (if protected)
        # This test documents current behavior
        assert response.status_code in [200, 401]


def test_status_probe_without_internal_key():
    """The platform status probe MUST stay reachable without the internal
    key even when one is configured — it exists to be polled by external,
    keyless status monitors. Guards against a future change re-gating it.
    Unlike its siblings (/api/stats, /api/surfaces.json), it is the one
    deliberately-public data endpoint; total_sims is filtered to
    public+completed in platform_status so this leaks no private volume."""
    # Set internal key to enable the auth guard for every other /api/* route.
    os.environ['MIROSHARK_INTERNAL_KEY'] = 'test-secret-key'

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        response = client.get('/api/status.json')
        # Must NOT be gated (401) or fail-closed (503) — the probe is exempt.
        assert response.status_code == 200, response.status_code
        body = response.get_json()
        assert body['success'] is True
        assert body['data']['ok'] is True
