"""
Template API routes — serves preset simulation templates
"""

import os
import json
from flask import jsonify, request

from . import templates_bp
from ..utils.logger import get_logger
from ..utils.i18n import get_locale, apply_i18n, t as _t
from ..services.oracle_seed import resolve_oracle_tools

logger = get_logger('miroshark.api.templates')

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'preset_templates')


@templates_bp.route('/capabilities', methods=['GET'])
def get_template_capabilities():
    """Expose backend feature flags that control template behaviour.

    Lets the frontend gray out toggles (e.g. "Live oracle data") when the
    corresponding server-side env flag is off — cleaner than surprising the
    user with a silent no-op.
    """
    return jsonify({
        "success": True,
        "data": {
            "oracle_seed_enabled": os.environ.get("ORACLE_SEED_ENABLED", "false").lower() == "true",
            "mcp_agent_tools_enabled": os.environ.get("MCP_AGENT_TOOLS_ENABLED", "false").lower() == "true",
        },
    })


def _load_templates():
    """Load all template JSON files from the templates directory."""
    templates = []
    if not os.path.isdir(TEMPLATES_DIR):
        return templates

    for filename in sorted(os.listdir(TEMPLATES_DIR)):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(TEMPLATES_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                template = json.load(f)
            templates.append(template)
        except Exception as e:
            logger.warning(f"Failed to load template {filename}: {e}")

    return templates


@templates_bp.route('/list', methods=['GET'])
def list_templates():
    """
    List all available simulation templates.

    Returns a summary of each template (without the full seed_document)
    so the frontend can render a gallery.
    """
    try:
        templates = _load_templates()
        locale = get_locale(request)

        summaries = []
        for tpl in templates:
            localized = apply_i18n(tpl, locale)
            branches = localized.get("counterfactual_branches", []) or []
            oracle_tools = localized.get("oracle_tools", []) or []
            summaries.append({
                "id": localized["id"],
                "name": localized["name"],
                "category": localized.get("category", ""),
                "description": localized.get("description", ""),
                "icon": localized.get("icon", ""),
                "difficulty": localized.get("difficulty", "medium"),
                "estimated_agents": localized.get("estimated_agents", 0),
                "estimated_rounds": localized.get("estimated_rounds", 0),
                "platforms": localized.get("platforms", []),
                "tags": localized.get("tags", []),
                "has_counterfactuals": len(branches) > 0,
                "counterfactual_count": len(branches),
                "has_oracle_tools": len(oracle_tools) > 0,
                "oracle_tool_count": len(oracle_tools),
            })

        return jsonify({
            "success": True,
            "data": summaries,
            "count": len(summaries)
        })

    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@templates_bp.route('/<template_id>', methods=['GET'])
def get_template(template_id: str):
    """
    Get a single template by ID, including the full seed_document and
    simulation_requirement for use in the creation flow.
    """
    try:
        locale = get_locale(request)
        filepath = os.path.realpath(os.path.join(TEMPLATES_DIR, f"{template_id}.json"))
        if not filepath.startswith(os.path.realpath(TEMPLATES_DIR)):
            return jsonify({
                "success": False,
                "error": _t("Invalid template ID", "无效的模板 ID", locale)
            }), 400
        if not os.path.exists(filepath):
            return jsonify({
                "success": False,
                "error": _t(f"Template not found: {template_id}", f"未找到模板:{template_id}", locale)
            }), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            template = json.load(f)

        # Opt-in oracle enrichment: ?enrich=true causes declared oracle_tools
        # to be resolved against the FeedOracle MCP endpoint and appended to
        # seed_document. Silent no-op if disabled or any call fails.
        if (request.args.get('enrich', '').lower() == 'true'):
            try:
                block = resolve_oracle_tools(template)
                if block:
                    template = dict(template)
                    template['seed_document'] = (template.get('seed_document') or '') + '\n\n' + block
                    template['oracle_enriched'] = True
            except Exception as exc:
                logger.warning(f"oracle enrichment failed for {template_id}: {exc}")

        template = apply_i18n(template, locale)

        return jsonify({
            "success": True,
            "data": template
        })

    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
