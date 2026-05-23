"""
Country config API — exposes the pluggable demographic packs under
backend/app/countries/ so the SPA can render a country picker on the
New Sim form. Read-only; safe to call without auth.
"""

from flask import jsonify, request

from . import countries_bp
from ..config import Config
from ..services import country_registry, demographic_sampler
from ..utils.logger import get_logger

logger = get_logger('miroshark.api.countries')


@countries_bp.route('', methods=['GET'])
def list_countries():
    """List available demographic country packs.

    Returns a public-safe summary: code, display name, flag, geography
    field+label, geography option count, max/default agent counts. Dataset
    repo ids and local paths are intentionally omitted.
    """
    return jsonify({
        "success": True,
        "data": {
            "active_country": Config.DEMOGRAPHICS_COUNTRY or None,
            "countries": country_registry.list_summaries(),
        }
    })


@countries_bp.route('/<code>', methods=['GET'])
def get_country(code: str):
    """Return the full filter schema for one country — geography values,
    groups, filter fields, agent caps. Used by the cohort selector UI."""
    cfg = country_registry.get(code)
    if cfg is None:
        return jsonify({"success": False, "error": f"Unknown country: {code}"}), 404

    geo = cfg.get('geography') or {}
    return jsonify({
        "success": True,
        "data": {
            "code": cfg.get('code'),
            "name": cfg.get('name'),
            "flag_emoji": cfg.get('flag_emoji', ''),
            "available": bool(cfg.get('available', True)),
            "geography": {
                "field": geo.get('field'),
                "label": geo.get('label'),
                "values": geo.get('values') or [],
                "groups": geo.get('groups') or {},
            },
            "filter_fields": cfg.get('filter_fields') or [],
            "max_agents": cfg.get('max_agents'),
            "default_agents": cfg.get('default_agents'),
        }
    })


@countries_bp.route('/<code>/filter-schema', methods=['GET'])
def get_filter_schema(code: str):
    """Return parquet-introspected filter options for the cohort selector.

    Triggers a one-time download of the country's Nemotron snapshot if not
    yet cached, then runs MIN/MAX for `range` fields and DISTINCT for
    categorical fields. Returns `{schema: []}` (with a `degraded: true` flag)
    when duckdb / huggingface_hub aren't installed or the dataset can't be
    reached — the SPA should treat it as "render whatever static hints the
    country pack ships".
    """
    cfg = country_registry.get(code)
    if cfg is None:
        return jsonify({"success": False, "error": f"Unknown country: {code}"}), 404

    try:
        max_distinct = int(request.args.get('max_distinct', '250'))
    except (TypeError, ValueError):
        max_distinct = 250
    max_distinct = max(1, min(2000, max_distinct))

    schema = demographic_sampler.infer_filter_schema(code, max_distinct=max_distinct)
    return jsonify({
        "success": True,
        "data": {
            "code": code,
            "schema": schema,
            "degraded": not schema,
        }
    })
