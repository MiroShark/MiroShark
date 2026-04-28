"""
MiroShark Backend - Flask application factory
"""

import os
import warnings

# Suppress multiprocessing resource_tracker warnings (from third-party libraries like transformers)
# Must be set before all other imports
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


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
    
    @app.after_request
    def log_response(response):
        logger = get_logger('miroshark.request')
        logger.debug(f"Response: {response.status_code}")
        return response
    
    # Register blueprints
    from .api import graph_bp, simulation_bp, report_bp, decision_lab_bp, seed_chat_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(decision_lab_bp, url_prefix='/api/decision-lab')
    app.register_blueprint(seed_chat_bp, url_prefix='/api/seed-chat')
    
    # Health check — verifies Neo4j and Ollama connectivity
    @app.route('/health')
    def health():
        import requests as http_req
        checks = {}
        try:
            storage = app.extensions.get("neo4j_storage")
            if storage:
                storage._driver.verify_connectivity()
                checks['neo4j'] = 'ok'
            else:
                checks['neo4j'] = 'not configured'
        except Exception as exc:
            checks['neo4j'] = f'error: {str(exc)[:80]}'
        try:
            llm_url = Config.LLM_BASE_URL.replace('/v1', '')
            resp = http_req.get(f'{llm_url}/api/version', timeout=3)
            checks['ollama'] = 'ok' if resp.ok else f'error: {resp.status_code}'
        except Exception as exc:
            checks['ollama'] = f'error: {str(exc)[:80]}'
        all_ok = all(v == 'ok' for v in checks.values())
        status_code = 200 if all_ok else 503
        return {'status': 'healthy' if all_ok else 'degraded', 'checks': checks}, status_code
    
    if should_log_startup:
        logger.info("MiroShark Backend startup complete")
    
    return app

