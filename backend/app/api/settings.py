"""
Settings API — runtime LLM configuration management.

GET  /api/settings        — return current active config (masked)
POST /api/settings        — update config at runtime (no restart required)
POST /api/settings/test-llm — make a minimal test call and return latency
"""

import time
from flask import request, jsonify

from . import settings_bp
from ..config import Config
from ..services import webhook_service  # noqa: F401 — kept for namespace-style access
from ..services.webhook_service import (
    mask_url as mask_webhook_url,
    send_test_webhook,
    validate_url as validate_webhook_url,
)
from ..utils.logger import get_logger

logger = get_logger('miroshark.api.settings')


def _mask_key(key: str) -> str:
    """Return only the last 4 characters of an API key."""
    if not key:
        return ''
    return '****' + key[-4:] if len(key) > 4 else '****'


# Preset blueprints mirror the .env.example Cloud / Local blocks.
# The `key_slots` list names the fields the preset's API key should be
# copied into when the caller supplies `preset_api_key`.
_PRESETS = {
    'cheap': {
        'label': 'Cloud — ~$1/run (Mimo V2 Flash + Grok-4.1 Fast)',
        'fields': {
            'LLM_PROVIDER': 'openai',
            'LLM_BASE_URL': 'https://openrouter.ai/api/v1',
            'LLM_MODEL_NAME': 'xiaomi/mimo-v2-flash',
            'SMART_PROVIDER': 'openai',
            'SMART_BASE_URL': 'https://openrouter.ai/api/v1',
            'SMART_MODEL_NAME': 'x-ai/grok-4.1-fast',
            'NER_BASE_URL': 'https://openrouter.ai/api/v1',
            'NER_MODEL_NAME': 'x-ai/grok-4.1-fast',
            'WONDERWALL_MODEL_NAME': 'xiaomi/mimo-v2-flash',
            'EMBEDDING_PROVIDER': 'openai',
            'EMBEDDING_BASE_URL': 'https://openrouter.ai/api',
            'EMBEDDING_MODEL': 'openai/text-embedding-3-large',
            'EMBEDDING_DIMENSIONS': 768,
            'WEB_SEARCH_MODEL': 'x-ai/grok-4.1-fast:online',
        },
        'key_slots': ['LLM_API_KEY', 'SMART_API_KEY', 'NER_API_KEY', 'EMBEDDING_API_KEY'],
    },
    'local': {
        'label': 'Local — Ollama (free, self-hosted)',
        'fields': {
            'LLM_PROVIDER': 'openai',
            'LLM_BASE_URL': 'http://localhost:11434/v1',
            'LLM_MODEL_NAME': 'qwen2.5:32b',
            'LLM_API_KEY': 'ollama',
            'SMART_PROVIDER': '',
            'SMART_BASE_URL': '',
            'SMART_MODEL_NAME': '',
            'SMART_API_KEY': '',
            'NER_BASE_URL': '',
            'NER_MODEL_NAME': '',
            'NER_API_KEY': '',
            'WONDERWALL_MODEL_NAME': '',
            'EMBEDDING_PROVIDER': 'ollama',
            'EMBEDDING_BASE_URL': 'http://localhost:11434',
            'EMBEDDING_MODEL': 'nomic-embed-text',
            'EMBEDDING_API_KEY': '',
            'EMBEDDING_DIMENSIONS': 768,
            'WEB_SEARCH_MODEL': '',
        },
        'key_slots': [],
    },
}


def _current_snapshot() -> dict:
    """Build a summary of every slot the Settings UI cares about."""
    return {
        'llm': {
            'provider': Config.LLM_PROVIDER,
            'base_url': Config.LLM_BASE_URL,
            'model_name': Config.LLM_MODEL_NAME,
            'api_key_masked': _mask_key(Config.LLM_API_KEY or ''),
            'has_api_key': bool(Config.LLM_API_KEY),
        },
        'smart': {
            'provider': Config.SMART_PROVIDER,
            'base_url': Config.SMART_BASE_URL,
            'model_name': Config.SMART_MODEL_NAME,
            'api_key_masked': _mask_key(Config.SMART_API_KEY or ''),
            'has_api_key': bool(Config.SMART_API_KEY),
        },
        'ner': {
            'base_url': Config.NER_BASE_URL,
            'model_name': Config.NER_MODEL_NAME,
            'api_key_masked': _mask_key(Config.NER_API_KEY or ''),
            'has_api_key': bool(Config.NER_API_KEY),
        },
        'wonderwall': {
            'model_name': Config.WONDERWALL_MODEL_NAME,
            'base_url': Config.WONDERWALL_BASE_URL,
            'api_key_masked': _mask_key(Config.WONDERWALL_API_KEY or ''),
            'has_api_key': bool(Config.WONDERWALL_API_KEY),
        },
        'embedding': {
            'provider': Config.EMBEDDING_PROVIDER,
            'base_url': Config.EMBEDDING_BASE_URL,
            'model_name': Config.EMBEDDING_MODEL,
            'dimensions': Config.EMBEDDING_DIMENSIONS,
            'api_key_masked': _mask_key(Config.EMBEDDING_API_KEY or ''),
            'has_api_key': bool(Config.EMBEDDING_API_KEY),
        },
        'web_search_model': Config.WEB_SEARCH_MODEL,
        'neo4j': {
            'uri': Config.NEO4J_URI,
            'user': Config.NEO4J_USER,
        },
        'integrations': {
            'webhook': {
                'configured': bool((Config.WEBHOOK_URL or '').strip()),
                'url_masked': mask_webhook_url(Config.WEBHOOK_URL or ''),
                'public_base_url': Config.PUBLIC_BASE_URL or '',
            },
        },
        'available_presets': [
            {'id': k, 'label': v['label']} for k, v in _PRESETS.items()
        ],
    }


@settings_bp.route('', methods=['GET'])
def get_settings():
    """Return current active config across every slot (API keys masked)."""
    return jsonify({'success': True, 'data': _current_snapshot()})


def _apply_preset(preset_id: str, preset_api_key: str) -> None:
    """Mutate Config in-place to match the named preset."""
    preset = _PRESETS[preset_id]
    for attr, value in preset['fields'].items():
        setattr(Config, attr, value)
    if preset_api_key:
        for slot in preset['key_slots']:
            setattr(Config, slot, preset_api_key)


@settings_bp.route('', methods=['POST'])
def update_settings():
    """
    Update configuration at runtime. All fields optional.

    Body fields:
      preset: "cheap" | "local"                              — apply a full preset
      preset_api_key: str                                    — key filled into every preset slot
      llm: { provider, base_url, model_name, api_key }
      smart: { provider, base_url, model_name, api_key }
      ner:   { base_url, model_name, api_key }
      wonderwall: { base_url, model_name, api_key }
      embedding: { provider, base_url, model_name, api_key, dimensions }
      web_search_model: str
      neo4j: { uri, user, password }
    """
    body = request.get_json(silent=True) or {}

    preset_id = body.get('preset')
    if preset_id:
        if preset_id not in _PRESETS:
            return jsonify({
                'success': False,
                'error': f"Unknown preset '{preset_id}'. Valid: {list(_PRESETS)}"
            }), 400
        _apply_preset(preset_id, body.get('preset_api_key', ''))

    llm = body.get('llm') or {}
    if llm.get('provider'): Config.LLM_PROVIDER = llm['provider']
    if llm.get('base_url') is not None: Config.LLM_BASE_URL = llm['base_url']
    if llm.get('model_name') is not None: Config.LLM_MODEL_NAME = llm['model_name']
    if llm.get('api_key'): Config.LLM_API_KEY = llm['api_key']

    smart = body.get('smart') or {}
    if smart.get('provider') is not None: Config.SMART_PROVIDER = smart['provider']
    if smart.get('base_url') is not None: Config.SMART_BASE_URL = smart['base_url']
    if smart.get('model_name') is not None: Config.SMART_MODEL_NAME = smart['model_name']
    if smart.get('api_key'): Config.SMART_API_KEY = smart['api_key']

    ner = body.get('ner') or {}
    if ner.get('base_url') is not None: Config.NER_BASE_URL = ner['base_url']
    if ner.get('model_name') is not None: Config.NER_MODEL_NAME = ner['model_name']
    if ner.get('api_key'): Config.NER_API_KEY = ner['api_key']

    wonderwall = body.get('wonderwall') or {}
    if wonderwall.get('model_name') is not None:
        Config.WONDERWALL_MODEL_NAME = wonderwall['model_name']
    if wonderwall.get('base_url') is not None:
        Config.WONDERWALL_BASE_URL = wonderwall['base_url']
    if wonderwall.get('api_key'):
        Config.WONDERWALL_API_KEY = wonderwall['api_key']

    embedding = body.get('embedding') or {}
    if embedding.get('provider') is not None: Config.EMBEDDING_PROVIDER = embedding['provider']
    if embedding.get('base_url') is not None: Config.EMBEDDING_BASE_URL = embedding['base_url']
    if embedding.get('model_name') is not None: Config.EMBEDDING_MODEL = embedding['model_name']
    if embedding.get('api_key'): Config.EMBEDDING_API_KEY = embedding['api_key']
    if embedding.get('dimensions') is not None:
        try:
            Config.EMBEDDING_DIMENSIONS = int(embedding['dimensions'])
        except (TypeError, ValueError):
            pass

    if 'web_search_model' in body and body['web_search_model'] is not None:
        Config.WEB_SEARCH_MODEL = body['web_search_model']

    neo4j = body.get('neo4j') or {}
    if neo4j.get('uri'): Config.NEO4J_URI = neo4j['uri']
    if neo4j.get('user'): Config.NEO4J_USER = neo4j['user']
    if neo4j.get('password'): Config.NEO4J_PASSWORD = neo4j['password']

    integrations = body.get('integrations') or {}
    webhook = integrations.get('webhook') or {}
    if 'url' in webhook and webhook['url'] is not None:
        new_url = (webhook['url'] or '').strip()
        err = validate_webhook_url(new_url)
        if err:
            return jsonify({'success': False, 'error': err}), 400
        Config.WEBHOOK_URL = new_url
    if 'public_base_url' in webhook and webhook['public_base_url'] is not None:
        new_base = (webhook['public_base_url'] or '').strip().rstrip('/')
        if new_base:
            lowered = new_base.lower()
            if not (lowered.startswith('http://') or lowered.startswith('https://')):
                return jsonify({
                    'success': False,
                    'error': 'public_base_url must start with http:// or https://',
                }), 400
        Config.PUBLIC_BASE_URL = new_base

    logger.info(
        "Settings updated: preset=%s provider=%s model=%s base_url=%s",
        preset_id or '—', Config.LLM_PROVIDER, Config.LLM_MODEL_NAME, Config.LLM_BASE_URL,
    )

    return jsonify({'success': True, 'data': _current_snapshot()})


@settings_bp.route('/test-llm', methods=['POST'])
def test_llm():
    """
    Make a minimal test call to the current LLM config.
    Returns { success, model, latency_ms, error }.
    """
    try:
        from ..utils.llm_client import LLMClient

        if Config.LLM_PROVIDER == 'claude-code':
            return jsonify({
                'success': True,
                'model': 'claude-code (local CLI)',
                'latency_ms': 0,
                'note': 'claude-code provider does not support connection testing'
            })

        client = LLMClient()
        start = time.time()
        response = client.chat(
            messages=[{'role': 'user', 'content': 'Reply with only the word OK.'}],
            temperature=0,
            max_tokens=8,
        )
        latency_ms = round((time.time() - start) * 1000)

        return jsonify({
            'success': True,
            'model': client.model,
            'latency_ms': latency_ms,
            'response': response.strip()[:100],
        })

    except Exception as e:
        logger.warning("LLM test failed: %s", e)
        return jsonify({
            'success': False,
            'error': str(e),
        }), 200  # Return 200 so the frontend can read the error body


@settings_bp.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Fire a sample ``simulation.test`` event at the user-supplied
    webhook URL and return delivery details.

    Body:
        {"url": "https://hooks.slack.com/...", "public_base_url": "..."}

    When ``url`` is omitted the currently saved ``Config.WEBHOOK_URL`` is
    tested instead — convenient for verifying that a previously saved
    endpoint is still reachable. Always returns HTTP 200 so the frontend
    can render the success / failure body uniformly.
    """
    body = request.get_json(silent=True) or {}
    url = (body.get('url') or '').strip() or (Config.WEBHOOK_URL or '').strip()
    base_url = (body.get('public_base_url') or '').strip() or (Config.PUBLIC_BASE_URL or '').strip() or None

    if not url:
        return jsonify({
            'success': False,
            'error': 'No webhook URL configured — provide one in the request or save it in Settings first.',
        }), 200

    err = validate_webhook_url(url)
    if err:
        return jsonify({'success': False, 'error': err}), 200

    try:
        result = send_test_webhook(url, base_url=base_url)
    except Exception as exc:
        logger.warning("Webhook test failed: %s", exc)
        return jsonify({
            'success': False,
            'error': str(exc),
        }), 200

    return jsonify({
        'success': bool(result.get('ok')),
        'message': result.get('message', ''),
        'latency_ms': result.get('latency_ms'),
        'url_masked': mask_webhook_url(url),
    }), 200
