"""
MiroShark Backend - Flask application factory
"""

import hmac
import os
import warnings

# Suppress multiprocessing resource_tracker warnings (from third-party libraries like transformers)
# Must be set before all other imports
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS
from flask_compress import Compress

from .config import Config
from .utils.logger import setup_logger, get_logger


# Environment variables injected by common managed deploy platforms. Their
# presence means we are NOT in local development, so the internal-key guard
# must fail closed even if FLASK_DEBUG was left at its default of "True".
_DEPLOY_PLATFORM_ENV_VARS = (
    'RAILWAY_ENVIRONMENT',
    'RAILWAY_PROJECT_ID',
    'RAILWAY_SERVICE_ID',
    'K_SERVICE',  # Google Cloud Run
)


def _is_deployed_environment() -> bool:
    """True when running on a known managed deploy platform (Railway / Cloud Run)."""
    return any(os.environ.get(var) for var in _DEPLOY_PLATFORM_ENV_VARS)


def create_app(config_class=Config):
    """Flask application factory function"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Set JSON encoding: ensure non-ASCII characters are displayed directly (instead of \uXXXX format)
    # Flask >= 2.3 uses app.json.ensure_ascii, older versions use JSON_AS_ASCII config
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Set up logging
    logger = setup_logger('miroshark')
    
    # Only print startup info in the reloader subprocess (avoid printing twice in debug mode)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroShark Backend starting...")
        logger.info("=" * 50)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Enable gzip/brotli response compression
    Compress(app)

    # --- Initialize Neo4jStorage singleton (DI via app.extensions) ---
    from .storage import Neo4jStorage
    try:
        neo4j_storage = Neo4jStorage()
        app.extensions['neo4j_storage'] = neo4j_storage
        if should_log_startup:
            logger.info("Neo4jStorage initialized (connected to %s)", Config.NEO4J_URI)
    except Exception as e:
        logger.error("Neo4jStorage initialization failed: %s", e)
        # Store None so endpoints can return 503 gracefully
        app.extensions['neo4j_storage'] = None

    # Register simulation process cleanup function (ensure all simulation processes are terminated when server shuts down)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Simulation process cleanup function registered")
    
    # Request logging middleware
    @app.before_request
    def log_request():
        logger = get_logger('miroshark.request')
        logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Request body: {request.get_json(silent=True)}")
    
    # Internal API authentication guard
    @app.before_request
    def internal_auth_guard():
        """Protect expensive API routes with internal key authentication"""
        # CORS preflight requests never carry custom headers — let Flask-CORS
        # answer them instead of returning 401 and breaking browser clients.
        if request.method == 'OPTIONS':
            return

        # Exempt health check endpoint
        if request.path == '/health':
            return

        # Exempt OpenAPI docs (optional - keeps API surface discoverable)
        if request.path in ['/api/openapi.json', '/api/openapi.yaml', '/api/docs']:
            return

        # Exempt the platform status probe. Unlike its gated siblings
        # (/api/stats, /api/surfaces.json), this endpoint exists to be polled
        # by external, keyless status monitors (Upptime, BetterUptime,
        # Statuspage.io) — requiring the internal key would defeat its purpose.
        # total_sims is filtered to public+completed in platform_status so an
        # anonymous caller can never read the volume of private/in-flight sims.
        if request.path == '/api/status.json':
            return

        # Exempt the multi-sim batch-status lookup. Same posture as
        # /api/status.json: external integrators (AntFleet, Capacitr) need
        # to poll batch runs from keyless clients, and the per-id publish
        # gate inside batch_status hides private sims behind a found:false
        # envelope so an anonymous caller can't read the volume or
        # analytics of any non-public sim.
        if request.path == '/api/simulation/batch-status':
            return

        # Only protect /api/* routes
        if not request.path.startswith('/api/'):
            return

        # Get internal key from environment
        internal_key = os.environ.get('MIROSHARK_INTERNAL_KEY')

        # If internal key is set, enforce authentication
        if internal_key:
            provided_key = request.headers.get('x-miroshark-internal-key')
            # Constant-time comparison to avoid leaking the key via timing.
            if not provided_key or not hmac.compare_digest(provided_key, internal_key):
                logger.warning(f"Unauthorized API access attempt: {request.method} {request.path}")
                return {'error': 'Unauthorized - Invalid or missing internal key'}, 401
        else:
            # Fail closed whenever we're not plainly in local development.
            # FLASK_DEBUG defaults to "True", so Config.DEBUG alone is not a safe
            # signal: on a managed deploy platform we must refuse rather than
            # serve the protected API openly.
            if _is_deployed_environment() or not Config.DEBUG:
                logger.error(f"Protected API access attempted without MIROSHARK_INTERNAL_KEY configured: {request.method} {request.path}")
                return {'error': 'Service not configured - missing internal key'}, 503
    
    @app.after_request
    def log_response(response):
        logger = get_logger('miroshark.request')
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp, templates_bp, settings_bp, observability_bp, mcp_bp, docs_bp, feed_bp, share_bp, watch_bp, sitemap_bp, notifications_bp, countries_bp, stats_bp, surfaces_bp, project_stats_bp, status_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(templates_bp, url_prefix='/api/templates')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(observability_bp, url_prefix='/api/observability')
    app.register_blueprint(mcp_bp, url_prefix='/api/mcp')
    # countries_bp serves /api/countries (+ /api/countries/<code>) — the
    # demographic-pack registry the SPA reads to render the country picker
    # on the New Sim form.
    app.register_blueprint(countries_bp, url_prefix='/api/countries')
    # docs_bp serves Swagger UI + the OpenAPI spec at /api/docs,
    # /api/openapi.yaml, /api/openapi.json (no extra sub-prefix — the spec
    # URL is the developer-facing surface so we keep it short).
    app.register_blueprint(docs_bp, url_prefix='/api')
    # feed_bp serves the public-gallery syndication feeds at
    # /api/feed.atom + /api/feed.rss — short URLs at the /api root so
    # feed auto-discovery scripts and aggregators find them without
    # digging through the /api/simulation namespace.
    app.register_blueprint(feed_bp, url_prefix='/api')
    # share_bp serves the public OG-tag landing page at /share/<sim_id>
    # (no prefix — keeps the social share URL short).
    app.register_blueprint(share_bp)
    # watch_bp serves the live spectator-watch page at /watch/<sim_id>
    # — same no-prefix policy so the URL stays a clean broadcast link.
    app.register_blueprint(watch_bp)
    # sitemap_bp serves /sitemap.xml + /robots.txt at the root —
    # crawlers expect both URLs at the deployment root, not under
    # /api/, so the blueprint is mounted with no prefix to match the
    # protocol convention.
    app.register_blueprint(sitemap_bp)
    # notifications_bp serves /api/config/notifications — kept on the
    # /api root (no extra sub-prefix) to mirror the sitemap config
    # endpoint that pairs with it on the SPA side.
    app.register_blueprint(notifications_bp)
    # stats_bp serves /api/stats (JSON aggregate) + /api/stats/badge.svg
    # (Shields.io platform badge). Mounted at /api/stats so both URLs
    # share the same prefix without leaking the implementation detail
    # to the rest of the simulation namespace.
    app.register_blueprint(stats_bp, url_prefix='/api/stats')
    # surfaces_bp serves /api/surfaces.json — the machine-readable
    # catalog of every share / platform surface this deployment
    # exposes. Mounted at /api (no sub-prefix) so the URL stays a
    # short, oEmbed-style discovery surface that an integrator can
    # query without knowing about any per-sim namespace.
    app.register_blueprint(surfaces_bp, url_prefix='/api')
    # project_stats_bp serves /api/project/<project_id>/stats — the
    # per-project sibling of /api/stats. Pinned at /api/project so the
    # URL stays the canonical place a per-project surface lives even
    # as the platform-stats namespace grows.
    app.register_blueprint(project_stats_bp, url_prefix='/api/project')
    # status_bp serves /api/status.json — the platform health probe
    # that external status monitors (Upptime, BetterUptime, Statuspage)
    # consume. Mounted at /api (no sub-prefix) so the URL stays the
    # short, well-known probe path a status-page template can drop in.
    app.register_blueprint(status_bp, url_prefix='/api')
    
    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroShark Backend'}
    
    if should_log_startup:
        logger.info("MiroShark Backend startup complete")
    
    return app

