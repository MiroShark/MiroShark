"""Education/debunking plan API routes."""

from flask import jsonify, request

from . import seed_chat_bp
from .seed_chat_common import current_store
from ..services.infographic_planner import plan_generic_education_infographics
from ..services.fact_packs.australia_budget import normalization_inputs_for_tax_per_resident
from ..services.normalization_engine import build_normalized_comparison

def _session_claims(session: dict) -> list[str | dict]:
    seed_state = session.get("seed_state") or {}
    claims = seed_state.get("contested_claims") or []
    if claims:
        return claims
    tree = session.get("tree") or {}
    if tree.get("question"):
        return [tree["question"]]
    if seed_state.get("topic"):
        return [seed_state["topic"]]
    return []


def _education_normalizations(topic: str, claims: list[str | dict]) -> list[dict]:
    """Return topic-aware normalized comparisons for the education plan UI."""

    haystack = " ".join([topic or "", *[str(c.get("surface_claim") or c.get("claim") or c.get("text") or c) if isinstance(c, dict) else str(c) for c in claims or []]]).lower()
    normalizations: list[dict] = []
    if any(token in haystack for token in ("tax", "revenue", "receipt", "debt", "spending", "budget")):
        inputs = normalization_inputs_for_tax_per_resident()
        comparison = build_normalized_comparison(
            inputs["label"],
            start=inputs["start"],
            end=inputs["end"],
            denominators=inputs["denominators"],
        )
        normalizations.append({
            "normalization_id": "australia_tax_per_resident_2006_2025",
            "label": inputs["label"],
            "question": "Is government collecting more tax per person, or only collecting more because there are more people?",
            "views": comparison["available_views"],
            "comparison": comparison,
            "source_facts": inputs.get("source_facts") or [],
            "plain_english": _tax_per_resident_plain_english(comparison),
        })
    return normalizations


def _tax_per_resident_plain_english(comparison: dict) -> str:
    start_pc = round(comparison["start"]["per_capita"] * 1000, -2)
    end_pc = round(comparison["end"]["per_capita"] * 1000, -2)
    pop_growth = comparison["changes"].get("population_growth_rate", 0)
    pc_ratio = comparison["changes"].get("per_capita_ratio", 0)
    return (
        f"Population rose about {pop_growth:.0%}, but tax collected per resident rose "
        f"from about ${start_pc:,.0f} to about ${end_pc:,.0f} — roughly {pc_ratio:.1f}× in nominal dollars. "
        "That average includes company tax, GST and other taxes, not just personal income tax."
    )


@seed_chat_bp.route("/education/plan", methods=["POST"])
def education_plan():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    topic = payload.get("topic") or seed_state.get("topic") or session.get("title") or "Untitled topic"
    claims = payload.get("claims") or _session_claims(session)
    plan = plan_generic_education_infographics(
        topic,
        claims,
        format=payload.get("format") or payload.get("output_format") or "landscape",
        audience_level=payload.get("audience_level") or "general_public",
    )
    education = plan.get("education_plan") or {}
    education["normalizations"] = _education_normalizations(topic, claims)
    plan["education_plan"] = education
    session["education_plan"] = education
    session["education_infographic_plan"] = plan
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "education_plan": plan.get("education_plan"),
        "infographic_plan": plan,
    })


