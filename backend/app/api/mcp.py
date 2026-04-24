"""
MCP API — surface the bundled `mcp_server.py` so the frontend can show users
exactly how to wire MiroShark into Claude Desktop, Cursor, Windsurf, Continue,
or any other MCP-aware client.

GET /api/mcp/status — returns:
  - the MiroShark MCP tool catalog (parsed from `mcp_server.py`)
  - resolved absolute paths for the python interpreter and `mcp_server.py`
    on this host (so the JSON snippets the UI shows are copy-paste ready
    for the user's own machine)
  - pre-rendered config blocks for each supported client
  - a graph database health probe (connection + graph count) so the UI can
    tell the user whether Neo4j is up and whether anything is in it yet

The MCP server itself runs over stdio — this endpoint never spawns or talks
to it. We only describe how to launch it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app, jsonify

from . import mcp_bp
from ..config import Config
from ..utils.logger import get_logger


logger = get_logger('miroshark.api.mcp')


# ──────────────────────────────────────────────────────────────────────────
# Tool catalog — kept in sync with `backend/mcp_server.py`. The backend ships
# both files, so a stale catalog here becomes a CI failure surfaced by the
# unit tests below (test_unit_mcp_api.py).
# ──────────────────────────────────────────────────────────────────────────

_TOOLS: List[Dict[str, str]] = [
    {
        'name': 'list_graphs',
        'description': (
            'Survey every knowledge graph in this MiroShark instance with '
            'entity and edge counts. Use this first to discover graph_ids.'
        ),
    },
    {
        'name': 'search_graph',
        'description': (
            'Hybrid retrieval over a graph: vector + BM25 + graph-traversal '
            'fused and reranked with a cross-encoder. Supports time-travel '
            '(as_of) and epistemic filtering (kinds=fact|belief|observation).'
        ),
    },
    {
        'name': 'browse_clusters',
        'description': (
            'Zoom-out over a graph: return LLM-summarized community clusters. '
            'Auto-builds clusters on first call if none exist.'
        ),
    },
    {
        'name': 'search_communities',
        'description': 'Semantic search over cluster summaries only (faster than search_graph).',
    },
    {
        'name': 'get_community',
        'description': 'Expand one cluster — returns title, summary, and member entities.',
    },
    {
        'name': 'list_reports',
        'description': 'List prior reports generated for a graph (most recent first).',
    },
    {
        'name': 'list_report_sections',
        'description': 'List the sections of a report in order.',
    },
    {
        'name': 'get_reasoning_trace',
        'description': (
            "Return the report-agent's full decision chain for one report "
            'section: thoughts, tool calls, observations, conclusion.'
        ),
    },
]


# ──────────────────────────────────────────────────────────────────────────
# Path resolution — these are the values that get stamped into the config
# snippets shown to the user.
# ──────────────────────────────────────────────────────────────────────────

def _resolve_paths() -> Dict[str, str]:
    """Locate the bundled mcp_server.py and the interpreter that should run it.

    The user copies these values into their MCP client config, so they must
    point at the *server's* on-disk install — that's the same machine where
    they'll be running both the backend and (eventually) the MCP server.
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent
    mcp_script = backend_dir / 'mcp_server.py'
    return {
        'backend_dir': str(backend_dir),
        'mcp_script': str(mcp_script),
        'mcp_script_exists': mcp_script.is_file(),
        'python_executable': sys.executable,
    }


def _build_config_snippets(paths: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Pre-render copy-pasteable config blocks for each supported MCP client.

    Each entry has:
      - label:    human-readable client name
      - file:     where the config typically lives on disk
      - config:   the JSON snippet (returned as a dict so the frontend can
                  pretty-print it however it wants)
      - notes:    optional one-liner shown beneath the snippet
    """
    py = paths['python_executable']
    script = paths['mcp_script']
    backend = paths['backend_dir']

    # The server ships as a uv-managed project; if the operator launched the
    # backend with uv we surface the cleaner `uv run` command which doesn't
    # depend on the .venv path being stable across hosts.
    uv_command = {
        'command': 'uv',
        'args': ['run', '--directory', backend, 'python', 'mcp_server.py'],
    }

    direct_command = {
        'command': py,
        'args': [script],
    }

    # Claude Desktop / Continue / generic-MCP all use the `mcpServers` shape.
    claude_desktop = {
        'mcpServers': {
            'miroshark': uv_command,
        }
    }

    # Cursor's `.cursor/mcp.json` is the same shape as Claude Desktop.
    cursor = {
        'mcpServers': {
            'miroshark': uv_command,
        }
    }

    # Windsurf's `~/.codeium/windsurf/mcp_config.json` also uses `mcpServers`.
    windsurf = {
        'mcpServers': {
            'miroshark': uv_command,
        }
    }

    # Continue prefers a flat list inside `experimental.modelContextProtocolServers`.
    continue_dev = {
        'experimental': {
            'modelContextProtocolServers': [
                {
                    'transport': {
                        'type': 'stdio',
                        **uv_command,
                    }
                }
            ]
        }
    }

    return {
        'claude_desktop': {
            'label': 'Claude Desktop',
            'file': '~/Library/Application Support/Claude/claude_desktop_config.json (macOS) · %APPDATA%\\Claude\\claude_desktop_config.json (Windows)',
            'config': claude_desktop,
            'notes': 'Open Claude Desktop → Settings → Developer → Edit Config. Restart Claude Desktop after saving.',
        },
        'cursor': {
            'label': 'Cursor',
            'file': '.cursor/mcp.json (in your workspace) or ~/.cursor/mcp.json (global)',
            'config': cursor,
            'notes': 'Reload the Cursor window after editing. The miroshark tools appear in the @ menu.',
        },
        'windsurf': {
            'label': 'Windsurf',
            'file': '~/.codeium/windsurf/mcp_config.json',
            'config': windsurf,
            'notes': 'Open Windsurf → Cascade → MCP Servers → Refresh after saving.',
        },
        'continue': {
            'label': 'Continue (VS Code / JetBrains)',
            'file': '~/.continue/config.json',
            'config': continue_dev,
            'notes': 'Continue ≥ 0.9.x. Reload your editor after saving.',
        },
        'fallback_direct': {
            'label': 'No uv? Use the interpreter path directly',
            'file': 'Replace the uv block above with this if `uv` is not on PATH.',
            'config': {'mcpServers': {'miroshark': direct_command}},
            'notes': f'Uses the same Python interpreter currently serving the backend ({py}).',
        },
    }


# ──────────────────────────────────────────────────────────────────────────
# Neo4j health probe — non-fatal. The endpoint must always return 200 so the
# frontend can render guidance even when Neo4j is down.
# ──────────────────────────────────────────────────────────────────────────

def _probe_neo4j() -> Dict[str, Any]:
    """Best-effort liveness + graph count. Never raises."""
    storage = current_app.extensions.get('neo4j_storage') if current_app else None
    result: Dict[str, Any] = {
        'connected': False,
        'uri': Config.NEO4J_URI,
        'user': Config.NEO4J_USER,
        'graph_count': None,
        'entity_count': None,
        'error': None,
    }

    if storage is None:
        result['error'] = 'Neo4jStorage failed to initialize at app startup. Check NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD.'
        return result

    try:
        with storage._driver.session() as sess:
            sess.run('RETURN 1').single()
            result['connected'] = True

            # Graph count — distinct graph_ids that own at least one Entity.
            row = sess.run(
                """
                MATCH (n:Entity)
                WITH count(DISTINCT n.graph_id) AS graphs, count(n) AS entities
                RETURN graphs, entities
                """
            ).single()
            if row is not None:
                result['graph_count'] = int(row['graphs'])
                result['entity_count'] = int(row['entities'])
            else:
                result['graph_count'] = 0
                result['entity_count'] = 0
    except Exception as e:  # noqa: BLE001 — surface every Neo4j failure mode
        logger.warning('MCP status: Neo4j probe failed: %s', e)
        result['error'] = str(e)

    return result


# ──────────────────────────────────────────────────────────────────────────
# Pure helpers — exported for unit testing without a Flask app context.
# ──────────────────────────────────────────────────────────────────────────

def build_status_payload(
    neo4j_probe: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the GET /api/mcp/status response body.

    Splitting this from the request handler keeps the unit tests Flask-free.
    """
    paths = _resolve_paths()
    snippets = _build_config_snippets(paths)
    return {
        'enabled': True,
        'transport': 'stdio',
        'paths': paths,
        'tools': _TOOLS,
        'tool_count': len(_TOOLS),
        'clients': snippets,
        'neo4j': neo4j_probe if neo4j_probe is not None else {
            'connected': False,
            'uri': Config.NEO4J_URI,
            'user': Config.NEO4J_USER,
            'graph_count': None,
            'entity_count': None,
            'error': 'Neo4j probe skipped.',
        },
        'docs_url': 'https://github.com/aaronjmars/MiroShark/blob/main/docs/MCP.md',
    }


@mcp_bp.route('/status', methods=['GET'])
def mcp_status():
    """Return the MiroShark MCP server catalog + per-client config snippets."""
    payload = build_status_payload(neo4j_probe=_probe_neo4j())
    return jsonify({'success': True, 'data': payload})
