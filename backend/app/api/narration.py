"""Infographic narration/audio API routes."""

import os

from flask import jsonify, request, send_from_directory

from . import seed_chat_bp
from .seed_chat_common import _get_or_create_infographic_plan, current_infographics_dir, current_store
from ..services.narration_planner import plan_narration
from ..services.omnivoice_renderer import OmniVoiceRenderError, render_omnivoice_audio
from ..services.piper_renderer import PiperConfigError, PiperRenderError, render_piper_audio
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.narration")


def _compat_attr(name: str, default):
    """Honor legacy tests/tools that patch app.api.seed_chat.<name>."""
    try:
        from . import seed_chat as seed_chat_module
        return getattr(seed_chat_module, name, default)
    except Exception:
        return default

@seed_chat_bp.route("/tree/infographics/narration/plan", methods=["POST"])
def tree_plan_infographic_narration():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    try:
        infographic_plan = _get_or_create_infographic_plan(session, payload)
    except ValueError:
        return jsonify({"error": "tree not initialised"}), 400

    target_seconds = int(payload.get("target_seconds") or 75)
    narration_script = _compat_attr("plan_narration", plan_narration)(infographic_plan, target_seconds=target_seconds)
    session["narration_script"] = narration_script
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "narration_script": narration_script,
    })


@seed_chat_bp.route("/tree/infographics/audio/render", methods=["POST"])
def tree_render_infographic_audio():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    try:
        infographic_plan = _get_or_create_infographic_plan(session, payload)
    except ValueError:
        return jsonify({"error": "tree not initialised"}), 400

    narration_script = session.get("narration_script")
    if not narration_script:
        narration_script = _compat_attr("plan_narration", plan_narration)(
            infographic_plan,
            target_seconds=int(payload.get("target_seconds") or 75),
        )
        session["narration_script"] = narration_script

    slide_id = payload.get("slide_id")
    slide_index = payload.get("slide_index")
    clip_key = "narration"
    default_filename = "narration.wav"
    if slide_id:
        slides = narration_script.get("slides") or []
        beat = next((s for s in slides if s.get("slide_id") == slide_id), None)
        if beat is None:
            return jsonify({"error": "slide_id out of range"}), 400
        slide_index = int(beat.get("slide_index", 0))
        text = (payload.get("text") or beat.get("voiceover") or "").strip()
        clip_key = slide_id
        default_filename = f"audio-{slide_id.replace('.', '-')}.wav"
    elif slide_index is not None:
        slide_index = int(slide_index)
        slides = narration_script.get("slides") or []
        if slide_index < 0 or slide_index >= len(slides):
            return jsonify({"error": "slide_index out of range"}), 400
        beat = slides[slide_index]
        text = (payload.get("text") or beat.get("voiceover") or "").strip()
        clip_key = beat.get("slide_id") or str(slide_index)
        default_filename = f"audio-slide-{slide_index + 1:02d}.wav"
    else:
        text = (payload.get("text") or narration_script.get("full_voiceover") or "").strip()

    if not text:
        return jsonify({"error": "narration text required"}), 400

    filename = payload.get("filename") or default_filename
    provider = (payload.get("provider") or os.environ.get("AUDIO_PROVIDER") or "local_piper").strip().lower()
    try:
        if provider in {"local_piper", "piper", "local"}:
            rendered = _compat_attr("render_piper_audio", render_piper_audio)(
                text,
                output_dir=current_infographics_dir() / session_id,
                filename=filename,
                model_path=payload.get("model_path"),
                length_scale=payload.get("length_scale"),
                sentence_silence=payload.get("sentence_silence"),
            )
        else:
            rendered = _compat_attr("render_omnivoice_audio", render_omnivoice_audio)(
                text,
                output_dir=current_infographics_dir() / session_id,
                filename=filename,
                language=payload.get("language") or "English",
                duration=float(payload.get("duration") or 0),
                gender=payload.get("gender") or "Auto",
                age=payload.get("age") or "Auto",
                pitch=payload.get("pitch") or "Auto",
                style=payload.get("style") or "Auto",
                accent=payload.get("accent") or "Australian Accent / 澳大利亚口音",
            )
    except PiperConfigError as exc:
        return jsonify({"error": f"piper_not_configured: {exc}"}), 503
    except PiperRenderError as exc:
        logger.error("Piper audio render failed: %s", exc)
        return jsonify({"error": f"piper_render_failed: {exc}"}), 502
    except OmniVoiceRenderError as exc:
        logger.error("OmniVoice audio render failed: %s", exc)
        return jsonify({"error": f"omnivoice_render_failed: {exc}"}), 502

    rendered["url"] = f"/api/seed-chat/infographics/audio/{session_id}/{filename}"
    if slide_index is not None:
        rendered["slide_index"] = slide_index
        rendered["slide_id"] = clip_key
    audio_renders = session.setdefault("audio_renders", {})
    if slide_index is None:
        audio_renders["narration"] = rendered
    else:
        slide_renders = audio_renders.setdefault("slides", {})
        slide_renders[clip_key] = rendered
        slide_renders[str(slide_index)] = rendered
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "audio_render": rendered,
        "narration_script": narration_script,
    })




@seed_chat_bp.route("/infographics/audio/<session_id>/<filename>", methods=["GET"])
def get_infographic_audio(session_id, filename):
    return send_from_directory(current_infographics_dir() / session_id, filename)
