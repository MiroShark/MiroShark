"""Shared seed-chat API state and helpers."""

from pathlib import Path

from ..services.infographic_planner import plan_gas_tax_public_explainer, plan_infographics
from ..storage.session_store import SessionStore

# Sessions persist as JSON files at <backend>/sessions/.
# `__file__` is backend/app/api/seed_chat_common.py — go up 3 levels to reach backend/.
_SESSIONS_DIR = Path(__file__).resolve().parents[2] / "sessions"
_INFOGRAPHICS_DIR = Path(__file__).resolve().parents[2] / "generated" / "infographics"
store = SessionStore(base_dir=_SESSIONS_DIR)

def _get_or_create_infographic_plan(session: dict, payload: dict) -> dict:
    """Return a stored infographic plan, regenerating when format changes."""
    tree = session.get("tree")
    if not tree:
        raise ValueError("tree not initialised")

    requested_format = payload.get("format") or payload.get("output_format")
    requested_variant = (payload.get("variant") or payload.get("planner") or payload.get("plan_variant") or "").strip().lower()
    plan = session.get("infographic_plan")
    if (
        (not plan)
        or (requested_format and plan.get("output_format") != requested_format)
        or (requested_variant and plan.get("planner") != requested_variant)
    ):
        if requested_variant in {"gas_tax_public_explainer", "public_explainer", "public"}:
            plan = plan_gas_tax_public_explainer(
                session.get("seed_state") or {},
                tree,
                format=requested_format or "tiktok",
            )
        else:
            plan = plan_infographics(
                session.get("seed_state") or {},
                tree,
                format=requested_format or "landscape",
            )
        session["infographic_plan"] = plan
    return plan


def _find_slide(sequence: list[dict], *, slide_id: str | None = None, slide_index: int | None = None) -> tuple[int, dict] | tuple[None, None]:
    if slide_id:
        for idx, slide in enumerate(sequence):
            if slide.get("slide_id") == slide_id:
                return idx, slide
        return None, None
    if slide_index is None:
        slide_index = 0
    if slide_index < 0 or slide_index >= len(sequence):
        return None, None
    return slide_index, sequence[slide_index]


def _slide_key(slide: dict, slide_index: int) -> str:
    return slide.get("slide_id") or str(slide_index)




def current_store():
    """Return the active session store, honoring legacy app.api.seed_chat._store patches."""
    try:
        from . import seed_chat as seed_chat_module
        return getattr(seed_chat_module, "_store", store)
    except Exception:
        return store


def current_infographics_dir():
    """Return generated media dir, honoring legacy app.api.seed_chat._INFOGRAPHICS_DIR patches."""
    try:
        from . import seed_chat as seed_chat_module
        return getattr(seed_chat_module, "_INFOGRAPHICS_DIR", _INFOGRAPHICS_DIR)
    except Exception:
        return _INFOGRAPHICS_DIR
