"""Infographic planning/rendering API routes."""

import os
from pathlib import Path

from flask import jsonify, request, send_from_directory

from . import seed_chat_bp
from .seed_chat_common import (
    current_infographics_dir,
    _find_slide,
    _get_or_create_infographic_plan,
    _slide_key,
    current_store,
)
from ..services.infographic_planner import plan_gas_tax_public_explainer, plan_infographics
from ..services.nano_banana_renderer import (
    NanoBananaConfigError,
    NanoBananaRenderError,
    render_infographic_slide,
)
from ..services.openai_image_renderer import (
    OpenAIImageConfigError,
    OpenAIImageRenderError,
    render_openai_infographic_slide,
    render_openai_infographic_slide_edit,
)
from ..services.render_accounting import (
    accounting_summary,
    assert_render_allowed,
    RenderLimitError,
    record_render_event,
)
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.infographics")


def _compat_attr(name: str, default):
    """Honor legacy tests/tools that patch app.api.seed_chat.<name>."""
    try:
        from . import seed_chat as seed_chat_module
        return getattr(seed_chat_module, name, default)
    except Exception:
        return default

@seed_chat_bp.route("/tree/infographics/plan", methods=["POST"])
def tree_plan_infographics():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    variant = (payload.get("variant") or payload.get("planner") or payload.get("plan_variant") or "").strip().lower()
    if variant in {"gas_tax_public_explainer", "public_explainer", "public"}:
        plan = plan_gas_tax_public_explainer(
            session.get("seed_state") or {},
            tree,
            format=payload.get("format") or payload.get("output_format") or "tiktok",
        )
    else:
        plan = plan_infographics(
            session.get("seed_state") or {},
            tree,
            format=payload.get("format") or payload.get("output_format") or "landscape",
        )
    session["infographic_plan"] = plan
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "infographic_plan": plan,
    })


@seed_chat_bp.route("/tree/infographics/render", methods=["POST"])
def tree_render_infographic():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    requested_slide_id = payload.get("slide_id")
    requested_slide_index = int(payload.get("slide_index", 0))
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    try:
        plan = _get_or_create_infographic_plan(session, payload)
    except ValueError:
        return jsonify({"error": "tree not initialised"}), 400

    sequence = plan.get("sequence") or []
    slide_index, slide = _find_slide(
        sequence,
        slide_id=requested_slide_id,
        slide_index=requested_slide_index,
    )
    if slide is None:
        return jsonify({"error": "slide_index out of range"}), 400

    slide_key = _slide_key(slide, slide_index)
    provider = (payload.get("provider") or os.environ.get("IMAGE_PROVIDER") or "nano_banana").strip().lower()
    render_mode = (payload.get("render_mode") or payload.get("mode") or "").strip().lower()
    filename = f"slide-{slide_index + 1:02d}.png"
    aspect_ratio = payload.get("aspect_ratio") or plan.get("aspect_ratio") or "16:9"
    image_size = payload.get("image_size") or "1K"
    try:
        if provider == "openai" and render_mode in {"strict", "strict_reference", "simple"}:
            _compat_attr("assert_render_allowed", assert_render_allowed)(session, "openai", requested=1)
            reference_image = _strict_reference_image_for_slide(slide, current_infographics_dir() / session_id)
            filename = _strict_filename_for_slide(slide_index, slide)
            rendered = _compat_attr("render_openai_infographic_slide_edit", render_openai_infographic_slide_edit)(
                slide,
                output_dir=current_infographics_dir() / session_id,
                filename=filename,
                reference_image=reference_image,
                prompt=_strict_reference_prompt(slide),
                model=payload.get("model"),
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            rendered["provider"] = "openai-strict-reference-edit"
            rendered["render_contract_version"] = _strict_contract_version(slide)
        elif provider == "openai":
            _compat_attr("assert_render_allowed", assert_render_allowed)(session, "openai", requested=1)
            rendered = _compat_attr("render_openai_infographic_slide", render_openai_infographic_slide)(
                slide,
                output_dir=current_infographics_dir() / session_id,
                filename=filename,
                model=payload.get("model"),
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
        else:
            rendered = _compat_attr("render_infographic_slide", render_infographic_slide)(
                slide,
                output_dir=current_infographics_dir() / session_id,
                filename=filename,
                model=payload.get("model"),
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            )
            rendered["provider"] = "nano_banana"
    except RenderLimitError as exc:
        return jsonify({
            "error": str(exc),
            "render_accounting": _compat_attr("accounting_summary", accounting_summary)(session),
        }), 429
    except OpenAIImageConfigError as exc:
        return jsonify({"error": f"openai_image_not_configured: {exc}"}), 503
    except OpenAIImageRenderError as exc:
        logger.error("OpenAI infographic render failed: %s", exc)
        return jsonify({"error": f"openai_image_render_failed: {exc}"}), 502
    except NanoBananaConfigError as exc:
        return jsonify({"error": f"nano_banana_not_configured: {exc}"}), 503
    except NanoBananaRenderError as exc:
        logger.error("Nano Banana infographic render failed: %s", exc)
        return jsonify({"error": f"nano_banana_render_failed: {exc}"}), 502

    rendered["slide_index"] = slide_index
    rendered["slide_id"] = slide_key
    rendered["url"] = f"/api/seed-chat/infographics/image/{session_id}/{filename}"
    _compat_attr("record_render_event", record_render_event)(
        session,
        provider=rendered.get("provider") or provider,
        model=rendered.get("model", ""),
        slide_index=slide_index,
        bytes=rendered.get("bytes", 0),
        quality=rendered.get("quality"),
        size=rendered.get("size") or rendered.get("image_size"),
    )
    renders = session.setdefault("infographic_renders", {})
    renders[slide_key] = rendered
    renders[str(slide_index)] = rendered
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "slide_index": slide_index,
        "slide_id": slide_key,
        "render": rendered,
        "render_accounting": _compat_attr("accounting_summary", accounting_summary)(session),
    })


def _strict_filename_for_slide(slide_index: int, slide: dict) -> str:
    template_id = slide.get("template_id") or "slide"
    suffix = {
        "SPENDING_BREAKDOWN": "strict-breakdown",
        "GOV_SPEND_CARD": "strict-gov",
        "GOV_SPEND_DETAIL": "strict-detail",
    }.get(template_id, "strict")
    return f"{suffix}-slide-{slide_index + 1:02d}.png"


def _strict_contract_version(slide: dict) -> str:
    return {
        "SPENDING_BREAKDOWN": "ui-v1-polished-three-tile",
        "GOV_SPEND_CARD": "ui-v1-gov-one-phrase",
        "GOV_SPEND_DETAIL": "ui-v1-detail-one-phrase",
    }.get(slide.get("template_id") or "", "ui-v1-strict-reference")


def _strict_reference_image_for_slide(slide: dict, output_dir: Path) -> Path:
    template_id = slide.get("template_id") or ""
    filename = {
        "SPENDING_BREAKDOWN": "reference-three-tile-polished.png",
        "GOV_SPEND_CARD": "reference-gov-simple-layout.png",
        "GOV_SPEND_DETAIL": "reference-detail-simple-layout.png",
    }.get(template_id)
    if filename:
        path = output_dir / filename
        if path.exists():
            return path
    fallback = output_dir / "slide-05.png"
    if fallback.exists():
        return fallback
    raise OpenAIImageRenderError(f"strict reference image missing for template {template_id}")


def _strict_reference_prompt(slide: dict) -> str:
    template_id = slide.get("template_id") or ""
    contract = slide.get("render_contract") or {}
    blocks = contract.get("map_to_reference_blocks") or {}
    if template_id == "SPENDING_BREAKDOWN":
        items = "\n".join(
            f"- {blocks.get(f'middle_bucket_{i}', {}).get('label', '')} {blocks.get(f'middle_bucket_{i}', {}).get('value', '')}"
            for i in range(1, 5)
        )
        return f"""Use the supplied polished reference as a STRICT layout and style template.
Preserve: top band, left category panel, three large item tiles, yellow "Why grows" tile, right benefit/pressure panels, and bottom strip.

Map content exactly:
Title: {slide.get('title')}
Left panel: {blocks.get('left_category_label')} / {blocks.get('left_category_value')}
Centre tiles:
{items}
Benefit panel: {_first_item(blocks.get('right_benefits'))}
Pressure panel: {_first_item(blocks.get('right_negatives'))}
Bottom strip: {blocks.get('bottom_debt_marker')}

Rules: one benefit and one pressure only; no photos; no 3D; simple doodle icons; no invented numbers; keep text large.
RENDER_CONTRACT_JSON:
{contract}
"""
    if template_id == "GOV_SPEND_CARD":
        phrases = _gov_one_phrase_fields(slide, blocks)
        buckets = (
            f"Welfare {blocks.get('middle_bucket_1', {}).get('value', '')} | "
            f"Health {blocks.get('middle_bucket_2', {}).get('value', '')} | "
            f"Education {blocks.get('middle_bucket_3', {}).get('value', '')} | "
            f"Defence {blocks.get('middle_bucket_4', {}).get('value', '')}"
        )
        return f"""Use the supplied government reference as a STRICT layout template.
CRITICAL TEXT RULE: one short phrase per box. No bullet lists. No paragraphs.

Title: {blocks.get('top_title')}
Top band: {blocks.get('top_party_flag')} | {blocks.get('top_calendar')} | {blocks.get('top_duration')}
Left total spend: {blocks.get('left_total_spend')}
What changed box: {phrases['changed']}
Why box: {phrases['why']}
Result box: {phrases['result']}
Benefit panel: {phrases['benefit']}
Pressure panel: {phrases['pressure']}
Mini bucket strip: {buckets}
Bottom debt strip: {blocks.get('bottom_debt_marker')}

Rules: hand-drawn sketchnote; doodle icons only; no invented numbers; keep text big.
RENDER_CONTRACT_JSON:
{contract}
"""
    if template_id == "GOV_SPEND_DETAIL":
        phrases = _detail_one_phrase_fields(slide, blocks)
        return f"""Use the supplied detail reference as a STRICT layout template.
CRITICAL TEXT RULE: one short phrase per box. No bullet lists. No paragraphs.

Title: {blocks.get('top_title')}
Top band: {blocks.get('top_party_flag')} | deeper dive | 1 issue
Left program panel: {phrases['program']}
What it pays for box: {phrases['pays']}
Benefit box: {phrases['benefit']}
Problem box: {phrases['problem']}
Scale side panel: {phrases['scale']}
Bottom scale check: {blocks.get('bottom_debt_marker')}

Rules: hand-drawn sketchnote; doodle icons only; no invented numbers; keep text big.
RENDER_CONTRACT_JSON:
{contract}
"""
    return slide.get("image_prompt") or ""


def _first_item(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _gov_one_phrase_fields(slide: dict, blocks: dict) -> dict[str, str]:
    phrase_map = {
        "spending_period_howard_1996_2007": ("Surplus era", "Mining boom helped", "Debt below zero", "core services funded", "future costs remained"),
        "spending_period_rudd_2007_2010": ("GFC stimulus", "Global shock", "Debt turned up", "jobs cushioned", "deficits began"),
        "spending_period_gillard_2010_2013": ("NDIS begins", "New social programs", "Debt kept rising", "disability support", "cost growth"),
        "spending_period_abbott_2013_2015": ("Budget repair fight", "Cuts blocked", "Debt still rose", "deficit focus", "repair politics"),
        "spending_period_turnbull_2015_2018": ("Services expanded", "NDIS ramp-up", "Debt rose again", "disability support", "structural gap"),
        "spending_period_morrison_pre_covid_2018_2020": ("Near balance", "Tax cuts + disasters", "Debt already high", "tax relief", "pre-COVID debt"),
        "spending_period_morrison_covid_2020_2022": ("COVID support", "Pandemic emergency", "Big debt jump", "income support", "overpayments"),
        "spending_period_albanese_2022_2026": ("Care spending", "Ageing + NDIS", "Debt still high", "aged care boost", "cost growth"),
    }
    changed, why, result, benefit, pressure = phrase_map.get(slide.get("slide_type"), ("Main change", "Main reason", "Main result", _first_item(blocks.get("right_benefits")), _first_item(blocks.get("right_negatives"))))
    return {"changed": changed, "why": why, "result": result, "benefit": benefit, "pressure": pressure}


def _detail_one_phrase_fields(slide: dict, blocks: dict) -> dict[str, str]:
    phrase_map = {
        "spending_detail_gillard_ndis": ("NDIS", "disability support", "independence", "fraud / price growth", "small vs $1t, big inside NDIS"),
        "spending_detail_gillard_carbon": ("Carbon package", "household compensation", "renewables signal", "price scare campaign", "costs vs climate benefits"),
        "spending_detail_morrison_jobkeeper": ("JobKeeper", "wage support", "jobs attached", "overpayments", "part of $219b COVID deficits"),
        "spending_detail_albanese_ndis_aged": ("NDIS + aged care", "care services", "family relief", "cost growth", "interest alone is $28.4b"),
    }
    program, pays, benefit, problem, scale = phrase_map.get(slide.get("slide_type"), (blocks.get("left_total_spend", "Program"), "what it pays for", _first_item(blocks.get("right_benefits")), _first_item(blocks.get("right_negatives")), "scale check"))
    return {"program": program, "pays": pays, "benefit": benefit, "problem": problem, "scale": scale}



@seed_chat_bp.route("/tree/infographics/accounting", methods=["GET"])
def tree_infographic_accounting():
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    return jsonify({
        "session_id": session_id,
        "render_accounting": _compat_attr("accounting_summary", accounting_summary)(session),
    })


@seed_chat_bp.route("/infographics/image/<session_id>/<filename>", methods=["GET"])
def get_infographic_image(session_id, filename):
    return send_from_directory(current_infographics_dir() / session_id, filename)
