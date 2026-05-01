"""
Simulation-related API routes
Step 2: Entity reading and filtering, Wonderwall simulation preparation and execution (fully automated)
"""

import os
import io
import csv
import hmac
import json
import traceback
from datetime import datetime, timezone
from functools import wraps
from flask import request, jsonify, send_file, current_app

from . import simulation_bp
from ..utils.llm_client import create_smart_llm_client, create_llm_client
from ..utils.i18n import get_locale, t as _t
from ..utils.validation import validate_simulation_id
from ..config import Config
from ..services.entity_reader import EntityReader
from ..services.wonderwall_profile_generator import WonderwallProfileGenerator
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_config_generator import SimulationConfigGenerator
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..utils.logger import get_logger
from ..models.project import ProjectManager

logger = get_logger('miroshark.api.simulation')


@simulation_bp.before_request
def _validate_url_simulation_id():
    """Reject requests whose URL-derived simulation_id could cause path traversal."""
    from flask import request as _req
    sim_id = _req.view_args.get('simulation_id') if _req.view_args else None
    if sim_id is not None:
        try:
            validate_simulation_id(sim_id)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400


# ============== Admin Auth (mutation endpoints) ==============
#
# Mutation endpoints that write to a simulation's on-disk state
# (/publish, /resolve, /outcome) require a shared admin secret —
# ``MIROSHARK_ADMIN_TOKEN`` — supplied via the ``Authorization: Bearer
# <token>`` header. This is the lightest-weight option from issue #48
# (per-sim ownership tokens / full account auth were also discussed,
# but a shared operator secret matches the deployment model: a single
# operator runs MiroShark behind a reverse proxy or on localhost, and
# any mutation is theirs).
#
# Fail-closed semantics: if ``MIROSHARK_ADMIN_TOKEN`` is unset or empty
# in the process environment, the dependency returns **503**, NOT 200.
# We deliberately do not silently fall back to "no auth required" — an
# operator who forgot to configure the secret would otherwise ship an
# open mutation surface and never know. The 503 message is generic on
# purpose so the failure is visible without leaking config detail to a
# probe.
#
# We use ``hmac.compare_digest`` for the actual comparison so a network
# attacker can't time-trial the token byte by byte.


_ADMIN_TOKEN_ENV_VAR = "MIROSHARK_ADMIN_TOKEN"


def _load_admin_token() -> str:
    """Read ``MIROSHARK_ADMIN_TOKEN`` from the environment at *call* time.

    Resolved per-request rather than module-import time so tests can
    monkeypatch ``os.environ`` without re-importing the module, and so
    operators rotating the token via a process restart don't need a
    code reload.
    """
    return (os.environ.get(_ADMIN_TOKEN_ENV_VAR) or "").strip()


def _extract_bearer_token() -> str:
    """Pull the token from the ``Authorization: Bearer <token>`` header.

    Returns the empty string when the header is missing or malformed —
    the caller treats both as "no token", which then resolves to a 401.
    """
    auth_header = request.headers.get("Authorization", "") or ""
    parts = auth_header.split(None, 1)
    if len(parts) != 2:
        return ""
    scheme, token = parts
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def require_admin_token(view_func):
    """Decorator: gate a Flask view on a valid admin bearer token.

    Behaviour matrix:

    * ``MIROSHARK_ADMIN_TOKEN`` unset/empty in env → **503**
      (fail-closed; the deploy is misconfigured and we refuse to serve
      the mutation rather than silently allowing it).
    * ``Authorization`` header missing or wrong / token mismatch →
      **401** with a generic "Unauthorized" message. We deliberately do
      not distinguish "missing" from "wrong" so a probe can't tell
      whether it found a valid endpoint.
    * Match → forward to the wrapped view.

    The constant-time comparison via :func:`hmac.compare_digest` keeps
    a network attacker from byte-trialing the token.

    Reusable across blueprints — apply to any future mutation endpoint
    that should share the same operator-secret gate.
    """

    @wraps(view_func)
    def _wrapper(*args, **kwargs):
        locale = get_locale(request)
        expected = _load_admin_token()
        if not expected:
            logger.error(
                "Mutation endpoint %s reached but %s is unset — refusing "
                "to serve (fail-closed). Set the env var to enable.",
                request.path, _ADMIN_TOKEN_ENV_VAR,
            )
            return jsonify({
                "success": False,
                "error": _t(
                    "Admin authentication is not configured on this deployment.",
                    "此部署尚未配置管理员身份验证。",
                    locale,
                ),
            }), 503

        provided = _extract_bearer_token()
        # ``hmac.compare_digest`` requires equal-length operands of the
        # same type to do its constant-time work; encode both sides to
        # bytes and let the function handle short-circuiting safely.
        if not provided or not hmac.compare_digest(
            provided.encode("utf-8"), expected.encode("utf-8")
        ):
            return jsonify({
                "success": False,
                "error": _t("Unauthorized", "未授权", locale),
            }), 401

        return view_func(*args, **kwargs)

    return _wrapper


def _get_simulation_id_or_400(data: dict, locale: str = "en") -> tuple:
    """Extract and validate simulation_id from POST body.

    Returns (simulation_id, None) on success or (None, error_response) on failure.
    """
    simulation_id = data.get('simulation_id')
    if not simulation_id:
        return None, (jsonify({
            "success": False,
            "error": _t("Please provide simulation_id", "请提供 simulation_id", locale),
        }), 400)
    try:
        validate_simulation_id(simulation_id)
    except ValueError as exc:
        return None, (jsonify({"success": False, "error": str(exc)}), 400)
    return simulation_id, None


# Interview prompt optimization prefix
# Adding this prefix prevents Agents from calling tools and makes them reply with text directly
INTERVIEW_PROMPT_PREFIX = "Based on your persona, all past memories and actions, reply directly with text without calling any tools: "


def _ensure_env_alive(simulation_id: str) -> bool:
    """
    Check if simulation environment is alive. If not, try to restart it
    in env-only mode for interviews. Returns True if env is alive.
    """
    if SimulationRunner.check_env_alive(simulation_id):
        return True

    # Try to auto-restart the environment
    logger.info(f"Environment not alive for {simulation_id}, attempting auto-restart for interviews...")
    is_prepared, _ = _check_simulation_prepared(simulation_id)
    if not is_prepared:
        return False

    try:
        SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform='parallel',
            start_round=0,
            env_only=True
        )
        # Wait a bit for the env to start
        import time
        for _ in range(15):
            time.sleep(2)
            if SimulationRunner.check_env_alive(simulation_id):
                logger.info(f"Environment auto-restarted for {simulation_id}")
                return True
        logger.warning(f"Environment auto-restart timed out for {simulation_id}")
        return False
    except Exception as e:
        logger.error(f"Failed to auto-restart environment: {e}")
        return False


def optimize_interview_prompt(prompt: str) -> str:
    """
    Optimize interview prompt by adding prefix to prevent Agent from calling tools

    Args:
        prompt: Original question

    Returns:
        Optimized question
    """
    if not prompt:
        return prompt
    # Avoid adding prefix repeatedly
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


# ============== Shared in-memory rate limit + LRU helpers ==============
#
# Three endpoints (scenario-suggest, ask, trending) each need a per-IP sliding
# window rate limiter, and two need a bounded LRU cache. The helpers below
# centralize that logic so each endpoint only needs its own config constants.


def _client_ip() -> str:
    """Resolve the client IP for rate-limit keying, tolerating proxies."""
    return (
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        or request.remote_addr
        or 'unknown'
    )


def _sliding_window_rate_limited(
    hits: "dict[str, list[float]]",
    client_ip: str,
    *,
    window_sec: float,
    max_calls: int,
) -> bool:
    """Sliding-window per-IP rate limit. Mutates ``hits`` in place.

    Returns True when ``client_ip`` has already exceeded ``max_calls`` within
    the last ``window_sec`` seconds. Opportunistically GCs stale buckets when
    the dict grows above 1024 entries.
    """
    import time
    now = time.monotonic()
    cutoff = now - window_sec
    bucket = [t for t in hits.get(client_ip, []) if t > cutoff]
    if len(bucket) >= max_calls:
        hits[client_ip] = bucket
        return True
    bucket.append(now)
    hits[client_ip] = bucket
    if len(hits) > 1024:
        for ip in list(hits.keys()):
            if not hits[ip] or hits[ip][-1] < cutoff:
                hits.pop(ip, None)
    return False


def _lru_get(cache: dict, order: list, key: str):
    """LRU read: returns the entry (or None) and promotes it to most-recent."""
    entry = cache.get(key)
    if entry is None:
        return None
    try:
        order.remove(key)
    except ValueError:
        pass
    order.append(key)
    return entry


def _lru_put(cache: dict, order: list, key: str, value, *, max_size: int) -> None:
    """LRU write with bounded size; evicts least-recent entries when full."""
    if key in cache:
        try:
            order.remove(key)
        except ValueError:
            pass
    cache[key] = value
    order.append(key)
    while len(order) > max_size:
        cache.pop(order.pop(0), None)


# ============== Scenario Auto-Suggest ==============

# In-memory LRU-style cache for scenario suggestions.
# Keyed by SHA-256 of the normalized text preview so re-renders / brief edits
# above/below the sampled window don't re-hit the LLM.
_SCENARIO_SUGGEST_CACHE: "dict[str, dict]" = {}
_SCENARIO_SUGGEST_CACHE_ORDER: "list[str]" = []
_SCENARIO_SUGGEST_CACHE_MAX = 64

# Per-IP sliding-window rate limit for the unauthenticated /suggest-scenarios
# endpoint. Prevents a runaway client (or attacker) from torching the LLM
# budget by hammering the endpoint. Bounds: 10 calls / 60s / IP.
_SCENARIO_RATE_WINDOW_SEC = 60
_SCENARIO_RATE_MAX_CALLS = 10
_SCENARIO_RATE_HITS: "dict[str, list[float]]" = {}

# Characters of preview sent to the LLM. Keeps prompt cost bounded even for
# 500K-token documents.
_SCENARIO_PREVIEW_CHAR_LIMIT = 2000

_SCENARIO_SUGGEST_SYSTEM_PROMPT = (
    "You generate concise prediction-market-style scenario questions for an "
    "agent-based social simulation.\n"
    "Given a document excerpt, return exactly 3 scenarios that cover a "
    "bullish, a bearish, and a neutral framing of an outcome the document "
    "could drive. Scenarios must be:\n"
    "- Concrete, answerable YES/NO questions with a specific outcome\n"
    "- Grounded in the document (reference named actors, events, or "
    "institutions where possible)\n"
    "- Non-trivial (not 'will X happen this year' with no stake)\n"
    "- Tied to a resolution window that makes sense for the dynamics "
    "involved — a few weeks for fast news cycles, a few months for "
    "product/market reactions, up to a year for policy or structural "
    "outcomes. Pick whatever window fits the scenario best.\n"
    "Each expected_yes_range must be two integers 0-100 reflecting a "
    "plausible initial market probability band for that framing.\n"
    "Return JSON exactly of this shape:\n"
    '{ "suggestions": [ { "question": str, "label": "Bull"|"Bear"|"Neutral", '
    '"expected_yes_range": [int, int], "rationale": str } ] }\n'
    "The rationale field is a single sentence (<= 140 chars) explaining why "
    "this framing follows from the document. Do not include any other fields."
)


def _today_context() -> str:
    """Current-date preamble so time-sensitive LLM output anchors on today
    rather than the model's training cutoff."""
    return f"Today's date is {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."


def _normalize_preview(text: str) -> str:
    """Whitespace-collapse + length-clamp the preview before hashing/sending."""
    collapsed = " ".join((text or "").split())
    return collapsed[:_SCENARIO_PREVIEW_CHAR_LIMIT]


def _scenario_rate_limited(client_ip: str) -> bool:
    """Return True if this IP has exceeded the per-window call budget."""
    return _sliding_window_rate_limited(
        _SCENARIO_RATE_HITS,
        client_ip,
        window_sec=_SCENARIO_RATE_WINDOW_SEC,
        max_calls=_SCENARIO_RATE_MAX_CALLS,
    )


def _scenario_cache_get(key: str):
    return _lru_get(_SCENARIO_SUGGEST_CACHE, _SCENARIO_SUGGEST_CACHE_ORDER, key)


def _scenario_cache_put(key: str, value: dict) -> None:
    _lru_put(
        _SCENARIO_SUGGEST_CACHE,
        _SCENARIO_SUGGEST_CACHE_ORDER,
        key,
        value,
        max_size=_SCENARIO_SUGGEST_CACHE_MAX,
    )


_VALID_SCENARIO_LABELS = ("Bull", "Bear", "Neutral")


def _clean_suggestions(payload) -> list:
    """Validate and normalize the LLM's suggestions array.

    Silently drops malformed entries and clamps the result to 3.
    Returns [] if nothing survives — the endpoint treats that as a graceful
    no-op (UI hides the panel).
    """
    if not isinstance(payload, dict):
        return []
    raw = payload.get("suggestions")
    if not isinstance(raw, list):
        return []

    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = (item.get("question") or "").strip()
        label = (item.get("label") or "").strip().capitalize()
        if label not in _VALID_SCENARIO_LABELS:
            continue
        yes_range = item.get("expected_yes_range")
        if (
            not isinstance(yes_range, (list, tuple))
            or len(yes_range) != 2
        ):
            continue
        try:
            lo = max(0, min(100, int(yes_range[0])))
            hi = max(0, min(100, int(yes_range[1])))
        except (TypeError, ValueError):
            continue
        if lo > hi:
            lo, hi = hi, lo
        rationale = (item.get("rationale") or "").strip()
        if len(question) < 8 or len(question) > 240:
            continue
        if len(rationale) > 200:
            rationale = rationale[:197].rstrip() + "..."
        out.append({
            "question": question,
            "label": label,
            "expected_yes_range": [lo, hi],
            "rationale": rationale,
        })
        if len(out) == 3:
            break
    return out


@simulation_bp.route('/suggest-scenarios', methods=['POST'])
def suggest_scenarios():
    """
    Generate 3 prediction-market-style simulation scenarios from a document
    preview, so new users don't face the blank-page problem at setup.

    Request (JSON):
        {
            "text_preview": "<document text — first ~2000 chars is enough>",
            "no_cache": false   // optional; forces a fresh LLM call
        }

    Returns:
        {
            "success": true,
            "data": {
                "suggestions": [
                    {
                        "question": "Will the EU AI Act pass with its stricter
                                     biometrics provisions intact by June 2026?",
                        "label": "Bull" | "Bear" | "Neutral",
                        "expected_yes_range": [60, 70],
                        "rationale": "Document emphasizes regulator unity on
                                      biometric safeguards."
                    },
                    ...  // up to 3 entries, possibly 0 if the LLM failed
                ],
                "cached": false,
                "model": "gpt-4o-mini"   // whatever provider is configured
            }
        }
    """
    locale = get_locale(request)
    try:
        client_ip = _client_ip()
        if _scenario_rate_limited(client_ip):
            return jsonify({
                "success": True,
                "data": {"suggestions": [], "cached": False, "reason": "rate_limited"}
            }), 429

        data = request.get_json(silent=True) or {}
        preview = data.get('text_preview') or data.get('document_preview') or ''
        if not isinstance(preview, str):
            return jsonify({
                "success": False,
                "error": _t(
                    "text_preview must be a string",
                    "text_preview 必须是字符串",
                    locale,
                )
            }), 400

        sim_prompt_raw = data.get('simulation_prompt') or ''
        if not isinstance(sim_prompt_raw, str):
            sim_prompt_raw = ''
        sim_prompt = " ".join(sim_prompt_raw.split())[:600]

        normalized = _normalize_preview(preview)
        # Require at least ~80 chars so we don't spin the LLM on keystroke fragments.
        if len(normalized) < 80:
            return jsonify({
                "success": True,
                "data": {"suggestions": [], "cached": False, "reason": "preview_too_short"}
            })

        import hashlib
        cache_key = hashlib.sha256(
            (normalized + "||" + sim_prompt).encode('utf-8')
        ).hexdigest()

        if not data.get('no_cache'):
            cached = _scenario_cache_get(cache_key)
            if cached is not None:
                return jsonify({
                    "success": True,
                    "data": {**cached, "cached": True}
                })

        try:
            llm = create_llm_client(timeout=20.0)
        except Exception as exc:
            logger.warning(f"suggest-scenarios: LLM client unavailable: {exc}")
            return jsonify({
                "success": True,
                "data": {"suggestions": [], "cached": False, "reason": "llm_unavailable"}
            })

        sim_prompt_block = (
            f"User's simulation prompt:\n{sim_prompt}\n\n"
            if sim_prompt else ""
        )
        messages = [
            {"role": "system", "content": _SCENARIO_SUGGEST_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{_today_context()}\n\n"
                    f"{sim_prompt_block}"
                    "Document excerpt (truncated):\n\n"
                    f"{normalized}\n\n"
                    "Generate the 3 scenarios now. Pick a resolution window "
                    "that fits each scenario's natural time horizon."
                ),
            },
        ]

        try:
            parsed = llm.chat_json(messages, temperature=0.4, max_tokens=700)
        except Exception as exc:
            # Don't 500 — scenario auto-suggest is best-effort; the form still works.
            logger.warning(f"suggest-scenarios: LLM call failed: {exc}")
            return jsonify({
                "success": True,
                "data": {"suggestions": [], "cached": False, "reason": "llm_error"}
            })

        suggestions = _clean_suggestions(parsed)

        result = {
            "suggestions": suggestions,
            "model": getattr(llm, 'model', None) or Config.LLM_MODEL_NAME,
        }

        if suggestions:
            _scenario_cache_put(cache_key, result)

        return jsonify({"success": True, "data": {**result, "cached": False}})

    except Exception as e:
        # Log internals server-side; surface only a generic error to the client
        # since this endpoint is unauthenticated.
        logger.error(
            f"Failed to suggest scenarios: {e}\n{traceback.format_exc()}"
        )
        return jsonify({
            "success": False,
            "error": "scenario_suggest_failed"
        }), 500


# ============== Ask Mode — question-only pipeline ==============
#
# Borrowed shape from MiroWhale's `mirowhale ask` CLI: the user arrives with a
# question and no document, and we synthesize a seed doc from the LLM's own
# research so the existing ontology → graph → simulation pipeline works
# unchanged downstream.

_ASK_RATE_WINDOW_SEC = 60
_ASK_RATE_MAX_CALLS = 5
_ASK_RATE_HITS: "dict[str, list[float]]" = {}
_ASK_CACHE: "dict[str, dict]" = {}
_ASK_CACHE_ORDER: "list[str]" = []
_ASK_CACHE_MAX = 32
_ASK_QUESTION_MAX_CHARS = 400

_ASK_SYSTEM_PROMPT = (
    "You are a research analyst producing a briefing that will seed an "
    "agent-based social simulation. Hundreds of personas will be generated "
    "from this briefing, so the richer and more specifically populated it "
    "is, the better the simulation behaves.\n\n"
    "Return JSON of this exact shape:\n"
    '{ "title": str, "simulation_requirement": str, "seed_document": str, '
    '"key_actors": [str], "suggested_platforms": ["twitter"|"reddit"|"polymarket"] }\n\n'
    "Rules:\n"
    "- title: short (<=60 chars), descriptive — this is the project name.\n"
    "- simulation_requirement: one paragraph (~400-600 chars) framing the "
    "simulation goal — who the agents should represent and what dynamics to watch.\n"
    "- seed_document: a 1800-3500 character markdown briefing with the sections "
    "Context, Key Actors, Camps & Positions, Recent Events, and Open Questions. "
    "Populate it with CONCRETE, NAMED entities — not categories. Name specific "
    "companies, products, funds, media outlets, regulators, CEOs, founders, "
    "journalists, analysts, researchers, academics, activists, politicians, "
    "and vocal critics/skeptics. Cover multiple camps so bulls, bears, and "
    "neutrals are all represented. Prefer qualitative framing over fabricated "
    "statistics, but DO name real organizations and real public figures "
    "associated with the topic.\n"
    "- key_actors: 15-25 entries, each a SPECIFIC named person, company, fund, "
    "outlet, or agency (e.g. 'Jensen Huang — NVIDIA CEO', 'Gary Marcus — AI "
    "critic, NYU emeritus', 'Andreessen Horowitz — AI-bull VC', 'Financial "
    "Times Lex column', 'EU AI Office'). Mix roles (exec, investor, journalist, "
    "researcher, regulator, activist), stances (bullish/bearish/neutral), and "
    "geographies (US, EU, UK, Asia) so the persona generator has variety. "
    "Avoid generic entries like 'venture capitalists' or 'the general public'.\n"
    "- suggested_platforms: 1-3 from the allowed set, chosen by relevance.\n"
    "Do not include disclaimers. Do not invent specific quotes or precise "
    "figures. Do not include any other fields."
)


def _ask_rate_limited(client_ip: str) -> bool:
    return _sliding_window_rate_limited(
        _ASK_RATE_HITS,
        client_ip,
        window_sec=_ASK_RATE_WINDOW_SEC,
        max_calls=_ASK_RATE_MAX_CALLS,
    )


def _ask_cache_get(key: str):
    return _lru_get(_ASK_CACHE, _ASK_CACHE_ORDER, key)


def _ask_cache_put(key: str, value: dict) -> None:
    _lru_put(_ASK_CACHE, _ASK_CACHE_ORDER, key, value, max_size=_ASK_CACHE_MAX)


_ASK_ALLOWED_PLATFORMS = {"twitter", "reddit", "polymarket"}


def _ask_clean_result(payload, question: str) -> "dict | None":
    if not isinstance(payload, dict):
        return None
    title = (payload.get("title") or "").strip()
    req = (payload.get("simulation_requirement") or "").strip()
    doc = (payload.get("seed_document") or "").strip()
    actors_raw = payload.get("key_actors") or []
    platforms_raw = payload.get("suggested_platforms") or []

    if not title or len(title) > 120:
        title = (question[:57] + "...") if len(question) > 60 else question
    if len(req) < 40 or len(doc) < 400:
        return None

    actors = []
    if isinstance(actors_raw, list):
        for a in actors_raw:
            if isinstance(a, str) and a.strip():
                actors.append(a.strip())
            if len(actors) == 25:
                break

    platforms = []
    if isinstance(platforms_raw, list):
        for p in platforms_raw:
            if isinstance(p, str) and p.strip().lower() in _ASK_ALLOWED_PLATFORMS:
                platforms.append(p.strip().lower())
    # dedupe while preserving order
    seen = set()
    platforms = [p for p in platforms if not (p in seen or seen.add(p))]
    if not platforms:
        platforms = ["twitter", "reddit"]

    return {
        "title": title[:120],
        "simulation_requirement": req,
        "seed_document": doc,
        "key_actors": actors,
        "suggested_platforms": platforms,
    }


@simulation_bp.route('/ask', methods=['POST'])
def ask_mode():
    """Question-only pipeline: turn a bare question into a seed document.

    Request (JSON): ``{"question": "..."}``. Returns a synthesized title,
    simulation_requirement, and a markdown seed_document the frontend can feed
    straight into ``/api/graph/ontology/generate`` as a ``url_docs`` entry —
    the rest of the flow (ontology, graph build, profiles, simulation) runs
    unchanged.

    Response:
    ``{"success": true, "data": {title, simulation_requirement, seed_document,
    key_actors, suggested_platforms, model, cached}}``.
    """
    locale = get_locale(request)
    try:
        client_ip = _client_ip()
        if _ask_rate_limited(client_ip):
            return jsonify({
                "success": False,
                "error": "rate_limited",
            }), 429

        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        if not isinstance(question, str) or len(question) < 8:
            return jsonify({
                "success": False,
                "error": _t(
                    "question must be at least 8 characters",
                    "问题至少需要 8 个字符",
                    locale,
                ),
            }), 400
        if len(question) > _ASK_QUESTION_MAX_CHARS:
            return jsonify({
                "success": False,
                "error": _t(
                    f"question too long (max {_ASK_QUESTION_MAX_CHARS} chars)",
                    f"问题过长(最多 {_ASK_QUESTION_MAX_CHARS} 字符)",
                    locale,
                ),
            }), 400

        import hashlib
        cache_key = hashlib.sha256(question.lower().encode('utf-8')).hexdigest()

        if not data.get('no_cache'):
            cached = _ask_cache_get(cache_key)
            if cached is not None:
                return jsonify({"success": True, "data": {**cached, "cached": True}})

        try:
            llm = create_smart_llm_client(timeout=60.0)
        except Exception as exc:
            logger.warning(f"ask: smart LLM unavailable: {exc}")
            return jsonify({"success": False, "error": "llm_unavailable"}), 503

        messages = [
            {"role": "system", "content": _ASK_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{_today_context()}\n\n"
                    f"User question: {question}\n\n"
                    "Produce the briefing now."
                ),
            },
        ]

        try:
            parsed = llm.chat_json(messages, temperature=0.4, max_tokens=3500)
        except Exception as exc:
            logger.warning(f"ask: LLM call failed: {exc}")
            return jsonify({"success": False, "error": "llm_error"}), 502

        cleaned = _ask_clean_result(parsed, question)
        if cleaned is None:
            return jsonify({"success": False, "error": "llm_returned_invalid_briefing"}), 502

        cleaned["model"] = getattr(llm, 'model', None) or Config.SMART_MODEL_NAME or Config.LLM_MODEL_NAME
        _ask_cache_put(cache_key, cleaned)
        return jsonify({"success": True, "data": {**cleaned, "cached": False}})

    except Exception as e:
        logger.error(f"ask mode failed: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "ask_failed"}), 500


# ============== Trending Topics ==============
#
# Closes the remaining onboarding gap left by Scenario Auto-Suggest (PR #39).
# Auto-Suggest helps users who already pasted a document; Trending Topics
# helps users who arrive without one — they pick a current headline, the URL
# is fetched, and Auto-Suggest fires immediately on the resulting text.

# Curated default feed list — broadly newsworthy, free, public.
# Operators can override via TRENDING_FEEDS env var (comma-separated URLs).
_TRENDING_DEFAULT_FEEDS = (
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://hnrss.org/frontpage",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
)

# Items returned to the client per request.
_TRENDING_ITEM_LIMIT = 5

# Per-feed fetch timeout. Keeps a slow upstream from stalling the whole call.
_TRENDING_FEED_TIMEOUT_SEC = 5.0

# Cache freshness window. Avoids re-hitting upstream feeds on every page load.
_TRENDING_CACHE_TTL_SEC = 900   # 15 minutes

# Per-IP rate limit. RSS fetches are cheaper than LLM calls, so the budget is
# higher than scenario-suggest's, but still bounded.
_TRENDING_RATE_WINDOW_SEC = 60
_TRENDING_RATE_MAX_CALLS = 30
_TRENDING_RATE_HITS: "dict[str, list[float]]" = {}

# Cache: keyed by feed-list hash → (expires_at_monotonic, items)
_TRENDING_CACHE: "dict[str, tuple[float, list[dict]]]" = {}

# RSS/Atom XML namespaces we care about. Atom uses default namespaces; RSS
# 2.0 sometimes injects Dublin Core for dates. ElementTree exposes namespaces
# as "{uri}localname" in tag names.
_TRENDING_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _trending_get_feeds() -> "list[str]":
    """Resolve the configured feed list from env, falling back to defaults."""
    raw = (os.environ.get('TRENDING_FEEDS') or '').strip()
    if not raw:
        return list(_TRENDING_DEFAULT_FEEDS)
    feeds = [u.strip() for u in raw.split(',') if u.strip()]
    return feeds or list(_TRENDING_DEFAULT_FEEDS)


def _trending_url_allowed(url: str) -> bool:
    """Reject URLs that aren't http(s) or target private/loopback hosts.

    First line of defense against using this endpoint as an SSRF proxy via
    the ?feeds= query param. We don't resolve DNS here (that would add
    per-call latency and still leaves a rebinding window); the hostname-level
    deny combined with the other controls — rate limit, 1 MB body cap, 5 s
    timeout, structured-output-only — is sufficient for this feature's scope.
    """
    try:
        from urllib.parse import urlparse
        import ipaddress
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ('http', 'https'):
        return False
    host = (parsed.hostname or '').strip().lower()
    if not host:
        return False
    # Block obvious loopback / cloud-metadata hostnames.
    if host in ('localhost', 'ip6-localhost', 'metadata.google.internal'):
        return False
    # If host parses as a standard IP literal, block private / reserved ranges.
    try:
        ip = ipaddress.ip_address(host)
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    except ValueError:
        pass  # Not a standard IP literal — fall through to obfuscated-form check.
    # Guard against obfuscated IPv4: Python's socket.getaddrinfo accepts
    # integer (2130706433), octal (0177.0.0.1), and hex (0x7f000001) encodings
    # of 127.0.0.1, and ipaddress.ip_address rejects all of them — so an
    # attacker could bypass the check above and still hit localhost. Normalize
    # via inet_aton (which accepts every form socket does) and re-check.
    try:
        import socket
        canonical = socket.inet_ntoa(socket.inet_aton(host))
        ip = ipaddress.ip_address(canonical)
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    except (OSError, ValueError):
        pass  # Not an IPv4 in any encoding — a real DNS name. Allow.
    return True


def _trending_rate_limited(client_ip: str) -> bool:
    """Sliding-window per-IP rate limit, mirroring scenario-suggest's pattern."""
    return _sliding_window_rate_limited(
        _TRENDING_RATE_HITS,
        client_ip,
        window_sec=_TRENDING_RATE_WINDOW_SEC,
        max_calls=_TRENDING_RATE_MAX_CALLS,
    )


def _trending_parse_pubdate(raw: str):
    """Best-effort parse of RSS/Atom date strings into a UTC datetime.

    Handles RFC 822 (RSS pubDate), RFC 3339 / ISO 8601 (Atom updated/published),
    and a couple of common malformed variants seen in the wild. Returns None
    on failure — callers fall back to "now-ish" sort order.
    """
    if not raw:
        return None
    raw = raw.strip()
    # Try ISO 8601 first (Atom + many modern RSS feeds use it).
    try:
        # Python's fromisoformat needs "+00:00" not "Z".
        iso = raw.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass
    # Fall back to RFC 822 / 2822 via email.utils (RSS pubDate format).
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _trending_strip_localname(tag: str) -> str:
    """Strip XML namespace prefix from a tag name: '{ns}foo' → 'foo'."""
    if tag.startswith('{'):
        return tag.split('}', 1)[1]
    return tag


def _trending_text(elem) -> str:
    """Return the trimmed text of an XML element, or '' if missing/empty."""
    if elem is None:
        return ''
    return (elem.text or '').strip()


def _trending_extract_link(item) -> str:
    """Pull the first usable URL from an RSS or Atom entry.

    Atom feeds emit multiple <link> elements per entry: rel="alternate" is
    the article URL, rel="self" is the entry's own representation, and other
    rels (enclosure, replies) point at non-article resources. We always
    prefer rel="alternate" (or an unspecified rel, which Atom treats as
    alternate by default).
    """
    # First pass: prefer Atom <link rel="alternate" href="..."/> entries.
    for child in item:
        if _trending_strip_localname(child.tag) != 'link':
            continue
        href = (child.get('href') or '').strip()
        if not href:
            continue
        rel = (child.get('rel') or 'alternate').lower()
        if rel == 'alternate' and href.startswith('http'):
            return href
    # Second pass: RSS 2.0 — <link>https://...</link> with no attributes.
    for child in item:
        if _trending_strip_localname(child.tag) != 'link':
            continue
        text = (child.text or '').strip()
        if text.startswith('http'):
            return text
    # Last resort: <guid isPermaLink="true"> may carry the article URL.
    for child in item:
        if _trending_strip_localname(child.tag) != 'guid':
            continue
        text = (child.text or '').strip()
        is_perma = (child.get('isPermaLink', 'true').lower() != 'false')
        if is_perma and text.startswith('http'):
            return text
    return ''


def _trending_extract_published(item) -> str:
    """Pull the best available timestamp from an RSS or Atom entry."""
    # Try in priority order: published > updated > pubDate > dc:date.
    candidates = []
    for child in item:
        local = _trending_strip_localname(child.tag)
        if local in ('published', 'updated', 'pubDate', 'date'):
            text = (child.text or '').strip()
            if text:
                candidates.append((local, text))
    priority = {'published': 0, 'updated': 1, 'pubDate': 2, 'date': 3}
    candidates.sort(key=lambda t: priority.get(t[0], 99))
    return candidates[0][1] if candidates else ''


def _trending_extract_source(root, feed_url: str) -> str:
    """Pick a human-readable source name from the channel/feed metadata."""
    # RSS: <channel><title>...</title>
    channel = root.find('channel')
    if channel is not None:
        title = _trending_text(channel.find('title'))
        if title:
            return title[:80]
    # Atom: <feed><title>...</title>. ElementTree elements evaluate as falsy
    # when they have no children, even if they have .text — so use explicit
    # `is not None` rather than `or` chaining.
    title_elem = root.find('atom:title', _TRENDING_NS)
    if title_elem is None:
        title_elem = root.find('title')
    title = _trending_text(title_elem)
    if title:
        return title[:80]
    # Last resort: derive from the feed URL host.
    try:
        from urllib.parse import urlparse
        host = (urlparse(feed_url).netloc or feed_url)
        if host.startswith('www.'):
            host = host[4:]
        return host[:80] or 'Unknown'
    except Exception:
        return 'Unknown'


def _trending_fetch_one(feed_url: str) -> "list[dict]":
    """Fetch and parse a single feed. Returns [] on any failure."""
    import xml.etree.ElementTree as ET
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    try:
        # User-Agent header — some feeds (Reuters, Atom-based blogs) reject the
        # default Python urllib UA with 403.
        req = Request(
            feed_url,
            headers={
                'User-Agent': 'MiroShark/1.0 (+https://github.com/aaronjmars/MiroShark)',
                'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8',
            },
        )
        with urlopen(req, timeout=_TRENDING_FEED_TIMEOUT_SEC) as resp:
            # Cap read at 1 MB to avoid hostile/oversized feeds.
            body = resp.read(1024 * 1024)
    except (URLError, TimeoutError, OSError) as exc:
        logger.info(f"trending: feed fetch failed for {feed_url}: {exc}")
        return []

    if not body:
        return []

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        logger.info(f"trending: feed parse failed for {feed_url}: {exc}")
        return []

    source_name = _trending_extract_source(root, feed_url)

    # RSS 2.0: items live under <channel><item>. Atom: <entry> directly under
    # <feed>. Try both — empty list is fine.
    items = []
    channel = root.find('channel')
    if channel is not None:
        items.extend(channel.findall('item'))
    items.extend(root.findall('atom:entry', _TRENDING_NS))
    items.extend(root.findall('entry'))

    out = []
    for item in items:
        title = ''
        for child in item:
            if _trending_strip_localname(child.tag) == 'title':
                title = (child.text or '').strip()
                break
        url = _trending_extract_link(item)
        if not title or not url or not url.startswith('http'):
            continue
        published_raw = _trending_extract_published(item)
        published_at = _trending_parse_pubdate(published_raw)
        out.append({
            "title": title[:240],
            "url": url,
            "source_name": source_name,
            "published_at": (
                published_at.isoformat() if published_at else None
            ),
            "_sort_ts": (
                published_at.timestamp() if published_at else 0.0
            ),
        })
    return out


def _trending_fetch_all(feeds: "list[str]") -> "list[dict]":
    """Fetch every feed in parallel and merge the results, newest first."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not feeds:
        return []

    merged = []
    # Bound workers so a long feed list doesn't open hundreds of sockets.
    max_workers = min(len(feeds), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_trending_fetch_one, url): url for url in feeds}
        for fut in as_completed(futures):
            try:
                merged.extend(fut.result() or [])
            except Exception as exc:
                logger.info(
                    f"trending: worker failed for {futures[fut]}: {exc}"
                )

    # Drop duplicates by URL while preserving the newest occurrence.
    seen = {}
    for item in merged:
        prev = seen.get(item['url'])
        if prev is None or item['_sort_ts'] > prev['_sort_ts']:
            seen[item['url']] = item

    deduped = list(seen.values())
    deduped.sort(key=lambda i: i['_sort_ts'], reverse=True)

    # Strip the internal sort key before returning.
    for item in deduped:
        item.pop('_sort_ts', None)
    return deduped


@simulation_bp.route('/trending', methods=['GET'])
def trending_topics():
    """Return the most recent items across the configured RSS/Atom feeds.

    Query params:
        feeds:   optional comma-separated URL list to override TRENDING_FEEDS
        refresh: pass any truthy value to bypass the in-memory cache

    Response:
        {
          "success": true,
          "data": {
            "items": [
              {"title": "...", "url": "...", "source_name": "...",
               "published_at": "2026-04-21T13:45:00+00:00"}
            ],
            "feeds_used": [...],
            "cached": true,
            "fetched_at": "2026-04-21T13:50:00+00:00"
          }
        }

    On total failure (every feed errored), `items` is an empty array — the
    UI hides the panel silently. The endpoint never 5xx's the client.
    """
    try:
        client_ip = _client_ip()
        if _trending_rate_limited(client_ip):
            return jsonify({
                "success": True,
                "data": {
                    "items": [],
                    "feeds_used": [],
                    "cached": False,
                    "reason": "rate_limited",
                }
            }), 429

        # Resolve feeds: ?feeds=... overrides; otherwise env / default list.
        # User-supplied URLs pass through _trending_url_allowed to block SSRF
        # attempts (non-http(s) schemes, loopback, private / link-local hosts).
        # Env / default feeds are operator-controlled and trusted as-is.
        feeds_param = (request.args.get('feeds') or '').strip()
        if feeds_param:
            feeds = [
                u.strip() for u in feeds_param.split(',')
                if u.strip() and _trending_url_allowed(u.strip())
            ]
        else:
            feeds = _trending_get_feeds()

        # Defensive: cap at 12 feeds per request to bound work.
        if len(feeds) > 12:
            feeds = feeds[:12]

        if not feeds:
            return jsonify({
                "success": True,
                "data": {
                    "items": [],
                    "feeds_used": [],
                    "cached": False,
                    "reason": "no_feeds_configured",
                }
            })

        import time
        import hashlib
        cache_key = hashlib.sha1(
            ('|'.join(feeds)).encode('utf-8')
        ).hexdigest()

        force_refresh = (request.args.get('refresh') or '').lower() in (
            '1', 'true', 'yes'
        )

        now = time.monotonic()
        if not force_refresh:
            cached = _TRENDING_CACHE.get(cache_key)
            if cached and cached[0] > now:
                items = cached[1][:_TRENDING_ITEM_LIMIT]
                return jsonify({
                    "success": True,
                    "data": {
                        "items": items,
                        "feeds_used": feeds,
                        "cached": True,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                })

        items = _trending_fetch_all(feeds)
        # Cache even an empty list briefly so we don't retry every page load
        # when all upstreams are down — but use a shorter TTL (60s) for the
        # empty case so recovery is fast.
        ttl = _TRENDING_CACHE_TTL_SEC if items else 60
        _TRENDING_CACHE[cache_key] = (now + ttl, items)
        # Bound cache size — feed-list permutations can otherwise leak.
        if len(_TRENDING_CACHE) > 64:
            # Drop the oldest expiring entry.
            oldest_key = min(_TRENDING_CACHE, key=lambda k: _TRENDING_CACHE[k][0])
            _TRENDING_CACHE.pop(oldest_key, None)

        return jsonify({
            "success": True,
            "data": {
                "items": items[:_TRENDING_ITEM_LIMIT],
                "feeds_used": feeds,
                "cached": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        })

    except Exception as exc:
        logger.error(
            f"Failed to fetch trending topics: {exc}\n{traceback.format_exc()}"
        )
        # Never 5xx — the panel is non-essential and should silently disappear.
        return jsonify({
            "success": True,
            "data": {
                "items": [],
                "feeds_used": [],
                "cached": False,
                "reason": "internal_error",
            }
        })


# ============== Entity Reading Endpoints ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    Get all entities from the graph (filtered)

    Only returns nodes matching predefined entity types (nodes whose Labels are not just Entity)

    Query parameters:
        entity_types: Comma-separated list of entity types (optional, for further filtering)
        enrich: Whether to include related edge information (default true)
    """
    try:
        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        logger.info(f"Fetching graph entities: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to fetch graph entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """Get detailed information for a single entity"""
    locale = get_locale(request)
    try:
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        entity = reader.get_entity_with_context(graph_id, entity_uuid)

        if not entity:
            return jsonify({
                "success": False,
                "error": _t(f"Entity not found: {entity_uuid}", f"未找到实体:{entity_uuid}", locale)
            }), 404
        
        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get entity details: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Get all entities of a specified type"""
    try:
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Management Endpoints ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    Create a new simulation

    Note: Parameters like max_rounds are intelligently generated by LLM, no manual setup needed

    Request (JSON):
        {
            "project_id": "proj_xxxx",      // Required
            "graph_id": "miroshark_xxxx",    // Optional, fetched from project if not provided
            "enable_twitter": true,          // Optional, default true
            "enable_reddit": true,           // Optional, default true
            "enable_polymarket": false       // Optional, default false
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "miroshark_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": _t("Please provide project_id", "请提供 project_id", locale)
            }), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": _t(f"Project not found: {project_id}", f"未找到项目:{project_id}", locale)
            }), 404

        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": _t(
                    "Graph not yet built for this project, please call /api/graph/build first",
                    "该项目尚未构建图谱,请先调用 /api/graph/build",
                    locale,
                )
            }), 400

        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
            enable_polymarket=data.get('enable_polymarket', False),
            polymarket_market_count=data.get('polymarket_market_count', 1),
        )
        
        return jsonify({
            "success": True,
            "data": state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to create simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/branch-counterfactual', methods=['POST'])
def branch_counterfactual_simulation():
    """Branch a simulation with a narrative injection at a chosen round.

    Request (JSON)::

        {
            "parent_simulation_id": "sim_xxxx",     // required
            "injection_text":       "CEO resigns…", // required, <= 2000 chars
            "trigger_round":        24,             // required, >= 0
            "label":                "CEO resigns",  // optional
            "branch_id":            "ceo_resigns"   // optional preset branch id
        }

    Returns the new simulation's state (``parent_simulation_id`` + the
    ``config_diff.counterfactual`` block identifies the branch). The runner
    reads ``counterfactual_injection.json`` in the new sim's directory and
    prepends ``injection_text`` to every agent's observation prompt starting
    at ``trigger_round``.
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}
        parent_id = data.get("parent_simulation_id")
        injection = (data.get("injection_text") or "").strip()
        trigger = data.get("trigger_round")
        label = data.get("label")
        branch_id = data.get("branch_id")

        if not parent_id:
            return jsonify({"success": False, "error": _t(
                "parent_simulation_id is required",
                "缺少 parent_simulation_id",
                locale,
            )}), 400
        if not injection:
            return jsonify({"success": False, "error": _t(
                "injection_text is required",
                "缺少 injection_text",
                locale,
            )}), 400
        if len(injection) > 2000:
            return jsonify({"success": False, "error": _t(
                "injection_text must be <= 2000 chars",
                "injection_text 不能超过 2000 个字符",
                locale,
            )}), 400
        try:
            trigger_int = int(trigger)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": _t(
                "trigger_round must be an integer >= 0",
                "trigger_round 必须为大于等于 0 的整数",
                locale,
            )}), 400
        if trigger_int < 0:
            return jsonify({"success": False, "error": _t(
                "trigger_round must be >= 0",
                "trigger_round 必须 >= 0",
                locale,
            )}), 400

        manager = SimulationManager()
        state = manager.branch_counterfactual(
            parent_simulation_id=parent_id,
            injection_text=injection,
            trigger_round=trigger_int,
            label=label,
            branch_id=branch_id,
        )
        return jsonify({"success": True, "data": state.to_dict()})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to branch counterfactual: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@simulation_bp.route('/fork', methods=['POST'])
def fork_simulation():
    """
    Fork an existing simulation into a new child simulation.

    Copies agent profiles and configuration from the parent so the child
    is immediately ready to run.  Optionally accepts a new
    simulation_requirement to explore a different scenario with the same
    agent population.

    Request (JSON):
        {
            "parent_simulation_id": "sim_xxxx",        // Required
            "simulation_requirement": "What if..."     // Optional override
        }

    Returns:
        {
            "success": true,
            "data": { ...simulation state... }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        parent_simulation_id = data.get('parent_simulation_id')
        if not parent_simulation_id:
            return jsonify({
                "success": False,
                "error": _t(
                    "Please provide parent_simulation_id",
                    "请提供 parent_simulation_id",
                    locale,
                )
            }), 400

        simulation_requirement = data.get('simulation_requirement') or None

        manager = SimulationManager()
        state = manager.fork_simulation(
            parent_simulation_id=parent_simulation_id,
            simulation_requirement=simulation_requirement,
        )

        return jsonify({
            "success": True,
            "data": state.to_dict()
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404

    except Exception as e:
        logger.error(f"Failed to fork simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """
    Check if the simulation has been prepared

    Conditions checked:
    1. state.json exists and status is "ready"
    2. Required files exist: reddit_profiles.json, twitter_profiles.csv, simulation_config.json

    Note: Run scripts (run_*.py) remain in backend/scripts/ directory and are no longer copied to simulation directory

    Args:
        simulation_id: Simulation ID

    Returns:
        (is_prepared: bool, info: dict)
    """
    import os
    from ..config import Config
    
    simulation_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
    
    # Check if directory exists
    if not os.path.exists(simulation_dir):
        return False, {"reason": "Simulation directory does not exist"}
    
    # Required files list (excluding scripts, which are in backend/scripts/)
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]
    
    # Check if files exist
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files:
        return False, {
            "reason": "Missing required files",
            "missing_files": missing_files,
            "existing_files": existing_files
        }
    
    # Check status in state.json
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        
        # Detailed logging
        logger.debug(f"Checking simulation preparation status: {simulation_id}, status={status}, config_generated={config_generated}")
        
        # If config_generated=True and files exist, consider preparation complete
        # The following statuses indicate preparation is complete:
        # - ready: preparation complete, can run
        # - preparing: if config_generated=True it means completed
        # - running: currently running, preparation was done long ago
        # - completed: run finished, preparation was done long ago
        # - stopped: stopped, preparation was done long ago
        # - failed: run failed (but preparation is complete)
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed", "paused"]
        if status in prepared_statuses and config_generated:
            # Get file statistics
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")

            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0
            
            # If status is preparing but files are complete, auto-update status to ready
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Auto-updated simulation status: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"Failed to auto-update status: {e}")
            
            logger.info(f"Simulation {simulation_id} check result: preparation complete (status={status}, config_generated={config_generated})")
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files
            }
        else:
            logger.warning(f"Simulation {simulation_id} check result: not prepared (status={status}, config_generated={config_generated})")
            return False, {
                "reason": f"Status not in prepared list or config_generated is false: status={status}, config_generated={config_generated}",
                "status": status,
                "config_generated": config_generated
            }
            
    except Exception as e:
        return False, {"reason": f"Failed to read state file: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
    Prepare simulation environment (async task, LLM intelligently generates all parameters)

    This is a time-consuming operation. The endpoint returns task_id immediately.
    Use GET /api/simulation/prepare/status to query progress.

    Features:
    - Auto-detects completed preparation work to avoid redundant generation
    - If already prepared, returns existing results directly
    - Supports forced regeneration (force_regenerate=true)

    Steps:
    1. Check if preparation work has already been completed
    2. Read and filter entities from knowledge graph
    3. Generate Wonderwall Agent Profile for each entity (with retry mechanism)
    4. LLM intelligently generates simulation configuration (with retry mechanism)
    5. Save configuration files and preset scripts

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                   // Required, simulation ID
            "entity_types": ["Student", "PublicFigure"],  // Optional, specify entity types
            "use_llm_for_profiles": true,                 // Optional, whether to use LLM for profile generation
            "parallel_profile_count": 5,                  // Optional, parallel profile generation count, default 5
            "force_regenerate": false                     // Optional, force regeneration, default false
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",           // Returned for new tasks
                "status": "preparing|ready",
                "message": "Preparation task started | Preparation already complete",
                "already_prepared": true|false    // Whether preparation is complete
            }
        }
    """
    import threading
    from ..models.task import TaskManager, TaskStatus

    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err

        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404
        
        # Check if force regeneration is requested
        force_regenerate = data.get('force_regenerate', False)
        logger.info(f"Processing /prepare request: simulation_id={simulation_id}, force_regenerate={force_regenerate}")
        
        # Check if already prepared (avoid redundant generation)
        if not force_regenerate:
            logger.debug(f"Checking if simulation {simulation_id} is already prepared...")
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            logger.debug(f"Check result: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"Simulation {simulation_id} already prepared, skipping redundant generation")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": "Preparation already complete, no need to regenerate",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"Simulation {simulation_id} not yet prepared, starting preparation task")
        
        # Get required information from project
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": _t(f"Project not found: {state.project_id}", f"未找到项目:{state.project_id}", locale)
            }), 404

        # Get simulation requirement
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": _t(
                    "Project missing simulation requirement description (simulation_requirement)",
                    "项目缺少模拟需求描述(simulation_requirement)",
                    locale,
                )
            }), 400
        
        # Get document text
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        
        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)
        
        # ========== Get GraphStorage (capture reference before background task starts) ==========
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized — check Neo4j connection")

        # ========== Synchronously get entity count (before background task starts) ==========
        # This allows the frontend to get the expected total Agent count immediately after calling prepare
        try:
            logger.info(f"Synchronously fetching entity count: graph_id={state.graph_id}")
            reader = EntityReader(storage)
            # Quick entity read (no edge info needed, just counting)
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # Skip edge info for faster processing
            )
            # Save entity count to state (for frontend to fetch immediately)
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"Expected entity count: {filtered_preview.filtered_count}, types: {filtered_preview.entity_types}")
        except Exception as e:
            logger.warning(f"Failed to synchronously get entity count (will retry in background task): {e}")
            # Failure does not affect subsequent flow, background task will re-fetch
        
        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )
        
        # Update simulation state (includes pre-fetched entity count)
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)
        
        # Define background task
        from ..utils.i18n import use_locale
        thread_locale = locale  # capture for the worker thread

        def run_prepare():
            with use_locale(thread_locale):
                _run_prepare_impl()

        def _run_prepare_impl():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Starting simulation environment preparation..."
                )
                
                # Prepare simulation (with progress callback)
                # Store stage progress details
                stage_details = {}
                
                def progress_callback(stage, progress, message, **kwargs):
                    # Calculate overall progress
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }
                    
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    
                    # Build detailed progress info
                    stage_names = {
                        "reading": "Reading graph entities",
                        "generating_profiles": "Generating Agent profiles",
                        "generating_config": "Generating simulation config",
                        "copying_scripts": "Preparing simulation scripts"
                    }
                    
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    
                    # Update stage details
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }
                    
                    # Build detailed progress info
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }
                    
                    # Build concise message
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    
                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )
                
                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count,
                    storage=storage
                )
                
                # Task complete
                task_manager.complete_task(
                    task_id,
                    result=result_state.to_simple_dict()
                )
                
            except Exception as e:
                logger.error(f"Failed to prepare simulation: {str(e)}")
                task_manager.fail_task(task_id, str(e))
                
                # Update simulation status to failed
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)
        
        # Start background thread
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": "Preparation task started, query progress via /api/simulation/prepare/status",
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # Expected total Agent count
                "entity_types": state.entity_types  # Entity type list
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to start preparation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    Query preparation task progress

    Supports two query methods:
    1. Query ongoing task progress by task_id
    2. Check if preparation is already complete by simulation_id

    Request (JSON):
        {
            "task_id": "task_xxxx",          // Optional, task_id returned from prepare
            "simulation_id": "sim_xxxx"      // Optional, simulation ID (to check completed preparation)
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // Whether preparation is already complete
                "prepare_info": {...}            // Detailed info when preparation is complete
            }
        }
    """
    from ..models.task import TaskManager

    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        if simulation_id:
            try:
                validate_simulation_id(simulation_id)
            except ValueError as exc:
                return jsonify({"success": False, "error": str(exc)}), 400

        # If simulation_id is provided, first check if preparation is complete
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": "Preparation work already complete",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # If no task_id, return error
        if not task_id:
            if simulation_id:
                # Has simulation_id but not yet prepared
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": "Preparation not yet started, call /api/simulation/prepare to begin",
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": _t(
                    "Please provide task_id or simulation_id",
                    "请提供 task_id 或 simulation_id",
                    locale,
                )
            }), 400

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # Task not found, but if simulation_id is provided, check if preparation is complete
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": "Task completed (preparation already exists)",
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": _t(f"Task not found: {task_id}", f"未找到任务:{task_id}", locale)
            }), 404

        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Get simulation status"""
    locale = get_locale(request)
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404
        
        result = state.to_dict()
        
        # If simulation is ready, append run instructions
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    List all simulations

    Query parameters:
        project_id: Filter by project ID (optional)
    """
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to list simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> str:
    """
    Get the latest report_id corresponding to a simulation

    Traverses the reports directory to find reports matching the simulation_id.
    If multiple exist, returns the most recent one (sorted by created_at).

    Args:
        simulation_id: Simulation ID

    Returns:
        report_id or None
    """
    import json
    
    # reports directory path: backend/uploads/reports
    # __file__ is app/api/simulation.py, need to go up two levels to backend/
    reports_dir = os.path.join(os.path.dirname(__file__), '../../uploads/reports')
    if not os.path.exists(reports_dir):
        return None
    
    matching_reports = []
    
    try:
        for report_folder in os.listdir(reports_dir):
            report_path = os.path.join(reports_dir, report_folder)
            if not os.path.isdir(report_path):
                continue
            
            meta_file = os.path.join(report_path, "meta.json")
            if not os.path.exists(meta_file):
                continue
            
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                if meta.get("simulation_id") == simulation_id:
                    matching_reports.append({
                        "report_id": meta.get("report_id"),
                        "created_at": meta.get("created_at", ""),
                        "status": meta.get("status", "")
                    })
            except Exception:
                continue
        
        if not matching_reports:
            return None
        
        # Sort by creation time descending, return the most recent
        matching_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matching_reports[0].get("report_id")
        
    except Exception as e:
        logger.warning(f"Failed to find report for simulation {simulation_id}: {e}")
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    Get historical simulation list (with project details)

    Used for homepage historical project display, returns simulation list with rich information including project name, description, etc.

    Query parameters:
        limit: Return count limit (default 20)

    Returns:
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "WHU Public Opinion Analysis",
                    "simulation_requirement": "If Wuhan University publishes...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # Enrich simulation data, read only from Simulation files
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # Get simulation config info (read simulation_requirement from simulation_config.json)
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # Recommended rounds (fallback value)
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # Get run status (read user-set actual rounds from run_state.json)
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # Use user-set total_rounds, fall back to recommended rounds
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # Get associated project file list (max 3)
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {
                        "filename": f.get("filename", "Unknown file"),
                        "url": f.get("url", ""),
                        "saved_filename": f.get("saved_filename", ""),
                    }
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # Get associated report_id (find the latest report for this simulation)
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            # Propagate fork lineage fields (already in to_dict but ensure they surface)
            sim_dict.setdefault("parent_simulation_id", sim.parent_simulation_id)

            # Add version number
            sim_dict["version"] = "v1.0.2"

            # Format date
            sim_dict["created_date"] = (sim_dict.get("created_at") or "")[:10]

            # Include resolution data if it exists
            resolution_path = os.path.join(
                Config.WONDERWALL_SIMULATION_DATA_DIR, sim.simulation_id, "resolution.json"
            )
            if os.path.exists(resolution_path):
                try:
                    with open(resolution_path, 'r', encoding='utf-8') as _rf:
                        sim_dict["resolution"] = json.load(_rf)
                except Exception:
                    sim_dict["resolution"] = None
            else:
                sim_dict["resolution"] = None

            # Include quality diagnostics if cached
            quality_path = os.path.join(
                Config.WONDERWALL_SIMULATION_DATA_DIR, sim.simulation_id, "quality.json"
            )
            if os.path.exists(quality_path):
                try:
                    with open(quality_path, 'r', encoding='utf-8') as _qf:
                        sim_dict["quality"] = json.load(_qf)
                except Exception:
                    sim_dict["quality"] = None
            else:
                sim_dict["quality"] = None

            enriched_simulations.append(sim_dict)

        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    Get simulation Agent Profiles

    Query parameters:
        platform: Platform type (reddit/twitter, default reddit)
    """
    try:
        platform = request.args.get('platform', 'reddit')
        
        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to get profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    Get simulation Agent Profiles in real-time (for viewing progress during generation)

    Differences from /profiles endpoint:
    - Reads files directly, bypassing SimulationManager
    - Suitable for real-time viewing during generation
    - Returns additional metadata (e.g., file modification time, whether generation is in progress)

    Query parameters:
        platform: Platform type (reddit/twitter, default reddit)

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // Expected total (if available)
                "is_generating": true,  // Whether generation is in progress
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    import json
    import csv
    from datetime import datetime

    locale = get_locale(request)
    try:
        platform = request.args.get('platform', 'reddit')

        # Get simulation directory
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        # Determine file path
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")

        # Check if file exists
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # Get file modification time
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read profiles file (may be in the process of writing): {e}")
                profiles = []
        
        # Check if generation is in progress (determined by state.json)
        is_generating = False
        total_expected = None

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception:
                pass
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get profiles in real-time: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    Get simulation configuration in real-time (for viewing progress during generation)

    Differences from /config endpoint:
    - Reads files directly, bypassing SimulationManager
    - Suitable for real-time viewing during generation
    - Returns additional metadata (e.g., file modification time, whether generation is in progress)
    - Can return partial info even if config generation is not yet complete

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // Whether generation is in progress
                "generation_stage": "generating_config",  // Current generation stage
                "config": {...}  // Config content (if available)
            }
        }
    """
    import json
    from datetime import datetime

    locale = get_locale(request)
    try:
        # Get simulation directory
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        # Config file path
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # Check if file exists
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # Get file modification time
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read config file (may be in the process of writing): {e}")
                config = None
        
        # Check if generation is in progress (determined by state.json)
        is_generating = False
        generation_stage = None
        config_generated = False
        sim_status = ""
        config_error = None

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    sim_status = state_data.get("status", "")
                    is_generating = sim_status == "preparing"
                    config_generated = state_data.get("config_generated", False)

                    # Expose error when generation failed
                    if sim_status == "failed":
                        config_error = state_data.get("error") or "Config generation failed"

                    # Determine current stage
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif sim_status == "ready":
                        generation_stage = "completed"
            except Exception:
                pass

        # Build response data
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "status": sim_status,
            "config_error": config_error,
            "config": config
        }
        
        # If config exists, extract some key statistics
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get config in real-time: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/retry', methods=['POST'])
def retry_simulation_config(simulation_id: str):
    """
    Retry config generation only (profiles already exist).

    Resets the simulation status to 'preparing', then regenerates the
    simulation_config.json from existing profiles and entities without
    repeating the (slow) profile generation step.

    Returns:
        { "success": true, "data": { "simulation_id": "...", "status": "preparing" } }
    """
    import threading
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config

    locale = get_locale(request)
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        # Profiles must exist before we can retry config generation
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        profiles_exist = (
            os.path.exists(os.path.join(sim_dir, "reddit_profiles.json")) or
            os.path.exists(os.path.join(sim_dir, "twitter_profiles.csv"))
        )
        if not profiles_exist:
            return jsonify({
                "success": False,
                "error": _t(
                    "Agent profiles not found — run /prepare first",
                    "未找到 Agent 配置文件 — 请先运行 /prepare",
                    locale,
                )
            }), 400

        # Get project data needed for config generation
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({"success": False, "error": _t(
                f"Project not found: {state.project_id}",
                f"未找到项目:{state.project_id}",
                locale,
            )}), 404

        simulation_requirement = project.simulation_requirement or ""
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({"success": False, "error": _t(
                "GraphStorage not initialized",
                "GraphStorage 尚未初始化",
                locale,
            )}), 500

        # Reset state so the frontend polling loop sees "preparing" again
        state.status = SimulationStatus.PREPARING
        state.config_generated = False
        state.error = None
        manager._save_simulation_state(state)

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_config_retry",
            metadata={"simulation_id": simulation_id}
        )

        from ..utils.i18n import use_locale
        thread_locale = locale  # capture for the worker thread

        def run_config_retry():
            with use_locale(thread_locale):
                _run_config_retry_impl()

        def _run_config_retry_impl():
            try:
                task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=0,
                                         message="Retrying config generation...")

                # Re-read entities for config generation context
                reader = EntityReader(storage)
                filtered = reader.filter_defined_entities(
                    graph_id=state.graph_id,
                    enrich_with_edges=True
                )

                config_generator = SimulationConfigGenerator()
                sim_params = config_generator.generate_config(
                    simulation_id=simulation_id,
                    project_id=state.project_id,
                    graph_id=state.graph_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    entities=filtered.entities,
                    enable_twitter=state.enable_twitter,
                    enable_reddit=state.enable_reddit,
                    polymarket_market_count=state.polymarket_market_count,
                )

                config_path = os.path.join(sim_dir, "simulation_config.json")
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(sim_params.to_json())

                # Mark as complete
                reload_state = manager.get_simulation(simulation_id)
                if reload_state:
                    reload_state.config_generated = True
                    reload_state.config_reasoning = sim_params.generation_reasoning
                    reload_state.status = SimulationStatus.READY
                    reload_state.error = None
                    manager._save_simulation_state(reload_state)

                task_manager.complete_task(task_id, result={"simulation_id": simulation_id})
                logger.info(f"Config retry complete for {simulation_id}")

            except Exception as e:
                logger.error(f"Config retry failed for {simulation_id}: {e}")
                task_manager.fail_task(task_id, str(e))
                failed_state = manager.get_simulation(simulation_id)
                if failed_state:
                    failed_state.status = SimulationStatus.FAILED
                    failed_state.error = str(e)
                    manager._save_simulation_state(failed_state)

        thread = threading.Thread(target=run_config_retry, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": "Config generation retry started"
            }
        })

    except Exception as e:
        logger.error(f"Failed to start config retry: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    Get simulation configuration (complete configuration intelligently generated by LLM)

    Returns containing:
        - time_config: Time configuration (simulation duration, rounds, peak/off-peak hours)
        - agent_configs: Activity configuration for each agent (activity level, posting frequency, stance, etc.)
        - event_config: Event configuration (initial posts, hot topics)
        - platform_configs: Platform configuration
        - generation_reasoning: LLM configuration reasoning explanation
    """
    locale = get_locale(request)
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)

        if not config:
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation configuration does not exist, please call /prepare endpoint first",
                    "模拟配置不存在,请先调用 /prepare 端点",
                    locale,
                )
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/project/<project_id>/files/<saved_filename>/download', methods=['GET'])
def download_project_file(project_id: str, saved_filename: str):
    """Stream a project's uploaded file back to the browser by its
    UUID-based saved_filename. Used by the History modal's file list
    so users can re-download originals they ingested earlier."""
    locale = get_locale(request)
    try:
        # Reject path-traversal attempts — saved_filename is supposed
        # to be a single segment, not a path.
        if '/' in saved_filename or '\\' in saved_filename or '..' in saved_filename:
            return jsonify({"success": False, "error": _t("Invalid filename", "无效的文件名", locale)}), 400

        files_dir = os.path.abspath(
            ProjectManager._get_project_files_dir(project_id)
        )
        file_path = os.path.abspath(os.path.join(files_dir, saved_filename))
        # Defense-in-depth: ensure resolved path is still inside files_dir
        if not file_path.startswith(files_dir + os.sep):
            return jsonify({"success": False, "error": _t("Invalid filename", "无效的文件名", locale)}), 400
        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": _t("File not found", "未找到文件", locale)}), 404

        # Look up the original filename from the project record so the
        # browser saves it with a meaningful name, not the UUID.
        download_name = saved_filename
        try:
            project = ProjectManager.get_project(project_id)
            if project and getattr(project, 'files', None):
                for f in project.files:
                    if f.get('saved_filename') == saved_filename:
                        download_name = f.get('filename') or saved_filename
                        break
        except Exception:
            pass

        return send_file(file_path, as_attachment=True, download_name=download_name)

    except Exception as e:
        logger.error(f"Failed to download project file: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """Download simulation configuration file"""
    locale = get_locale(request)
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": _t(
                    "Configuration file does not exist, please call /prepare endpoint first",
                    "配置文件不存在,请先调用 /prepare 端点",
                    locale,
                )
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"Failed to download configuration: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    Download simulation run script file (common scripts, located at backend/scripts/)

    Options for script_name:
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    locale = get_locale(request)
    try:
        # Scripts located at backend/scripts/ directory
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))

        # Validate script name
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py",
            "run_parallel_simulation.py",
            "action_logger.py"
        ]

        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": _t(
                    f"Unknown script: {script_name}, options: {allowed_scripts}",
                    f"未知脚本:{script_name},可选项:{allowed_scripts}",
                    locale,
                )
            }), 400

        script_path = os.path.join(scripts_dir, script_name)

        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": _t(
                    f"Script file does not exist: {script_name}",
                    f"脚本文件不存在:{script_name}",
                    locale,
                )
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"Failed to download script: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Profile Generation Endpoint (standalone use) ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    Directly generate Wonderwall Agent Profile from graph (without creating simulation)

    Request (JSON):
        {
            "graph_id": "miroshark_xxxx",     // Required
            "entity_types": ["Student"],      // Optional
            "use_llm": true,                  // Optional
            "platform": "reddit"              // Optional
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": _t("Please provide graph_id", "请提供 graph_id", locale)
            }), 400

        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )

        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": _t(
                    "No matching entities found",
                    "未找到匹配的实体",
                    locale,
                )
            }), 400
        
        generator = WonderwallProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to generate profile: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Run Control Endpoints ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
    Start running simulation

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",          // Required, simulation ID
            "platform": "parallel",                // Optional: twitter / reddit / parallel (default)
            "max_rounds": 100,                     // Optional: maximum simulation rounds, used to truncate overly long simulations
            "enable_graph_memory_update": false,   // Optional: whether to dynamically update agent activity to knowledge graph memory
            "force": false                         // Optional: force restart (will stop running simulation and clean up logs)
        }

    About the force parameter:
        - When enabled, if simulation is running or completed, it will first stop and clean up run logs
        - Cleanup includes: run_state.json, actions.jsonl, simulation.log, etc.
        - Will not clean up configuration files (simulation_config.json) and profile files
        - Suitable for scenarios requiring simulation re-run

    About enable_graph_memory_update:
        - When enabled, all agent activities during simulation (posting, commenting, liking, etc.) will be updated to knowledge graph in real-time
        - This allows the graph to "remember" the simulation process, for subsequent analysis or AI conversation
        - Requires the associated project to have a valid graph_id
        - Uses batch update mechanism to reduce API call frequency

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "process_pid": 12345,
                "twitter_running": true,
                "reddit_running": true,
                "started_at": "2025-12-01T10:00:00",
                "graph_memory_update_enabled": true,  // Whether graph memory update is enabled
                "force_restarted": true               // Whether it was a forced restart
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # Optional: maximum simulation rounds
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # Optional: whether to enable graph memory update
        force = data.get('force', False)  # Optional: force restart
        resume = data.get('resume', False)  # Optional: resume from last round

        # If resume requested, read the last round from run_state
        start_round = 0
        if resume:
            existing_state = SimulationRunner.get_run_state(simulation_id)
            if existing_state and existing_state.current_round > 0:
                start_round = existing_state.current_round
                logger.info(f"Resuming simulation {simulation_id} from round {start_round}")

        # Validate max_rounds parameter
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": _t(
                            "max_rounds must be a positive integer",
                            "max_rounds 必须为正整数",
                            locale,
                        )
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": _t(
                        "max_rounds must be a valid integer",
                        "max_rounds 必须是有效的整数",
                        locale,
                    )
                }), 400

        if platform not in ['twitter', 'reddit', 'polymarket', 'parallel']:
            return jsonify({
                "success": False,
                "error": _t(
                    f"Invalid platform type: {platform}, options: twitter/reddit/polymarket/parallel",
                    f"无效的平台类型:{platform},可选项:twitter/reddit/polymarket/parallel",
                    locale,
                )
            }), 400

        enable_cross_platform = data.get('enable_cross_platform', True)

        # Check if simulation is ready
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        force_restarted = False
        
        # Smart status handling: if preparation is complete, allow restart
        if state.status != SimulationStatus.READY:
            # Check if preparation is complete
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                # Preparation complete, check if there is a running process
                if state.status == SimulationStatus.RUNNING:
                    # Check if simulation process is actually running
                    run_state = SimulationRunner.get_run_state(simulation_id)
                    if run_state and run_state.runner_status.value == "running":
                        # Process is actually running
                        if force:
                            # Force mode: stopping running simulation
                            logger.info(f"Force mode: stopping running simulation {simulation_id}")
                            try:
                                SimulationRunner.stop_simulation(simulation_id)
                            except Exception as e:
                                logger.warning(f"Warning while stopping simulation: {str(e)}")
                        else:
                            return jsonify({
                                "success": False,
                                "error": _t(
                                    "Simulation is running, please call /stop endpoint to stop first, or use force=true to force restart",
                                    "模拟正在运行,请先调用 /stop 端点停止,或使用 force=true 强制重启",
                                    locale,
                                )
                            }), 400

                # If force mode (and not resuming), clean up run logs
                if force and not resume:
                    logger.info(f"Force mode: cleaning simulation logs {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        logger.warning(f"Warning while cleaning logs: {cleanup_result.get('errors')}")
                    force_restarted = True

                # Process does not exist or has ended, reset status to ready
                logger.info(f"Simulation {simulation_id} preparation complete, reset status to ready (previous status: {state.status.value})")
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # Preparation incomplete
                return jsonify({
                    "success": False,
                    "error": _t(
                        f"Simulation not ready, current status: {state.status.value}, please call /prepare endpoint first",
                        f"模拟尚未就绪,当前状态:{state.status.value},请先调用 /prepare 端点",
                        locale,
                    )
                }), 400
        
        # Get graph ID (for graph memory update)
        graph_id = None
        if enable_graph_memory_update:
            # Get graph_id from simulation state or project
            graph_id = state.graph_id
            if not graph_id:
                # Try to get from project
                project = ProjectManager.get_project(state.project_id)
                if project:
                    graph_id = project.graph_id
            
            if not graph_id:
                return jsonify({
                    "success": False,
                    "error": _t(
                        "Enabling graph memory update requires a valid graph_id, please ensure the project has built a graph",
                        "启用图谱记忆更新需要有效的 graph_id,请确保项目已构建图谱",
                        locale,
                    )
                }), 400
            
            logger.info(f"Enable graph memory update: simulation_id={simulation_id}, graph_id={graph_id}")
        
        # Get storage for graph memory update if enabled
        sim_storage = None
        if enable_graph_memory_update:
            sim_storage = current_app.extensions.get('neo4j_storage')

        # Start simulation
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            graph_id=graph_id,
            storage=sim_storage,
            start_round=start_round,
            enable_cross_platform=enable_cross_platform,
        )
        
        # Update simulation status
        state.status = SimulationStatus.RUNNING
        manager._save_simulation_state(state)
        
        response_data = run_state.to_dict()
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        response_data['resumed'] = resume and start_round > 0
        if start_round > 0:
            response_data['resumed_from_round'] = start_round
        if enable_graph_memory_update:
            response_data['graph_id'] = graph_id
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
    Stop simulation

    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // Required, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err

        run_state = SimulationRunner.stop_simulation(simulation_id)
        
        # Update simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to stop simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Real-time Status Monitoring Endpoints ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    Get simulation real-time running status (for frontend polling)

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get running status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    Get simulation detailed running status (including all actions)

    For frontend real-time display

    Query parameters:
        platform: Filter platform (twitter/reddit, optional)

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # All actions on Twitter platform
                "reddit_actions": [...]    # All actions on Reddit platform
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })
        
        # Get complete action list
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )
        
        # Get actions by platform
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []
        
        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []
        
        # Get current round actions (recent_actions only shows latest round)
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []
        
        # Get basic status information
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions only shows current latest round content for both platforms
        result["recent_actions"] = [a.to_dict() for a in recent_actions]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get detailed status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
    Get agent action history during simulation

    Query parameters:
        limit: Return count (default 100)
        offset: Offset (default 0)
        platform: Filter platform (twitter/reddit)
        agent_id: Filter Agent ID
        round_num: Filter round

    Returns:
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)
        
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get action history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    Get simulation timeline (summarized by round)

    For frontend progress bar and timeline view

    Query parameters:
        start_round: Start round (default 0)
        end_round: End round (default all)

    Returns summary info per round
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)
        
        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )
        
        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get timeline: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
    Get statistics for each agent

    For frontend agent activity ranking, action distribution, etc.
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get agent statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Influence Leaderboard ==============


def _compute_influence_ranked(simulation_id, top_n=None):
    """
    Compute agent influence scores from simulation action JSONL logs.

    Reads twitter/actions.jsonl, reddit/actions.jsonl, and polymarket/actions.jsonl,
    then ranks agents by a composite influence score:

        score = engagement_received * 3 + follows_received * 2
                + platform_count * 5 + posts_created

    Returns a list of ranked agent dicts (1-based rank), optionally truncated to top_n.
    Returns an empty list if the simulation directory does not exist.
    """
    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
    if not os.path.exists(sim_dir):
        return []

    ENGAGEMENT_TYPES = frozenset({
        'LIKE_POST', 'REPOST', 'QUOTE_POST', 'LIKE_COMMENT',
        'CREATE_COMMENT',
    })

    agents = {}

    def _get_or_create(name):
        if name not in agents:
            agents[name] = {
                'agent_name': name,
                'posts_created': 0,
                'engagement_received': 0,
                'follows_received': 0,
                'platforms': set(),
            }
        return agents[name]

    for platform in ('twitter', 'reddit', 'polymarket'):
        actions_path = os.path.join(sim_dir, platform, 'actions.jsonl')
        if not os.path.exists(actions_path):
            continue

        with open(actions_path, 'r', encoding='utf-8') as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if event.get('event_type') in (
                    'simulation_start', 'round_start', 'round_end', 'simulation_end'
                ):
                    continue

                agent_name = event.get('agent_name')
                if not agent_name:
                    continue

                actor = _get_or_create(agent_name)
                actor['platforms'].add(platform)

                action_type = event.get('action_type', '')
                args = event.get('action_args') or {}

                if action_type == 'CREATE_POST':
                    actor['posts_created'] += 1

                elif action_type in ENGAGEMENT_TYPES:
                    author = (
                        args.get('post_author_name')
                        or args.get('original_author_name')
                    )
                    if author and author != agent_name:
                        _get_or_create(author)['engagement_received'] += 1

                elif action_type == 'FOLLOW':
                    target = args.get('target_user_name')
                    if target:
                        _get_or_create(target)['follows_received'] += 1

    ranked = []
    for a in agents.values():
        platform_count = len(a['platforms'])
        score = (
            a['engagement_received'] * 3
            + a['follows_received'] * 2
            + platform_count * 5
            + a['posts_created']
        )
        ranked.append({
            'agent_name': a['agent_name'],
            'posts_created': a['posts_created'],
            'engagement_received': a['engagement_received'],
            'follows_received': a['follows_received'],
            'platform_count': platform_count,
            'platforms': sorted(a['platforms']),
            'influence_score': score,
        })

    ranked.sort(key=lambda x: x['influence_score'], reverse=True)

    for i, entry in enumerate(ranked):
        entry['rank'] = i + 1

    return ranked[:top_n] if top_n else ranked


@simulation_bp.route('/<simulation_id>/influence', methods=['GET'])
def get_influence_leaderboard(simulation_id: str):
    """
    Compute agent influence scores from simulation action JSONL logs.
    Returns the top 20 agents sorted by score descending.
    """
    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        ranked = _compute_influence_ranked(simulation_id, top_n=20)

        return jsonify({
            "success": True,
            "data": {
                "agents": ranked,
                "total_agents": len(ranked),
            }
        })

    except Exception as e:
        logger.error(f"Failed to compute influence leaderboard: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/belief-drift', methods=['GET'])
def get_belief_drift(simulation_id: str):
    """
    Compute per-round belief distribution from the simulation's trajectory.json.

    Returns bullish/neutral/bearish agent percentages per round, the first
    consensus round (where one stance exceeds 50%), and a plain-English summary.
    Requires trajectory.json generated by the belief tracking system.
    """
    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        trajectory_path = os.path.join(sim_dir, "trajectory.json")
        if not os.path.exists(trajectory_path):
            return jsonify({
                "success": True,
                "data": None,
                "message": (
                    "No belief trajectory data available. The simulation may not have "
                    "used the belief tracking system."
                )
            })

        with open(trajectory_path, 'r', encoding='utf-8') as f:
            traj = json.load(f)

        snapshots = traj.get("snapshots", [])
        topics = traj.get("topics", [])

        rounds = []
        bullish = []
        neutral = []
        bearish = []

        for snap in snapshots:
            round_num = snap.get("round_num", 0)
            belief_positions = snap.get("belief_positions", {})

            if not belief_positions:
                continue

            # Average each agent's stance across all tracked topics
            agent_stances = []
            for positions in belief_positions.values():
                if positions:
                    avg = sum(positions.values()) / len(positions)
                    agent_stances.append(avg)

            if not agent_stances:
                continue

            total = len(agent_stances)
            n_bullish = sum(1 for s in agent_stances if s > 0.2)
            n_bearish = sum(1 for s in agent_stances if s < -0.2)
            n_neutral = total - n_bullish - n_bearish

            rounds.append(round_num)
            bullish.append(round(n_bullish / total * 100, 1))
            neutral.append(round(n_neutral / total * 100, 1))
            bearish.append(round(n_bearish / total * 100, 1))

        # First round where one stance exceeds 50% of agents
        consensus_round = None
        consensus_stance = None
        for i, r in enumerate(rounds):
            if bullish[i] > 50:
                consensus_round = r
                consensus_stance = "bullish"
                break
            if bearish[i] > 50:
                consensus_round = r
                consensus_stance = "bearish"
                break

        def _dominant(b, n, be):
            if b >= n and b >= be:
                return "bullish"
            if be >= n and be >= b:
                return "bearish"
            return "neutral"

        if rounds:
            first_stance = _dominant(bullish[0], neutral[0], bearish[0])
            last_stance = _dominant(bullish[-1], neutral[-1], bearish[-1])
            if consensus_round is not None:
                summary = (
                    f"Consensus shifted from {first_stance} (round {rounds[0]}) "
                    f"to {consensus_stance} majority (round {consensus_round}) "
                    f"and held through the final round."
                )
            elif first_stance == last_stance:
                summary = (
                    f"Agents remained predominantly {first_stance} "
                    f"throughout all {len(rounds)} rounds."
                )
            else:
                summary = (
                    f"Collective stance shifted from {first_stance} (round {rounds[0]}) "
                    f"to {last_stance} by the final round (round {rounds[-1]})."
                )
        else:
            summary = "Insufficient data to compute belief drift."

        return jsonify({
            "success": True,
            "data": {
                "rounds": rounds,
                "bullish": bullish,
                "neutral": neutral,
                "bearish": bearish,
                "topics": topics,
                "consensus_round": consensus_round,
                "consensus_stance": consensus_stance,
                "total_rounds": len(rounds),
                "summary": summary,
            }
        })

    except Exception as e:
        logger.error(f"Failed to compute belief drift: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Counterfactual Explorer ("What If?") ==============


def _drift_from_positions_by_agent(snapshots, allowed_agent_ids=None):
    """Compute per-round bullish/neutral/bearish % from trajectory snapshots.

    If allowed_agent_ids is None, includes every agent. Otherwise only agents
    whose stringified id is in the set are counted.

    Returns a dict with the same shape as the belief-drift endpoint plus
    a `final_bullish_pct` convenience key.
    """
    rounds = []
    bullish = []
    neutral = []
    bearish = []

    for snap in snapshots:
        belief_positions = snap.get("belief_positions") or {}
        if not belief_positions:
            continue

        agent_stances = []
        for aid, positions in belief_positions.items():
            if allowed_agent_ids is not None and str(aid) not in allowed_agent_ids:
                continue
            if positions:
                agent_stances.append(sum(positions.values()) / len(positions))

        if not agent_stances:
            continue

        total = len(agent_stances)
        n_bullish = sum(1 for s in agent_stances if s > 0.2)
        n_bearish = sum(1 for s in agent_stances if s < -0.2)
        n_neutral = total - n_bullish - n_bearish

        rounds.append(snap.get("round_num", 0))
        bullish.append(round(n_bullish / total * 100, 1))
        neutral.append(round(n_neutral / total * 100, 1))
        bearish.append(round(n_bearish / total * 100, 1))

    consensus_round = None
    consensus_stance = None
    for i, r in enumerate(rounds):
        if bullish[i] > 50:
            consensus_round = r
            consensus_stance = "bullish"
            break
        if bearish[i] > 50:
            consensus_round = r
            consensus_stance = "bearish"
            break

    return {
        "rounds": rounds,
        "bullish": bullish,
        "neutral": neutral,
        "bearish": bearish,
        "consensus_round": consensus_round,
        "consensus_stance": consensus_stance,
        "final_bullish_pct": bullish[-1] if bullish else None,
        "final_neutral_pct": neutral[-1] if neutral else None,
        "final_bearish_pct": bearish[-1] if bearish else None,
        "agent_count": None,
    }


@simulation_bp.route('/<simulation_id>/counterfactual', methods=['GET'])
def get_counterfactual_drift(simulation_id: str):
    """
    Recompute belief drift with a subset of agents excluded ("What If?" analysis).

    Query params:
        exclude_agents: comma-separated agent usernames to remove from the analysis.

    Returns both the original drift and the counterfactual drift so the UI can
    render them on shared axes, plus the headline `delta_final_bullish` which is
    the finding researchers typically cite (e.g. "removing Agent X shifted
    consensus by 23 points").

    Pure data transform over trajectory.json — no LLM calls, no re-simulation.
    """
    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        trajectory_path = os.path.join(sim_dir, "trajectory.json")
        if not os.path.exists(trajectory_path):
            return jsonify({
                "success": True,
                "data": None,
                "message": (
                    "No belief trajectory data available. The simulation may not "
                    "have used the belief tracking system."
                )
            })

        with open(trajectory_path, 'r', encoding='utf-8') as f:
            traj = json.load(f)

        snapshots = traj.get("snapshots", [])
        topics = traj.get("topics", [])

        raw_exclude = request.args.get('exclude_agents', '') or ''
        exclude_names = [n.strip() for n in raw_exclude.split(',') if n.strip()]

        # Build name -> str(user_id) map from the profiles file.
        # Index under every available name field because the influence
        # leaderboard surfaces the display `name` (e.g. "Mallku") while the
        # profile files also carry a handle under `username` / `user_name`
        # (e.g. "mallku_519"). Without this, incoming display names fall
        # through to `unresolved` and counterfactual ends up empty.
        profiles = _demo_load_profiles(sim_dir)
        name_to_id = {}
        for p in profiles:
            if not isinstance(p, dict):
                continue
            # `x or y` can't be used here: user_id 0 is a legitimate id and
            # 0 is falsy, so `p.get('user_id') or p.get('agent_id')` would
            # silently drop agent 0 (classic Python trap).
            uid = next(
                (p[k] for k in ('user_id', 'agent_id', 'id')
                 if p.get(k) is not None),
                None,
            )
            if uid is None:
                continue
            uid_str = str(uid)
            for key in ('name', 'user_name', 'username'):
                uname = p.get(key)
                if uname:
                    name_to_id.setdefault(str(uname), uid_str)

        # Resolve names to ids, tracking which we matched vs. missed.
        excluded_ids = set()
        resolved = []
        unresolved = []
        for n in exclude_names:
            aid = name_to_id.get(n)
            if aid is not None:
                excluded_ids.add(aid)
                resolved.append({"agent_name": n, "agent_id": aid})
            else:
                unresolved.append(n)

        # Set of agent ids present in the trajectory (all snapshots union).
        all_ids = set()
        for snap in snapshots:
            for aid in (snap.get("belief_positions") or {}).keys():
                all_ids.add(str(aid))

        allowed_ids = all_ids - excluded_ids

        original = _drift_from_positions_by_agent(snapshots, allowed_agent_ids=None)
        original["agent_count"] = len(all_ids)

        if excluded_ids:
            counterfactual = _drift_from_positions_by_agent(
                snapshots, allowed_agent_ids=allowed_ids
            )
            counterfactual["agent_count"] = len(allowed_ids)
        else:
            counterfactual = None

        def _delta(a, b):
            if a is None or b is None:
                return None
            return round(a - b, 1)

        delta_final_bullish = None
        delta_final_bearish = None
        delta_consensus_round = None
        if counterfactual is not None:
            delta_final_bullish = _delta(
                counterfactual.get("final_bullish_pct"),
                original.get("final_bullish_pct"),
            )
            delta_final_bearish = _delta(
                counterfactual.get("final_bearish_pct"),
                original.get("final_bearish_pct"),
            )
            cf_r = counterfactual.get("consensus_round")
            or_r = original.get("consensus_round")
            if cf_r is not None and or_r is not None:
                delta_consensus_round = cf_r - or_r

        def _impact_badge(delta):
            if delta is None:
                return None
            mag = abs(delta)
            if mag >= 15:
                return "strong"
            if mag >= 5:
                return "moderate"
            return "minimal"

        impact = _impact_badge(delta_final_bullish)

        summary = None
        if counterfactual is not None and delta_final_bullish is not None:
            names_str = ", ".join(r["agent_name"] for r in resolved) or "selected agents"
            direction = "increased" if delta_final_bullish > 0 else (
                "decreased" if delta_final_bullish < 0 else "did not change"
            )
            if delta_final_bullish == 0:
                summary = (
                    f"Removing {names_str} did not change final bullish share "
                    f"({original['final_bullish_pct']}%)."
                )
            else:
                summary = (
                    f"Removing {names_str} would have {direction} final bullish "
                    f"share from {original['final_bullish_pct']}% to "
                    f"{counterfactual['final_bullish_pct']}% "
                    f"({'+' if delta_final_bullish > 0 else ''}{delta_final_bullish} pts)."
                )

        return jsonify({
            "success": True,
            "data": {
                "original": original,
                "counterfactual": counterfactual,
                "excluded_requested": exclude_names,
                "excluded_resolved": resolved,
                "excluded_unresolved": unresolved,
                "topics": topics,
                "delta_final_bullish": delta_final_bullish,
                "delta_final_bearish": delta_final_bearish,
                "delta_consensus_round": delta_consensus_round,
                "impact": impact,
                "summary": summary,
            }
        })

    except Exception as e:
        logger.error(f"Failed to compute counterfactual drift: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Quality Diagnostics ==============

@simulation_bp.route('/<simulation_id>/quality', methods=['GET'])
def get_simulation_quality(simulation_id: str):
    """
    Compute post-completion quality diagnostics for a simulation.

    Measures participation rate, stance entropy, convergence speed,
    and cross-platform interaction rate. Returns an overall health
    badge (Excellent / Good / Low) plus actionable suggestions.
    Results are cached in quality.json inside the simulation directory.
    """
    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        quality_path = os.path.join(sim_dir, "quality.json")
        if os.path.exists(quality_path):
            with open(quality_path, 'r', encoding='utf-8') as f:
                return jsonify({"success": True, "data": json.load(f)})

        quality = _compute_quality_diagnostics(simulation_id, sim_dir)
        if quality is None:
            return jsonify({
                "success": True,
                "data": None,
                "message": "Insufficient data to compute quality diagnostics."
            })

        with open(quality_path, 'w', encoding='utf-8') as f:
            json.dump(quality, f, indent=2)

        return jsonify({"success": True, "data": quality})

    except Exception as e:
        logger.error(f"Failed to compute quality diagnostics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _compute_quality_diagnostics(simulation_id: str, sim_dir: str):
    """Compute quality metrics from trajectory.json and action logs."""
    import math

    trajectory_path = os.path.join(sim_dir, "trajectory.json")
    has_trajectory = os.path.exists(trajectory_path)

    all_actions = SimulationRunner.get_all_actions(simulation_id=simulation_id)
    if not all_actions and not has_trajectory:
        return None

    # --- Participation rate ---
    run_state = SimulationRunner.get_run_state(simulation_id)
    total_agents = 0
    if run_state:
        total_agents = run_state.total_agents if hasattr(run_state, 'total_agents') and run_state.total_agents else 0

    active_agent_ids = set()
    content_actions = {'CREATE_POST', 'QUOTE_POST', 'CREATE_COMMENT', 'BUY_SHARES', 'SELL_SHARES'}
    platform_actions = {}
    agent_platforms = {}
    for a in all_actions:
        a_dict = a.to_dict() if hasattr(a, 'to_dict') else a
        aid = a_dict.get('agent_id')
        atype = a_dict.get('action_type', '')
        platform = a_dict.get('platform', '')
        if atype in content_actions:
            active_agent_ids.add(aid)
        if platform:
            platform_actions[platform] = platform_actions.get(platform, 0) + 1
            if aid not in agent_platforms:
                agent_platforms[aid] = set()
            agent_platforms[aid].add(platform)

    if total_agents == 0:
        total_agents = len(set(
            (a.to_dict() if hasattr(a, 'to_dict') else a).get('agent_id')
            for a in all_actions
        )) or 1

    participation_rate = round(len(active_agent_ids) / max(total_agents, 1), 3)

    # --- Cross-platform interaction rate ---
    cross_platform_agents = sum(1 for p in agent_platforms.values() if len(p) > 1)
    total_interacting = len(agent_platforms) or 1
    cross_platform_rate = round(cross_platform_agents / total_interacting, 3)

    # --- Belief trajectory metrics ---
    stance_entropy = None
    convergence_round = None
    total_rounds = 0

    if has_trajectory:
        with open(trajectory_path, 'r', encoding='utf-8') as f:
            traj = json.load(f)

        snapshots = traj.get("snapshots", [])
        total_rounds = len(snapshots)

        if snapshots:
            for snap in snapshots:
                round_num = snap.get("round_num", 0)
                belief_positions = snap.get("belief_positions", {})
                if not belief_positions:
                    continue

                agent_stances = []
                for positions in belief_positions.values():
                    if positions:
                        avg = sum(positions.values()) / len(positions)
                        agent_stances.append(avg)

                if not agent_stances:
                    continue

                total = len(agent_stances)
                n_bullish = sum(1 for s in agent_stances if s > 0.2)
                n_bearish = sum(1 for s in agent_stances if s < -0.2)
                n_neutral = total - n_bullish - n_bearish

                pcts = [n_bullish / total, n_neutral / total, n_bearish / total]

                if convergence_round is None:
                    for p in pcts:
                        if p > 0.6:
                            convergence_round = round_num
                            break

            last_snap = snapshots[-1]
            bp = last_snap.get("belief_positions", {})
            if bp:
                stances = []
                for positions in bp.values():
                    if positions:
                        avg = sum(positions.values()) / len(positions)
                        stances.append(avg)
                if stances:
                    total = len(stances)
                    n_b = sum(1 for s in stances if s > 0.2)
                    n_be = sum(1 for s in stances if s < -0.2)
                    n_n = total - n_b - n_be
                    pcts = [n_b / total, n_n / total, n_be / total]
                    entropy = -sum(p * math.log(p) for p in pcts if p > 0)
                    max_entropy = math.log(3)
                    stance_entropy = round(entropy / max_entropy, 3) if max_entropy > 0 else 0
    else:
        if run_state:
            total_rounds = run_state.total_rounds if hasattr(run_state, 'total_rounds') else 0

    # --- Health badge ---
    health = "Good"
    if (participation_rate >= 0.8
            and (stance_entropy is None or stance_entropy >= 0.5)
            and (convergence_round is None or convergence_round >= 4)
            and cross_platform_rate >= 0.2):
        health = "Excellent"
    elif (participation_rate < 0.6
            or (stance_entropy is not None and stance_entropy < 0.2)):
        health = "Low"

    # --- Suggestions ---
    suggestions = []
    if participation_rate < 0.6:
        suggestions.append(
            f"Participation rate was {round(participation_rate * 100)}%. "
            "Try reducing agent count by 30% for this document complexity."
        )
    if convergence_round is not None and convergence_round < 3:
        suggestions.append(
            f"Consensus formed by round {convergence_round}. "
            "Consider increasing rounds to 12+ to allow more debate development."
        )
    if cross_platform_rate < 0.1:
        suggestions.append(
            "Cross-platform interaction rate is very low. "
            "Enable the cross-platform digest option to increase inter-platform agent awareness."
        )
    if stance_entropy is not None and stance_entropy < 0.3:
        suggestions.append(
            "Stance diversity is low — agents are in strong agreement. "
            "Consider adding agents with contrarian backgrounds to stimulate debate."
        )

    return {
        "participation_rate": participation_rate,
        "stance_entropy": stance_entropy,
        "convergence_round": convergence_round,
        "cross_platform_rate": cross_platform_rate,
        "total_rounds": total_rounds,
        "active_agents": len(active_agent_ids),
        "total_agents": total_agents,
        "health": health,
        "suggestions": suggestions,
    }


# ============== Per-round snapshot (ReplayView / analytics) ==============

@simulation_bp.route('/<simulation_id>/frame/<int:round_num>', methods=['GET'])
def get_simulation_frame(simulation_id: str, round_num: int):
    """Compact round snapshot: actions in the round + market prices + belief state.

    Purpose: power scrubbing UIs (ReplayView) without loading all actions
    upfront. A 500-agent × 72-round simulation may emit ~36k actions; this
    endpoint returns only the round requested plus any rolling state the
    client needs to render the frame.

    Query params:
        include_belief: "true" (default) — inlines belief positions at/before round
        include_market: "true" (default) — inlines YES price per market at round
        platforms: comma-list (twitter,reddit,polymarket) — filter returned actions

    Response: ``{actions, market_prices, belief, active_agents, action_counts}``.
    """
    try:
        validate_simulation_id(simulation_id)

        platforms_raw = (request.args.get('platforms') or '').strip()
        platforms = [p.strip().lower() for p in platforms_raw.split(',') if p.strip()] if platforms_raw else None
        include_belief = (request.args.get('include_belief', 'true').lower() == 'true')
        include_market = (request.args.get('include_market', 'true').lower() == 'true')

        # Collect actions for this round
        actions_for_round: list = []
        if platforms:
            for p in platforms:
                if p not in ('twitter', 'reddit', 'polymarket'):
                    continue
                actions_for_round.extend(
                    SimulationRunner.get_all_actions(simulation_id, platform=p, round_num=round_num)
                )
        else:
            actions_for_round = SimulationRunner.get_all_actions(simulation_id, round_num=round_num)

        actions_for_round.sort(key=lambda a: getattr(a, 'timestamp', '') or '')
        action_counts = {"twitter": 0, "reddit": 0, "polymarket": 0}
        active_agents = set()
        for a in actions_for_round:
            plat = getattr(a, 'platform', None)
            if plat in action_counts:
                action_counts[plat] += 1
            aid = getattr(a, 'agent_id', None)
            if aid is not None:
                active_agents.add(aid)

        # Market prices snapshot at this round
        market_prices: list = []
        if include_market:
            sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
            db_path = os.path.join(sim_dir, 'polymarket', 'polymarket.db')
            if os.path.exists(db_path):
                try:
                    import sqlite3
                    con = sqlite3.connect(db_path)
                    cur = con.cursor()
                    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if 'price_history' in tables:
                        # Most recent price at-or-before this round, per market
                        rows = cur.execute(
                            "SELECT market_id, price_yes, round_num FROM price_history "
                            "WHERE round_num <= ? ORDER BY round_num DESC",
                            (round_num,)
                        ).fetchall()
                        seen_markets = set()
                        for mid, py, rn in rows:
                            if mid in seen_markets:
                                continue
                            seen_markets.add(mid)
                            market_prices.append({"market_id": mid, "price_yes": py, "as_of_round": rn})
                    con.close()
                except Exception as exc:
                    logger.warning(f"frame: market price read failed for {simulation_id}: {exc}")

        # Belief snapshot at this round (or closest prior snapshot)
        belief_snapshot = None
        if include_belief:
            traj_path = os.path.join(
                Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id, "trajectory.json"
            )
            if os.path.exists(traj_path):
                try:
                    with open(traj_path, 'r', encoding='utf-8') as f:
                        traj = json.load(f)
                    snapshots = traj.get("snapshots", []) or []
                    chosen = None
                    for snap in snapshots:
                        if snap.get("round_num", -1) <= round_num:
                            chosen = snap
                        else:
                            break
                    if chosen:
                        positions = chosen.get("belief_positions", {}) or {}
                        stances = []
                        for p in positions.values():
                            if isinstance(p, dict) and p:
                                stances.append(sum(p.values()) / len(p))
                        total = len(stances) or 1
                        nb = sum(1 for s in stances if s > 0.2)
                        nbe = sum(1 for s in stances if s < -0.2)
                        belief_snapshot = {
                            "round_num": chosen.get("round_num"),
                            "bullish_pct": round(nb / total * 100, 1),
                            "bearish_pct": round(nbe / total * 100, 1),
                            "neutral_pct": round((total - nb - nbe) / total * 100, 1),
                            "agents_with_positions": len(positions),
                        }
                except Exception as exc:
                    logger.warning(f"frame: belief read failed for {simulation_id}: {exc}")

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "round_num": round_num,
                "actions": [a.to_dict() for a in actions_for_round],
                "action_counts": action_counts,
                "active_agents_count": len(active_agents),
                "market_prices": market_prices,
                "belief": belief_snapshot,
            },
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        logger.error(f"frame: failed for {simulation_id} round {round_num}: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============== Polymarket Live Chart ==============


def _polymarket_db_path(simulation_id: str) -> str:
    """Resolve the on-disk Polymarket DB. Handles both the current layout
    (``<sim_dir>/polymarket_simulation.db``) and the older nested layout
    (``<sim_dir>/polymarket/polymarket.db``)."""
    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
    candidates = [
        os.path.join(sim_dir, 'polymarket_simulation.db'),
        os.path.join(sim_dir, 'polymarket', 'polymarket.db'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


@simulation_bp.route('/<simulation_id>/polymarket/markets', methods=['GET'])
def polymarket_markets(simulation_id: str):
    """List all prediction markets in a simulation with current YES price.

    Response: { success, data: { markets: [{market_id, question, outcome_a,
    outcome_b, price_yes, reserve_a, reserve_b, resolved, winning_outcome,
    trade_count, created_at}] } }
    """
    try:
        validate_simulation_id(simulation_id)
        db_path = _polymarket_db_path(simulation_id)
        if not os.path.exists(db_path):
            return jsonify({"success": True, "data": {"markets": []}})

        import sqlite3
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            rows = cur.execute(
                "SELECT market_id, question, outcome_a, outcome_b, reserve_a, reserve_b, "
                "resolved, winning_outcome, created_at FROM market ORDER BY market_id"
            ).fetchall()
            trade_counts = dict(cur.execute(
                "SELECT market_id, COUNT(*) FROM trade GROUP BY market_id"
            ).fetchall())

        markets = []
        for mid, question, out_a, out_b, ra, rb, resolved, winner, created_at in rows:
            total = (ra or 0) + (rb or 0)
            price_yes = (rb / total) if total > 0 else 0.5
            markets.append({
                "market_id": mid,
                "question": question,
                "outcome_a": out_a,
                "outcome_b": out_b,
                "price_yes": round(price_yes, 4),
                "reserve_a": ra,
                "reserve_b": rb,
                "resolved": bool(resolved),
                "winning_outcome": winner,
                "trade_count": trade_counts.get(mid, 0),
                "created_at": created_at,
            })
        return jsonify({"success": True, "data": {"markets": markets}})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        logger.error(f"polymarket_markets: {simulation_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/polymarket/market/<int:market_id>/prices', methods=['GET'])
def polymarket_market_prices(simulation_id: str, market_id: int):
    """Time-series of YES price for a single market, reconstructed from trades.

    For each trade row we derive yes_price:
      - outcome == 'YES' → yes_price = price
      - outcome == 'NO'  → yes_price = 1 - price
    Prepends an origin point at 0.5 (AMM initial state before any trade).

    Response: { success, data: { market, points: [{t, price_yes, side, outcome,
    shares, trade_id}] } }
    """
    locale = get_locale(request)
    try:
        validate_simulation_id(simulation_id)
        db_path = _polymarket_db_path(simulation_id)
        if not os.path.exists(db_path):
            return jsonify({"success": False, "error": _t(
                "Polymarket not enabled for this simulation",
                "该模拟未启用 Polymarket",
                locale,
            )}), 404

        import sqlite3
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            market_row = cur.execute(
                "SELECT market_id, question, outcome_a, outcome_b, reserve_a, reserve_b, "
                "resolved, winning_outcome, created_at FROM market WHERE market_id = ?",
                (market_id,),
            ).fetchone()
            if not market_row:
                return jsonify({"success": False, "error": _t(
                    f"Market {market_id} not found",
                    f"未找到市场 {market_id}",
                    locale,
                )}), 404
            trades = cur.execute(
                "SELECT trade_id, user_id, side, outcome, shares, price, created_at "
                "FROM trade WHERE market_id = ? ORDER BY created_at ASC, trade_id ASC",
                (market_id,),
            ).fetchall()

        mid, question, out_a, out_b, ra, rb, resolved, winner, created_at = market_row
        total = (ra or 0) + (rb or 0)
        current_price_yes = (rb / total) if total > 0 else 0.5

        points = [{
            "t": created_at,
            "price_yes": 0.5,
            "side": None,
            "outcome": None,
            "shares": 0,
            "trade_id": None,
        }]
        for tid, uid, side, outcome, shares, price, t_created in trades:
            outcome_up = (outcome or '').upper()
            if outcome_up in ('NO', out_b.upper() if out_b else 'NO'):
                yes_price = max(0.0, min(1.0, 1.0 - (price or 0)))
            else:
                yes_price = max(0.0, min(1.0, price or 0))
            points.append({
                "t": t_created,
                "price_yes": round(yes_price, 4),
                "side": side,
                "outcome": outcome,
                "shares": shares,
                "trade_id": tid,
            })

        return jsonify({
            "success": True,
            "data": {
                "market": {
                    "market_id": mid,
                    "question": question,
                    "outcome_a": out_a,
                    "outcome_b": out_b,
                    "price_yes": round(current_price_yes, 4),
                    "reserve_a": ra,
                    "reserve_b": rb,
                    "resolved": bool(resolved),
                    "winning_outcome": winner,
                    "trade_count": len(trades),
                    "created_at": created_at,
                },
                "points": points,
            },
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as e:
        logger.error(f"polymarket_market_prices: {simulation_id}/{market_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============== Embed Widget ==============

@simulation_bp.route('/<simulation_id>/publish', methods=['POST'])
@require_admin_token
def publish_simulation(simulation_id: str):
    """Mark a simulation as publicly embeddable.

    Body (optional): ``{"public": false}`` to unpublish instead of publish.
    Returns the new public state.

    Auth: requires ``Authorization: Bearer $MIROSHARK_ADMIN_TOKEN``.
    """
    locale = get_locale(request)
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        payload = request.get_json(silent=True) or {}
        new_value = bool(payload.get("public", True))
        state.is_public = new_value
        manager._save_simulation_state(state)

        return jsonify({"success": True, "data": {"simulation_id": simulation_id, "is_public": state.is_public}})
    except Exception as e:
        logger.error(f"Failed to publish simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


def _build_embed_summary_payload(simulation_id: str) -> dict:
    """Assemble the same dict the embed-summary endpoint returns.

    Extracted so the share-card renderer can reuse the data pipeline without
    going back through HTTP. Caller is responsible for the ``is_public``
    gate — this only does the disk reads and aggregation. Raises
    ``LookupError`` if the simulation doesn't exist.
    """
    manager = SimulationManager()
    state = manager.get_simulation(simulation_id)
    if not state:
        raise LookupError(f"Simulation not found: {simulation_id}")

    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

    config = manager.get_simulation_config(simulation_id)
    scenario = ""
    if config:
        scenario = (config.get("simulation_requirement") or "").strip()

    run_state = SimulationRunner.get_run_state(simulation_id)
    if run_state:
        current_round = run_state.current_round
        total_rounds = run_state.total_rounds if getattr(run_state, 'total_rounds', 0) else 0
        runner_status = run_state.runner_status.value if hasattr(run_state.runner_status, 'value') else str(run_state.runner_status)
    else:
        current_round = 0
        total_rounds = 0
        runner_status = "idle"

    if total_rounds == 0 and config:
        time_config = config.get("time_config", {})
        minutes_per_round = max(int(time_config.get("minutes_per_round", 60) or 60), 1)
        hours = int(time_config.get("total_simulation_hours", 0) or 0)
        total_rounds = int(hours * 60 / minutes_per_round)

    belief = None
    trajectory_path = os.path.join(sim_dir, "trajectory.json") if os.path.exists(sim_dir) else None
    if trajectory_path and os.path.exists(trajectory_path):
        try:
            with open(trajectory_path, 'r', encoding='utf-8') as f:
                traj = json.load(f)

            rounds = []
            bullish = []
            neutral = []
            bearish = []
            for snap in traj.get("snapshots", []):
                positions = snap.get("belief_positions", {}) or {}
                if not positions:
                    continue
                stances = []
                for p in positions.values():
                    if p:
                        stances.append(sum(p.values()) / len(p))
                if not stances:
                    continue
                total = len(stances)
                nb = sum(1 for s in stances if s > 0.2)
                nbe = sum(1 for s in stances if s < -0.2)
                nn = total - nb - nbe
                rounds.append(snap.get("round_num", len(rounds)))
                bullish.append(round(nb / total * 100, 1))
                neutral.append(round(nn / total * 100, 1))
                bearish.append(round(nbe / total * 100, 1))

            consensus_round = None
            consensus_stance = None
            for i, _ in enumerate(rounds):
                if bullish[i] > 50:
                    consensus_round = rounds[i]
                    consensus_stance = "bullish"
                    break
                if bearish[i] > 50:
                    consensus_round = rounds[i]
                    consensus_stance = "bearish"
                    break

            if rounds:
                belief = {
                    "rounds": rounds,
                    "bullish": bullish,
                    "neutral": neutral,
                    "bearish": bearish,
                    "final": {
                        "bullish": bullish[-1],
                        "neutral": neutral[-1],
                        "bearish": bearish[-1],
                    },
                    "consensus_round": consensus_round,
                    "consensus_stance": consensus_stance,
                }
        except Exception as exc:
            logger.warning(f"Embed summary: failed to parse trajectory for {simulation_id}: {exc}")

    quality = None
    quality_path = os.path.join(sim_dir, "quality.json") if os.path.exists(sim_dir) else None
    if quality_path and os.path.exists(quality_path):
        try:
            with open(quality_path, 'r', encoding='utf-8') as f:
                q = json.load(f)
            quality = {
                "health": q.get("health"),
                "participation_rate": q.get("participation_rate"),
            }
        except Exception:
            quality = None

    resolution = None
    resolution_path = os.path.join(sim_dir, "resolution.json") if os.path.exists(sim_dir) else None
    if resolution_path and os.path.exists(resolution_path):
        try:
            with open(resolution_path, 'r', encoding='utf-8') as f:
                r = json.load(f)
            resolution = {
                "actual_outcome": r.get("actual_outcome"),
                "predicted_consensus": r.get("predicted_consensus"),
                "accuracy_score": r.get("accuracy_score"),
            }
        except Exception:
            resolution = None

    created_date = (state.created_at or "")[:10]

    return {
        "simulation_id": simulation_id,
        "scenario": scenario,
        "status": state.status.value if hasattr(state.status, 'value') else str(state.status),
        "runner_status": runner_status,
        "current_round": current_round,
        "total_rounds": total_rounds,
        "profiles_count": state.profiles_count,
        "created_date": created_date,
        "parent_simulation_id": state.parent_simulation_id,
        "is_public": getattr(state, "is_public", False),
        "belief": belief,
        "quality": quality,
        "resolution": resolution,
    }


@simulation_bp.route('/<simulation_id>/embed-summary', methods=['GET'])
def get_embed_summary(simulation_id: str):
    """
    Return a minimal summary for rendering the embeddable widget.

    Bundles only the fields the embed iframe needs — scenario, round counts,
    agent count, belief drift sparkline, optional consensus/resolution/health —
    so a single request powers the read-only widget without the full simulation
    payload.

    Access: requires ``is_public=True`` on the simulation state. Use the
    ``/publish`` endpoint to toggle.
    """
    locale = get_locale(request)
    try:
        try:
            summary = _build_embed_summary_payload(simulation_id)
        except LookupError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

        if not summary.get("is_public"):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation is not published for embedding. POST /api/simulation/<id>/publish to enable.",
                    "该模拟未发布为可嵌入,请通过 POST /api/simulation/<id>/publish 启用。",
                    locale,
                ),
            }), 403

        response = jsonify({"success": True, "data": summary})
        # Widget is read-only and explicitly designed to be embedded anywhere.
        response.headers["Cache-Control"] = "public, max-age=60"
        return response

    except Exception as e:
        logger.error(f"Failed to build embed summary: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/share-card.png', methods=['GET'])
def get_share_card(simulation_id: str):
    """Render a 1200x630 PNG suitable for Open Graph / Twitter image
    unfurling.

    Same publish gate as ``/embed-summary``: requires ``is_public=True`` on
    the simulation state. Cached on disk by content hash so repeat
    unfurler hits don't re-render.
    """
    from ..services import share_card as share_card_renderer
    from flask import Response

    locale = get_locale(request)
    try:
        try:
            summary = _build_embed_summary_payload(simulation_id)
        except LookupError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

        if not summary.get("is_public"):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation is not published. POST /api/simulation/<id>/publish to enable.",
                    "该模拟未发布,请通过 POST /api/simulation/<id>/publish 启用。",
                    locale,
                ),
            }), 403

        cache_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id, "share-cards")
        os.makedirs(cache_dir, exist_ok=True)
        key = share_card_renderer.summary_cache_key(summary)
        cache_path = os.path.join(cache_dir, f"{key}.png")

        if os.path.exists(cache_path):
            with open(cache_path, "rb") as fh:
                png_bytes = fh.read()
        else:
            png_bytes = share_card_renderer.render_share_card(summary)
            try:
                with open(cache_path, "wb") as fh:
                    fh.write(png_bytes)
            except OSError as exc:
                logger.warning(f"share-card: failed to cache to {cache_path}: {exc}")

        response = Response(png_bytes, mimetype="image/png")
        response.headers["Cache-Control"] = "public, max-age=3600"
        # Suggest a friendly filename when downloaded directly.
        response.headers["Content-Disposition"] = (
            f'inline; filename="miroshark-{simulation_id[:12]}.png"'
        )
        return response

    except Exception as e:
        logger.error(f"share-card: failed for {simulation_id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@simulation_bp.route('/<simulation_id>/replay.gif', methods=['GET'])
def get_replay_gif(simulation_id: str):
    """Render an animated GIF of the per-round belief drift.

    1200×630 (same OG aspect as the share card) — one frame per round
    with belief bars sliding to that round's bullish/neutral/bearish
    split, a round counter, and a progress bar. X / Discord / Slack
    auto-play GIF URLs inline so a public simulation gets a motion
    asset on every share without any extra effort from the operator.

    Same publish gate as ``/share-card.png``: requires ``is_public=True``.
    Cached on disk by content hash so repeat hits don't re-render.
    """
    from ..services import replay_gif as replay_renderer
    from flask import Response

    locale = get_locale(request)
    try:
        try:
            summary = _build_embed_summary_payload(simulation_id)
        except LookupError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

        if not summary.get("is_public"):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation is not published. POST /api/simulation/<id>/publish to enable.",
                    "该模拟未发布,请通过 POST /api/simulation/<id>/publish 启用。",
                    locale,
                ),
            }), 403

        cache_dir = os.path.join(
            Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id, "replay-gifs"
        )
        os.makedirs(cache_dir, exist_ok=True)
        key = replay_renderer.summary_cache_key(summary)
        cache_path = os.path.join(cache_dir, f"{key}.gif")

        if os.path.exists(cache_path):
            with open(cache_path, "rb") as fh:
                gif_bytes = fh.read()
        else:
            gif_bytes = replay_renderer.render_replay_gif(summary)
            try:
                with open(cache_path, "wb") as fh:
                    fh.write(gif_bytes)
            except OSError as exc:
                logger.warning(f"replay-gif: failed to cache to {cache_path}: {exc}")

        response = Response(gif_bytes, mimetype="image/gif")
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["Content-Disposition"] = (
            f'inline; filename="miroshark-{simulation_id[:12]}-replay.gif"'
        )
        return response

    except Exception as e:
        logger.error(f"replay-gif: failed for {simulation_id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


def _serve_transcript(simulation_id: str, fmt: str):
    """Shared body for the transcript.md / transcript.json routes.

    Both endpoints share the same publish gate, the same data assembly
    (``transcript.build_transcript_data``), and only diverge in the
    encoding step. Extracted so the two route handlers stay one-line
    wrappers — the decorator presence is what the OpenAPI drift test
    scans for, but the actual logic lives here.
    """
    from ..services import transcript as transcript_renderer
    from flask import Response

    locale = get_locale(request)
    try:
        try:
            summary = _build_embed_summary_payload(simulation_id)
        except LookupError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

        if not summary.get("is_public"):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation is not published. POST /api/simulation/<id>/publish to enable.",
                    "该模拟未发布,请通过 POST /api/simulation/<id>/publish 启用。",
                    locale,
                ),
            }), 403

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        data = transcript_renderer.build_transcript_data(summary, sim_dir)

        if fmt == "json":
            payload = transcript_renderer.render_json_bytes(data)
            mimetype = "application/json; charset=utf-8"
            filename = f"miroshark-{simulation_id[:12]}-transcript.json"
        else:
            payload = transcript_renderer.render_markdown_bytes(data)
            mimetype = "text/markdown; charset=utf-8"
            filename = f"miroshark-{simulation_id[:12]}-transcript.md"

        response = Response(payload, mimetype=mimetype)
        # Short cache — the transcript can change every round on a
        # live run, but unfurlers / curl loops shouldn't hammer the
        # disk reads either. 60s matches the embed-summary cadence.
        response.headers["Cache-Control"] = "public, max-age=60"
        # Inline so a click from the frontend renders in-tab; the UI
        # uses an explicit ``download`` attribute on its anchor when it
        # wants a save-as.
        response.headers["Content-Disposition"] = (
            f'inline; filename="{filename}"'
        )
        return response

    except Exception as e:
        logger.error(f"transcript: failed for {simulation_id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@simulation_bp.route('/<simulation_id>/transcript.md', methods=['GET'])
def get_transcript_md(simulation_id: str):
    """Citable Markdown transcript of the simulation.

    Per-round agent posts + stance labels + final consensus, served as
    ``text/markdown`` so Notion / Obsidian / Bear / Substack import the
    YAML front matter as page metadata. Same publish gate as the share
    card and replay GIF — the underlying ``is_public`` flag controls
    who can read the agent posts.

    Pairs with ``share-card.png`` (preview), ``replay.gif`` (motion),
    and this endpoint (text) as the three quote-friendly share formats.
    """
    return _serve_transcript(simulation_id, "md")


@simulation_bp.route('/<simulation_id>/transcript.json', methods=['GET'])
def get_transcript_json(simulation_id: str):
    """Same transcript payload as ``transcript.md`` but as JSON.

    Same publish gate. Pretty-printed (indent=2) so a ``curl`` to a
    file is immediately readable. Intended for SDK / pipeline consumers
    (Python client SDK, downstream LLM-as-judge eval pipelines, etc.)
    that need a structured form rather than the human-readable
    Markdown.
    """
    return _serve_transcript(simulation_id, "json")


def _serve_trajectory(simulation_id: str, fmt: str):
    """Shared body for the trajectory.csv / trajectory.jsonl routes.

    Both endpoints share the same publish gate, the same row assembly
    (``trajectory_export.build_rows``), and only diverge in the encoding
    step. Extracted so the two route handlers stay one-line wrappers —
    the decorator presence is what the OpenAPI drift test scans for,
    but the actual logic lives here.
    """
    from ..services import trajectory_export
    from flask import Response

    locale = get_locale(request)
    try:
        try:
            summary = _build_embed_summary_payload(simulation_id)
        except LookupError as exc:
            return jsonify({"success": False, "error": str(exc)}), 404

        if not summary.get("is_public"):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation is not published. POST /api/simulation/<id>/publish to enable.",
                    "该模拟未发布,请通过 POST /api/simulation/<id>/publish 启用。",
                    locale,
                ),
            }), 403

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        rows = trajectory_export.build_rows(sim_dir)

        if fmt == "jsonl":
            payload = trajectory_export.render_jsonl(rows)
            mimetype = "application/jsonl; charset=utf-8"
            filename = f"miroshark-{simulation_id[:12]}-trajectory.jsonl"
        else:
            payload = trajectory_export.render_csv(rows)
            mimetype = "text/csv; charset=utf-8"
            filename = f"miroshark-{simulation_id[:12]}-trajectory.csv"

        response = Response(payload, mimetype=mimetype)
        # Short cache — the trajectory grows by one row per round on a
        # live run; 60s matches transcript + embed-summary so an
        # analyst polling for completion sees fresh data quickly while
        # bot crawlers don't hammer disk reads.
        response.headers["Cache-Control"] = "public, max-age=60"
        # ``attachment`` so a click from the embed dialog triggers a
        # save-as without an explicit ``download`` attribute on the
        # anchor — analysts paste the URL into ``pandas.read_csv()``,
        # they don't render the bytes in-tab.
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        return response

    except Exception as e:
        logger.error(f"trajectory: failed for {simulation_id}: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@simulation_bp.route('/<simulation_id>/trajectory.csv', methods=['GET'])
def get_trajectory_csv(simulation_id: str):
    """Per-round belief trajectory as RFC 4180 CSV.

    One row per recorded round with the bullish/neutral/bearish split
    (using the same ±0.2 stance threshold as the gallery, share card,
    replay GIF, transcript, webhook, and feed surfaces), participating
    agents, post + engagement counts, and the overall quality health.
    Intended for ``pandas.read_csv()`` / Excel / Tableau / R / Observable
    consumers — the analyst's default toolkit. Same publish gate as the
    transcript and share card.
    """
    return _serve_trajectory(simulation_id, "csv")


@simulation_bp.route('/<simulation_id>/trajectory.jsonl', methods=['GET'])
def get_trajectory_jsonl(simulation_id: str):
    """Same per-round belief trajectory as ``trajectory.csv`` but as
    newline-delimited JSON.

    One JSON object per line — the format ``pandas.read_json(lines=True)``,
    DuckDB ``read_json_auto``, and most stream-processing pipelines
    consume natively without a separate CSV-to-DataFrame conversion.
    Intended for SDK / pipeline consumers that need the same numbers
    the CSV carries but in a structured shape.
    """
    return _serve_trajectory(simulation_id, "jsonl")


# ============== Public Gallery ==============


_VALID_OUTCOME_LABELS = ("correct", "incorrect", "partial")


def _read_outcome_file(sim_dir: str) -> dict | None:
    """Read ``<sim_dir>/outcome.json`` if it exists.

    Returns the parsed dict (with the public fields the gallery + embed
    surfaces care about) or ``None`` when the file is absent or malformed.
    Never raises — a corrupt artifact must not blank out the gallery.
    """
    outcome_path = os.path.join(sim_dir, "outcome.json")
    if not os.path.exists(outcome_path):
        return None
    try:
        with open(outcome_path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
    except Exception:
        return None

    label = (data.get("label") or "").strip().lower()
    if label not in _VALID_OUTCOME_LABELS:
        # Silently ignore an artifact with an unknown label — same posture
        # as the rest of the gallery helper: render the card without it.
        return None

    summary = (data.get("outcome_summary") or "").strip()
    if len(summary) > 280:
        summary = summary[:277].rstrip() + "…"

    url = (data.get("outcome_url") or "").strip()
    # Only echo URLs we recognize — protects readers from a malformed
    # ``javascript:``/``file://`` value sneaking onto the gallery card.
    if url and not (url.startswith("http://") or url.startswith("https://")):
        url = ""

    return {
        "label": label,
        "outcome_url": url,
        "outcome_summary": summary,
        "submitted_at": data.get("submitted_at") or "",
    }


def _build_gallery_card_payload(state, sim_dir: str) -> dict:
    """Assemble the minimal card-friendly payload for the public gallery.

    Cheap reads only — no DB joins, no LLM calls. Walks the on-disk
    artifacts (``state.json``, ``simulation_config.json``, ``quality.json``,
    ``trajectory.json``, ``resolution.json``) that are already produced by
    the normal run pipeline. Any missing artifact degrades gracefully into
    ``None`` rather than raising.
    """
    scenario = ""
    total_rounds = 0
    config_path = os.path.join(sim_dir, "simulation_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            scenario = (cfg.get("simulation_requirement") or "").strip()
            time_config = cfg.get("time_config", {}) or {}
            minutes_per_round = max(int(time_config.get("minutes_per_round", 60) or 60), 1)
            hours = int(time_config.get("total_simulation_hours", 0) or 0)
            total_rounds = int(hours * 60 / minutes_per_round)
        except Exception:
            pass

    # Cap the scenario to a tweet-sized headline so the gallery stays
    # visually even regardless of how verbose the operator was.
    if scenario and len(scenario) > 180:
        scenario = scenario[:177].rstrip() + "…"

    current_round = 0
    runner_status = "idle"
    try:
        run_state = SimulationRunner.get_run_state(state.simulation_id)
        if run_state:
            current_round = run_state.current_round
            runner_status = (
                run_state.runner_status.value
                if hasattr(run_state.runner_status, 'value')
                else str(run_state.runner_status)
            )
            if getattr(run_state, 'total_rounds', 0):
                total_rounds = run_state.total_rounds
    except Exception:
        pass

    quality_health = None
    quality_path = os.path.join(sim_dir, "quality.json")
    if os.path.exists(quality_path):
        try:
            with open(quality_path, 'r', encoding='utf-8') as f:
                q = json.load(f)
            quality_health = q.get("health")
        except Exception:
            pass

    final_consensus = None
    trajectory_path = os.path.join(sim_dir, "trajectory.json")
    if os.path.exists(trajectory_path):
        try:
            with open(trajectory_path, 'r', encoding='utf-8') as f:
                traj = json.load(f)
            snapshots = traj.get("snapshots", []) or []
            # Walk snapshots in reverse to pick the last one with
            # computable belief positions.
            for snap in reversed(snapshots):
                positions = snap.get("belief_positions", {}) or {}
                if not positions:
                    continue
                stances = []
                for p in positions.values():
                    if p:
                        stances.append(sum(p.values()) / len(p))
                if not stances:
                    continue
                total = len(stances)
                nb = sum(1 for s in stances if s > 0.2)
                nbe = sum(1 for s in stances if s < -0.2)
                nn = total - nb - nbe
                final_consensus = {
                    "bullish": round(nb / total * 100, 1),
                    "neutral": round(nn / total * 100, 1),
                    "bearish": round(nbe / total * 100, 1),
                }
                break
        except Exception:
            pass

    resolution_outcome = None
    resolution_path = os.path.join(sim_dir, "resolution.json")
    if os.path.exists(resolution_path):
        try:
            with open(resolution_path, 'r', encoding='utf-8') as f:
                r = json.load(f)
            resolution_outcome = r.get("actual_outcome")
        except Exception:
            pass

    outcome = _read_outcome_file(sim_dir)

    return {
        "simulation_id": state.simulation_id,
        "scenario": scenario,
        "status": state.status.value if hasattr(state.status, 'value') else str(state.status),
        "runner_status": runner_status,
        "current_round": current_round,
        "total_rounds": total_rounds,
        "agent_count": state.profiles_count,
        "quality_health": quality_health,
        "final_consensus": final_consensus,
        "resolution_outcome": resolution_outcome,
        "outcome": outcome,
        "created_at": state.created_at,
        "parent_simulation_id": state.parent_simulation_id,
        "share_card_url": f"/api/simulation/{state.simulation_id}/share-card.png",
        "share_landing_url": f"/share/{state.simulation_id}",
    }


@simulation_bp.route('/public', methods=['GET'])
def list_public_simulations():
    """Gallery feed of simulations the operator has toggled public.

    Every published simulation already has a share card, embed summary,
    and public landing page — this endpoint is the discovery layer that
    lists them all in one place so the ``/explore`` view can render a
    gallery grid.

    Query parameters:
        limit: max items to return (default 50, clamped to [1, 100])
        offset: pagination offset (default 0)
        verified: when truthy ("1", "true", "yes"), filter to simulations
            with a recorded outcome annotation (see
            ``POST /api/simulation/<id>/outcome``).

    Response shape::

        {
          "success": true,
          "data": [
            {
              "simulation_id": "sim_xxx",
              "scenario": "Will the ECB cut rates in June?",
              "status": "completed",
              "runner_status": "completed",
              "current_round": 20,
              "total_rounds": 20,
              "agent_count": 248,
              "quality_health": "Excellent",
              "final_consensus": {"bullish": 62.0, "neutral": 13.0, "bearish": 25.0},
              "resolution_outcome": "YES",
              "created_at": "2026-04-22T10:12:34",
              "parent_simulation_id": null,
              "share_card_url": "/api/simulation/sim_xxx/share-card.png",
              "share_landing_url": "/share/sim_xxx"
            },
            ...
          ],
          "count": 17,
          "total": 17,
          "limit": 50,
          "offset": 0,
          "has_more": false
        }

    ``count`` is the size of the current page; ``total`` is the count of
    all public simulations. An empty ``data`` array is normal — the
    caller should render the "No public simulations yet" empty state.
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        limit = max(1, min(100, int(limit or 50)))
        offset = max(0, int(offset or 0))

        verified_raw = (request.args.get('verified') or "").strip().lower()
        verified_only = verified_raw in ("1", "true", "yes", "on")

        manager = SimulationManager()
        all_sims = manager.list_simulations()

        public_sims = [s for s in all_sims if bool(getattr(s, "is_public", False))]
        public_sims.sort(key=lambda s: s.created_at or "", reverse=True)

        if verified_only:
            # Filter on disk before paginating so ``total`` reflects the
            # filtered set — otherwise the "X remaining" hint and
            # ``has_more`` flag would lie about how much is left.
            verified_sims = []
            for s in public_sims:
                sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, s.simulation_id)
                if _read_outcome_file(sim_dir) is not None:
                    verified_sims.append(s)
            public_sims = verified_sims

        total = len(public_sims)
        page = public_sims[offset:offset + limit]

        items = []
        for state in page:
            sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, state.simulation_id)
            try:
                items.append(_build_gallery_card_payload(state, sim_dir))
            except Exception as exc:
                # One bad artifact shouldn't tank the whole gallery.
                logger.warning(
                    f"public-gallery: failed to build card for {state.simulation_id}: {exc}"
                )
                continue

        response = jsonify({
            "success": True,
            "data": items,
            "count": len(items),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
            "verified_only": verified_only,
        })
        # Short cache so newly-published simulations show up quickly while
        # still absorbing repeat hits from bots/social unfurlers.
        response.headers["Cache-Control"] = "public, max-age=30"
        return response

    except Exception as e:
        logger.error(f"Failed to list public simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Database Query Endpoints ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    Get simulation posts

    Query parameters:
        platform: Platform type (twitter/reddit)
        limit: Return count (default 50)
        offset: Offset

    Returns post list (read from SQLite database)
    """
    try:
        platform = request.args.get('platform', 'reddit')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": "Database does not exist, simulation may not have started"
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM post 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            posts = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            posts = []
            total = 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get posts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interview Endpoints ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    Interview single agent

    Note: This feature requires the simulation environment to be running
    (after completing simulation loop, entering command waiting mode)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                      // Required, simulation ID
            "agent_id": 0,                                    // Required, Agent ID
            "prompt": "What do you think about this?",        // Required, interview question
            "platform": "twitter",                            // Optional, specify platform (twitter/reddit)
                                                              // When not specified: dual-platform simulation interviews both platforms simultaneously
            "timeout": 60                                     // Optional, timeout (seconds), default 60
        }

    Returns (without specifying platform, dual-platform mode):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Returns (with specified platform):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "response": "I think...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": _t("Please provide agent_id", "请提供 agent_id", locale)
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": _t(
                    "Please provide prompt (interview question)",
                    "请提供 prompt(访谈问题)",
                    locale,
                )
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": _t(
                    "platform parameter can only be 'twitter' or 'reddit'",
                    "platform 参数只能为 'twitter' 或 'reddit'",
                    locale,
                )
            }), 400

        # Check environment status — auto-restart if needed
        if not _ensure_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation environment could not be started. Please try again.",
                    "无法启动模拟环境,请重试。",
                    locale,
                )
            }), 400

        # Optimize prompt, add prefix to prevent agent from calling tools
        optimized_prompt = optimize_interview_prompt(prompt)
        
        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for interview response: {str(e)}"
        }), 504
        
    except Exception as e:
        logger.error(f"Interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    Batch interview multiple agents

    Note: This feature requires the simulation environment to be running

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                  // Required, simulation ID
            "interviews": [                               // Required, interview list
                {
                    "agent_id": 0,
                    "prompt": "What do you think about A?",
                    "platform": "twitter"                 // Optional, specify interview platform for this agent
                },
                {
                    "agent_id": 1,
                    "prompt": "What do you think about B?"  // If platform not specified, uses default
                }
            ],
            "platform": "reddit",                         // Optional, default platform (overridden by each item's platform)
                                                          // When not specified: dual-platform simulation interviews each agent on both platforms simultaneously
            "timeout": 120                                // Optional, timeout (seconds), default 120
        }

    Returns:
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err
        interviews = data.get('interviews')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 120)

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": _t(
                    "Please provide interviews (interview list)",
                    "请提供 interviews(访谈列表)",
                    locale,
                )
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": _t(
                    "platform parameter can only be 'twitter' or 'reddit'",
                    "platform 参数只能为 'twitter' 或 'reddit'",
                    locale,
                )
            }), 400

        # Validate each interview item
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": _t(
                        f"Interview list item {i+1} is missing agent_id",
                        f"访谈列表第 {i+1} 项缺少 agent_id",
                        locale,
                    )
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": _t(
                        f"Interview list item {i+1} is missing prompt",
                        f"访谈列表第 {i+1} 项缺少 prompt",
                        locale,
                    )
                }), 400
            # Validate each item's platform (if present)
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": _t(
                        f"Interview list item {i+1} platform can only be 'twitter' or 'reddit'",
                        f"访谈列表第 {i+1} 项的 platform 只能为 'twitter' 或 'reddit'",
                        locale,
                    )
                }), 400

        # Check environment status — auto-restart if needed
        if not _ensure_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation environment could not be started. Please try again.",
                    "无法启动模拟环境,请重试。",
                    locale,
                )
            }), 400

        # Optimize each interview item's prompt, add prefix to prevent agent from calling tools
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for batch interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Batch interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    Get interview history

    Read all interview records from simulation database

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // Required, simulation ID
            "platform": "reddit",          // Optional, platform type (reddit/twitter)
                                           // If not specified, return all history for both platforms
            "agent_id": 0,                 // Optional, only get this agent's interview history
            "limit": 100                   // Optional, return count, default 100
        }

    Returns:
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "I think...",
                        "prompt": "What do you think about this?",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err
        platform = data.get('platform')  # If not specified, return history for both platforms
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"Failed to get interview history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    Get simulation environment status

    Check if simulation environment is alive (can receive interview commands)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // Required, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Environment is running, can receive interview commands"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # Get more detailed status information
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = "Environment is running, can receive interview commands"
        else:
            message = "Environment is not running or has been shut down"

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"Failed to get environment status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/restart-env', methods=['POST'])
def restart_env():
    """
    Restart simulation environment for interviews (without running simulation).
    Launches the simulation script with --env-only flag.
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}
        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err

        # Check if env is already alive
        if SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "message": "Environment is already running",
                    "already_running": True
                }
            })

        # Check if simulation is prepared
        is_prepared, _ = _check_simulation_prepared(simulation_id)
        if not is_prepared:
            return jsonify({"success": False, "error": _t(
                "Simulation not prepared",
                "模拟尚未准备完成",
                locale,
            )}), 400

        # Start the simulation script with --env-only
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform='parallel',
            start_round=0,
            env_only=True
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "process_pid": run_state.process_pid,
                "message": "Environment starting for interviews",
                "already_running": False
            }
        })

    except Exception as e:
        logger.error(f"Failed to restart env: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    Shut down simulation environment

    Send shutdown command to simulation for graceful exit from command waiting mode.

    Note: This is different from /stop endpoint. /stop will forcefully terminate the process,
    while this endpoint allows the simulation to gracefully shut down and exit.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // Required, simulation ID
            "timeout": 30                  // Optional, timeout (seconds), default 30
        }

    Returns:
        {
            "success": true,
            "data": {
                "message": "Environment shutdown command sent",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    locale = get_locale(request)
    try:
        data = request.get_json() or {}

        simulation_id, err = _get_simulation_id_or_400(data, locale)
        if err:
            return err
        timeout = data.get('timeout', 30)
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )
        
        # Update simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to shut down environment: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Data Export Endpoints ==============

@simulation_bp.route('/<simulation_id>/export', methods=['GET'])
def export_simulation_data(simulation_id: str):
    """
    Export simulation data as JSON or CSV file download.

    Query parameters:
        format: Export format — 'json' (default) or 'csv'
        include: Comma-separated data sections to include.
                 Options: actions,posts,timeline,agent_stats,metadata
                 Default: all sections

    Returns:
        File download (application/json or text/csv)
    """
    locale = get_locale(request)
    try:
        export_format = request.args.get('format', 'json').lower()
        include_raw = request.args.get('include', 'actions,posts,timeline,agent_stats,metadata')
        include_sections = {s.strip() for s in include_raw.split(',')}

        if export_format not in ('json', 'csv'):
            return jsonify({
                "success": False,
                "error": _t(
                    "Unsupported format. Use 'json' or 'csv'.",
                    "不支持的格式,请使用 'json' 或 'csv'。",
                    locale,
                )
            }), 400

        export_data = {}

        # --- Metadata ---
        if 'metadata' in include_sections:
            manager = SimulationManager()
            state = manager.get_simulation(simulation_id)
            run_state = SimulationRunner.get_run_state(simulation_id)
            export_data['metadata'] = {
                "simulation_id": simulation_id,
                "exported_at": datetime.utcnow().isoformat(),
                "status": state.status.value if state else None,
                "project_id": state.project_id if state else None,
                "run_state": run_state.to_dict() if run_state else None,
            }

        # --- Actions ---
        if 'actions' in include_sections:
            actions = SimulationRunner.get_all_actions(simulation_id)
            export_data['actions'] = [a.to_dict() for a in actions]

        # --- Timeline ---
        if 'timeline' in include_sections:
            export_data['timeline'] = SimulationRunner.get_timeline(simulation_id)

        # --- Agent Stats ---
        if 'agent_stats' in include_sections:
            export_data['agent_stats'] = SimulationRunner.get_agent_stats(simulation_id)

        # --- Posts (both platforms) ---
        if 'posts' in include_sections:
            import sqlite3
            sim_dir = os.path.join(
                os.path.dirname(__file__),
                f'../../uploads/simulations/{simulation_id}'
            )
            all_posts = []
            for platform in ('twitter', 'reddit'):
                db_path = os.path.join(sim_dir, f"{platform}_simulation.db")
                if os.path.exists(db_path):
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM post ORDER BY created_at DESC")
                        for row in cursor.fetchall():
                            post = dict(row)
                            post['platform'] = platform
                            all_posts.append(post)
                        conn.close()
                    except sqlite3.OperationalError:
                        pass
            export_data['posts'] = all_posts

        # --- Build response ---
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename_base = f"miroshark_export_{simulation_id[:12]}_{timestamp}"

        if export_format == 'json':
            buf = io.BytesIO()
            buf.write(json.dumps(export_data, indent=2, default=str, ensure_ascii=False).encode('utf-8'))
            buf.seek(0)
            return send_file(
                buf,
                mimetype='application/json',
                as_attachment=True,
                download_name=f"{filename_base}.json"
            )

        # CSV: flatten actions into a single table (the most useful tabular view)
        rows = export_data.get('actions', [])
        if not rows:
            return jsonify({
                "success": False,
                "error": _t(
                    "No action data available to export as CSV",
                    "没有可导出为 CSV 的动作数据",
                    locale,
                )
            }), 404

        fieldnames = ['round_num', 'timestamp', 'platform', 'agent_id',
                      'agent_name', 'action_type', 'action_args', 'result', 'success']

        string_buf = io.StringIO()
        writer = csv.DictWriter(string_buf, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            row_copy = dict(row)
            # Serialize nested dicts to JSON strings for CSV
            if isinstance(row_copy.get('action_args'), dict):
                row_copy['action_args'] = json.dumps(row_copy['action_args'], ensure_ascii=False)
            writer.writerow(row_copy)

        buf = io.BytesIO()
        buf.write(string_buf.getvalue().encode('utf-8'))
        buf.seek(0)
        return send_file(
            buf,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{filename_base}.csv"
        )

    except Exception as e:
        logger.error(f"Failed to export simulation data: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Comparison Endpoint ==============

@simulation_bp.route('/compare', methods=['GET'])
def compare_simulations():
    """
    Compare two completed simulations side by side.

    Query parameters:
        id1: First simulation ID (required)
        id2: Second simulation ID (required)

    Returns aggregated comparison data from both simulations:
    - Influence leaderboards (top 10 each)
    - Per-round activity timelines
    - Prediction market final prices (from polymarket SQLite if available)
    - Divergence score (0–1, higher = more divergent outcomes)

    Divergence score methodology:
        For each agent that appears in the top-10 of both runs, compute the
        normalized absolute rank difference. Agents present in one run but not
        the other contribute a penalty of 0.5 per missing agent. The final score
        is the mean across all compared agents, clamped to [0, 1].
    """
    locale = get_locale(request)
    try:
        id1 = request.args.get('id1', '').strip()
        id2 = request.args.get('id2', '').strip()

        if not id1 or not id2:
            return jsonify({"success": False, "error": _t(
                "Both id1 and id2 are required",
                "需要同时提供 id1 和 id2",
                locale,
            )}), 400

        if id1 == id2:
            return jsonify({"success": False, "error": _t(
                "id1 and id2 must be different simulations",
                "id1 和 id2 必须是不同的模拟",
                locale,
            )}), 400

        def _load_state(sim_id):
            m = SimulationManager()
            return m.get_simulation(sim_id)

        def _load_timeline_summary(sim_id):
            """Load and summarise timeline: per-round total actions, total rounds."""
            timeline = SimulationRunner.get_timeline(sim_id)
            return [
                {
                    'round_num': r['round_num'],
                    'total_actions': r['total_actions'],
                    'twitter_actions': r['twitter_actions'],
                    'reddit_actions': r['reddit_actions'],
                }
                for r in timeline
            ]

        def _load_market_prices(sim_id):
            """
            Extract per-round YES token prices from the Polymarket SQLite database.

            Reads the AmM reserve table to derive price_yes = reserve_no / (reserve_yes + reserve_no)
            per round. Returns an empty list if Polymarket was not enabled or the DB does not exist.
            """
            sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id)
            db_path = os.path.join(sim_dir, 'polymarket', 'polymarket.db')
            if not os.path.exists(db_path):
                return []
            try:
                import sqlite3
                con = sqlite3.connect(db_path)
                cur = con.cursor()
                # Try to read round-level price snapshots if they exist
                tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                prices = []

                if 'price_history' in tables:
                    # Custom table we may have written
                    rows = cur.execute(
                        "SELECT round_num, market_id, price_yes FROM price_history ORDER BY round_num, market_id"
                    ).fetchall()
                    for rn, mid, py in rows:
                        prices.append({'round_num': rn, 'market_id': mid, 'price_yes': py})
                elif 'market' in tables:
                    # Wonderwall market table: id, reserve_yes, reserve_no
                    rows = cur.execute(
                        "SELECT id, reserve_yes, reserve_no FROM market"
                    ).fetchall()
                    for mid, ry, rn in rows:
                        total = (ry or 0) + (rn or 0)
                        price_yes = (rn / total) if total > 0 else 0.5
                        prices.append({'market_id': mid, 'price_yes': round(price_yes, 4), 'round_num': None})
                con.close()
                return prices
            except Exception:
                return []

        # Load data for both simulations
        state1 = _load_state(id1)
        state2 = _load_state(id2)

        if not state1:
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {id1}",
                f"未找到模拟:{id1}",
                locale,
            )}), 404
        if not state2:
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {id2}",
                f"未找到模拟:{id2}",
                locale,
            )}), 404

        influence1 = _compute_influence_ranked(id1, top_n=10)
        influence2 = _compute_influence_ranked(id2, top_n=10)
        timeline1 = _load_timeline_summary(id1)
        timeline2 = _load_timeline_summary(id2)
        markets1 = _load_market_prices(id1)
        markets2 = _load_market_prices(id2)

        # ---- Divergence Score ----
        # Rank-based divergence: normalized mean absolute rank difference for top-10 agents
        rank_map1 = {a['agent_name']: a['rank'] for a in influence1}
        rank_map2 = {a['agent_name']: a['rank'] for a in influence2}
        all_agents = set(rank_map1) | set(rank_map2)
        if all_agents:
            diffs = []
            for name in all_agents:
                r1 = rank_map1.get(name, 15)  # penalty: treat absent agents as rank 15
                r2 = rank_map2.get(name, 15)
                diffs.append(abs(r1 - r2) / 14.0)  # normalise to [0, 1] (max diff = 14)
            divergence_score = round(min(1.0, sum(diffs) / len(diffs)), 3)
        else:
            divergence_score = 0.0

        # ---- Total activity stats ----
        def _total_actions(timeline):
            return sum(r['total_actions'] for r in timeline)

        return jsonify({
            "success": True,
            "data": {
                "id1": id1,
                "id2": id2,
                "divergence_score": divergence_score,
                "sim1": {
                    "simulation_id": id1,
                    "status": state1.status.value if state1 else None,
                    "profiles_count": state1.profiles_count if state1 else 0,
                    "total_rounds": len(timeline1),
                    "total_actions": _total_actions(timeline1),
                    "influence": influence1,
                    "timeline": timeline1,
                    "markets": markets1,
                },
                "sim2": {
                    "simulation_id": id2,
                    "status": state2.status.value if state2 else None,
                    "profiles_count": state2.profiles_count if state2 else 0,
                    "total_rounds": len(timeline2),
                    "total_actions": _total_actions(timeline2),
                    "influence": influence2,
                    "timeline": timeline2,
                    "markets": markets2,
                },
            }
        })

    except Exception as e:
        logger.error(f"Failed to compare simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Prediction Resolution Endpoint ==============

@simulation_bp.route('/<simulation_id>/resolve', methods=['POST'])
@require_admin_token
def resolve_simulation(simulation_id: str):
    """
    Record the real-world outcome of a simulation prediction.

    Auth: requires ``Authorization: Bearer $MIROSHARK_ADMIN_TOKEN``.

    Body:
        {
            "actual_outcome": "YES" | "NO",    // Required
            "notes": "Optional context"         // Optional
        }

    Reads the Polymarket price data (if available) to determine whether the
    agent consensus correctly predicted the outcome, then writes resolution.json
    to the simulation directory.

    accuracy_score:
        1.0  — agent consensus matched actual outcome
        0.5  — market was split (price_yes within 0.05 of 0.5)
        0.0  — agent consensus was wrong
        null — no Polymarket data available to compute consensus

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "actual_outcome": "YES",
                "predicted_consensus": "YES",   // null if no market data
                "predicted_confidence": 0.78,   // null if no market data
                "accuracy_score": 1.0,          // null if no market data
                "notes": "...",
                "resolved_at": "2026-04-12T..."
            }
        }
    """
    import sqlite3

    locale = get_locale(request)
    try:
        data = request.get_json(force=True) or {}
        actual_outcome = (data.get("actual_outcome") or "").strip().upper()
        notes = data.get("notes", "")

        if actual_outcome not in ("YES", "NO"):
            return jsonify({
                "success": False,
                "error": _t(
                    "actual_outcome must be 'YES' or 'NO'",
                    "actual_outcome 必须为 'YES' 或 'NO'",
                    locale,
                )
            }), 400

        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

        # Attempt to read final Polymarket consensus from the SQLite database
        predicted_consensus = None
        predicted_confidence = None
        accuracy_score = None

        db_path = os.path.join(sim_dir, 'polymarket', 'polymarket.db')
        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as con:
                    cur = con.cursor()
                    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}

                    final_price_yes = None

                    if 'price_history' in tables:
                        # Read the latest round's price for the first market
                        row = cur.execute(
                            "SELECT price_yes FROM price_history ORDER BY round_num DESC, market_id LIMIT 1"
                        ).fetchone()
                        if row:
                            final_price_yes = row[0]
                    elif 'market' in tables:
                        row = cur.execute(
                            "SELECT reserve_yes, reserve_no FROM market LIMIT 1"
                        ).fetchone()
                        if row:
                            ry, rn = row
                            total = (ry or 0) + (rn or 0)
                            if total > 0:
                                final_price_yes = rn / total  # price_yes = reserve_no / total (Wonderwall AMM)

                if final_price_yes is not None:
                    predicted_confidence = round(float(final_price_yes), 4)
                    if abs(final_price_yes - 0.5) <= 0.05:
                        # Split market — too close to call
                        predicted_consensus = None
                        accuracy_score = 0.5
                    elif final_price_yes > 0.5:
                        predicted_consensus = "YES"
                        accuracy_score = 1.0 if actual_outcome == "YES" else 0.0
                    else:
                        predicted_consensus = "NO"
                        accuracy_score = 1.0 if actual_outcome == "NO" else 0.0

            except Exception as e:
                logger.warning(f"Could not read Polymarket data for {simulation_id}: {e}")

        resolution = {
            "simulation_id": simulation_id,
            "actual_outcome": actual_outcome,
            "predicted_consensus": predicted_consensus,
            "predicted_confidence": predicted_confidence,
            "accuracy_score": accuracy_score,
            "notes": notes,
            "resolved_at": datetime.now().isoformat(),
        }

        resolution_path = os.path.join(sim_dir, "resolution.json")
        with open(resolution_path, 'w', encoding='utf-8') as f:
            json.dump(resolution, f, ensure_ascii=False, indent=2)

        logger.info(f"Prediction resolved for {simulation_id}: actual={actual_outcome}, score={accuracy_score}")

        return jsonify({
            "success": True,
            "data": resolution
        })

    except Exception as e:
        logger.error(f"Failed to resolve simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Predictive Accuracy Ledger ==============


@simulation_bp.route('/<simulation_id>/outcome', methods=['POST', 'GET'])
def simulation_outcome(simulation_id: str):
    """Verified-Prediction annotation layer for public simulations.

    A lightweight successor to ``/resolve``: that one writes a binary
    YES/NO Polymarket-aligned resolution, this one accepts an open-ended
    "did this run predict a real event?" annotation. The two are
    complementary — a simulation can have both — and outcome.json is the
    record the public gallery and ``/verified`` filter read from.

    Body (POST):

        {
            "label": "correct" | "incorrect" | "partial",   // required
            "outcome_url": "https://...",                    // optional
            "outcome_summary": "Tweet-sized description"      // ≤280 chars
        }

    Returns the saved outcome on success. Submission requires
    ``is_public=True`` on the simulation (toggle via ``/publish``).

    GET returns the current outcome (or ``data: null``) — no publish
    gate so the embed dialog can show the existing annotation when the
    operator re-opens it.

    Auth: POST requires ``Authorization: Bearer $MIROSHARK_ADMIN_TOKEN``.
    GET is unauthenticated — the gallery and embed widgets read this.
    """
    locale = get_locale(request)
    # Gate POST writes on the admin token (GET stays public — the
    # gallery reads this and the embed dialog re-renders the existing
    # annotation when an operator re-opens it).
    if request.method == 'POST':
        expected = _load_admin_token()
        if not expected:
            logger.error(
                "outcome POST reached but %s is unset — refusing to "
                "serve (fail-closed).", _ADMIN_TOKEN_ENV_VAR,
            )
            return jsonify({
                "success": False,
                "error": _t(
                    "Admin authentication is not configured on this deployment.",
                    "此部署尚未配置管理员身份验证。",
                    locale,
                ),
            }), 503
        provided = _extract_bearer_token()
        if not provided or not hmac.compare_digest(
            provided.encode("utf-8"), expected.encode("utf-8")
        ):
            return jsonify({"success": False, "error": _t("Unauthorized", "未授权", locale)}), 401

    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

        if request.method == 'GET':
            outcome = _read_outcome_file(sim_dir)
            return jsonify({"success": True, "data": outcome})

        if not bool(getattr(state, "is_public", False)):
            return jsonify({
                "success": False,
                "error": _t(
                    "Simulation must be public to record an outcome. POST /api/simulation/<id>/publish to enable.",
                    "必须将模拟设为公开后才能记录结果。请通过 POST /api/simulation/<id>/publish 启用。",
                    locale,
                ),
            }), 403

        data = request.get_json(force=True, silent=True) or {}
        label = (data.get("label") or "").strip().lower()
        if label not in _VALID_OUTCOME_LABELS:
            return jsonify({
                "success": False,
                "error": _t(
                    "label must be one of: correct, incorrect, partial",
                    "label 必须为以下之一:correct、incorrect、partial",
                    locale,
                ),
            }), 400

        outcome_url = (data.get("outcome_url") or "").strip()
        if outcome_url and not (outcome_url.startswith("http://") or outcome_url.startswith("https://")):
            return jsonify({
                "success": False,
                "error": _t(
                    "outcome_url must be an http(s) URL",
                    "outcome_url 必须是 http(s) URL",
                    locale,
                ),
            }), 400
        if len(outcome_url) > 500:
            return jsonify({
                "success": False,
                "error": _t(
                    "outcome_url must be 500 characters or fewer",
                    "outcome_url 不能超过 500 个字符",
                    locale,
                ),
            }), 400

        outcome_summary = (data.get("outcome_summary") or "").strip()
        if len(outcome_summary) > 280:
            return jsonify({
                "success": False,
                "error": _t(
                    "outcome_summary must be 280 characters or fewer",
                    "outcome_summary 不能超过 280 个字符",
                    locale,
                ),
            }), 400

        try:
            os.makedirs(sim_dir, exist_ok=True)
        except OSError as exc:
            logger.error(f"outcome: failed to ensure sim_dir for {simulation_id}: {exc}")
            return jsonify({"success": False, "error": _t(
                "Could not persist outcome.",
                "无法保存结果。",
                locale,
            )}), 500

        record = {
            "simulation_id": simulation_id,
            "label": label,
            "outcome_url": outcome_url,
            "outcome_summary": outcome_summary,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        outcome_path = os.path.join(sim_dir, "outcome.json")
        try:
            with open(outcome_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error(f"outcome: failed to write {outcome_path}: {exc}")
            return jsonify({"success": False, "error": _t(
                "Could not persist outcome.",
                "无法保存结果。",
                locale,
            )}), 500

        logger.info(
            f"outcome: recorded label={label} for {simulation_id} (url_set={bool(outcome_url)})"
        )

        return jsonify({"success": True, "data": _read_outcome_file(sim_dir)})

    except Exception as e:
        logger.error(f"Failed to handle outcome for {simulation_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


# ============== Article Generator ==============

@simulation_bp.route('/<simulation_id>/article', methods=['POST'])
def generate_simulation_article(simulation_id: str):
    """
    Generate a 400-600 word publishable article brief from simulation results.

    Returns a Substack-style article with abstract, key findings, market dynamics,
    implications, and a caveats paragraph. Result is cached in generated_article.json
    inside the simulation directory so re-opening the drawer does not re-call the LLM.

    Request body (JSON, optional):
        {
            "force_regenerate": false,    // Re-generate even if cached
            "share_url": "https://..."    // Optional share permalink to append
        }

    Returns:
        {
            "success": true,
            "data": {
                "article_text": "...",
                "cached": false
            }
        }
    """
    locale = get_locale(request)
    try:
        body = request.get_json(silent=True) or {}
        force_regenerate = body.get('force_regenerate', False)
        share_url = body.get('share_url', '')

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": _t(f"Simulation not found: {simulation_id}", f"未找到模拟:{simulation_id}", locale)
            }), 404

        # --- Cache check ---
        cache_path = os.path.join(sim_dir, 'generated_article.json')
        if not force_regenerate and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                return jsonify({
                    "success": True,
                    "data": {
                        "article_text": cached.get('article_text', ''),
                        "cached": True
                    }
                })
            except Exception:
                pass  # corrupt cache — fall through to regenerate

        # --- Gather context ---
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        config = manager.get_simulation_config(simulation_id)

        scenario = ''
        if config:
            scenario = config.get('simulation_requirement', '')
        if not scenario and state:
            scenario = getattr(state, 'simulation_requirement', '') or ''

        run_state = SimulationRunner.get_run_state(simulation_id)
        total_rounds = 0
        agent_count = 0
        if run_state:
            total_rounds = run_state.current_round
        if state:
            agent_count = state.profiles_count

        # Timeline stats: peak activity, quiet stretches
        timeline = SimulationRunner.get_timeline(simulation_id)
        top_rounds = sorted(timeline, key=lambda r: r['total_actions'], reverse=True)[:3]
        top_rounds_summary = ', '.join(
            f"round {r['round_num']} ({r['total_actions']} actions)"
            for r in top_rounds
        )
        total_actions_all = sum(r['total_actions'] for r in timeline) if timeline else 0

        # Top 3 influence leaders
        leaders = _compute_influence_ranked(simulation_id, top_n=3)
        leader_lines = []
        for agent in leaders:
            name = agent.get('agent_name', 'Unknown')
            score = agent.get('influence_score', 0)
            posts = agent.get('posts_created', 0)
            engagement = agent.get('engagement_received', 0)
            leader_lines.append(
                f"- {name}: influence score {score}, {posts} posts, {engagement} engagements received"
            )
        leaders_text = '\n'.join(leader_lines) if leader_lines else 'No agent data available.'

        # Top-engaged posts — read actions.jsonl per platform, rank CREATE_POSTs
        # by incoming LIKE_POST / REPOST / QUOTE_POST / CREATE_COMMENT volume.
        def _top_posts(platform: str, limit: int = 5):
            path = os.path.join(sim_dir, platform, 'actions.jsonl')
            if not os.path.exists(path):
                return []
            posts = {}  # post_id -> {content, author, round, likes, reposts, replies}
            engagement = {}  # post_id -> weighted engagement score
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception:
                            continue
                        atype = (rec.get('action_type') or '').upper()
                        args = rec.get('action_args') or {}
                        pid = args.get('post_id')
                        if atype == 'CREATE_POST' and pid is not None:
                            posts[pid] = {
                                'content': (args.get('content') or '').strip(),
                                'author': rec.get('agent_name') or '?',
                                'round': rec.get('round'),
                                'likes': 0, 'reposts': 0, 'replies': 0, 'quotes': 0,
                            }
                        elif atype == 'LIKE_POST' and pid is not None:
                            engagement[pid] = engagement.get(pid, 0) + 1
                            if pid in posts:
                                posts[pid]['likes'] += 1
                        elif atype in ('REPOST',) and pid is not None:
                            engagement[pid] = engagement.get(pid, 0) + 3
                            if pid in posts:
                                posts[pid]['reposts'] += 1
                        elif atype == 'QUOTE_POST' and pid is not None:
                            engagement[pid] = engagement.get(pid, 0) + 3
                            if pid in posts:
                                posts[pid]['quotes'] += 1
                        elif atype == 'CREATE_COMMENT' and pid is not None:
                            engagement[pid] = engagement.get(pid, 0) + 2
                            if pid in posts:
                                posts[pid]['replies'] += 1
            except Exception:
                return []
            ranked = sorted(
                (p for p in posts.values() if p['content']),
                key=lambda p: p['likes'] * 1 + p['reposts'] * 3 + p['quotes'] * 3 + p['replies'] * 2,
                reverse=True,
            )
            return ranked[:limit]

        viral_lines = []
        for plat in ('twitter', 'reddit'):
            for post in _top_posts(plat, limit=3):
                text = post['content'][:220].replace('\n', ' ').strip()
                eng = post['likes'] + post['reposts'] + post['quotes'] + post['replies']
                viral_lines.append(
                    f"- Platform: {plat}. Author: {post['author']}. Round: {post['round']}. "
                    f"Engagement: {post['likes']} likes, {post['reposts']} reposts, "
                    f"{post['replies']} replies (total {eng}).\n  Content: {text}"
                )
        viral_posts_text = '\n'.join(viral_lines) if viral_lines else 'No viral posts captured.'

        # Belief-shift: first vs last trajectory snapshot
        belief_shift_text = ''
        trajectory_path = os.path.join(sim_dir, "trajectory.json")
        if os.path.exists(trajectory_path):
            try:
                with open(trajectory_path, 'r', encoding='utf-8') as f:
                    traj = json.load(f)
                snaps = traj.get('snapshots') or []

                def _stance_dist(snap):
                    bp = snap.get('belief_positions') or {}
                    stances = [
                        sum(p.values()) / len(p)
                        for p in bp.values() if isinstance(p, dict) and p
                    ]
                    if not stances:
                        return None
                    total = len(stances)
                    nb = sum(1 for s in stances if s > 0.2)
                    nbe = sum(1 for s in stances if s < -0.2)
                    return {
                        'bullish': round(nb / total * 100, 1),
                        'bearish': round(nbe / total * 100, 1),
                        'neutral': round((total - nb - nbe) / total * 100, 1),
                        'round': snap.get('round_num'),
                    }
                first = next((_stance_dist(s) for s in snaps if _stance_dist(s)), None)
                last = next((_stance_dist(s) for s in reversed(snaps) if _stance_dist(s)), None)
                if first and last:
                    belief_shift_text = (
                        f"Opening sentiment (round {first['round']}): "
                        f"{first['bullish']}% bullish / {first['neutral']}% neutral / {first['bearish']}% bearish. "
                        f"Closing sentiment (round {last['round']}): "
                        f"{last['bullish']}% bullish / {last['neutral']}% neutral / {last['bearish']}% bearish. "
                        f"Net shift: bullish Δ {round(last['bullish'] - first['bullish'], 1):+}%, "
                        f"bearish Δ {round(last['bearish'] - first['bearish'], 1):+}%."
                    )
            except Exception:
                pass

        # Polymarket: final prices + biggest round-over-round swing
        market_summary = ''
        market_swing_text = ''
        polymarket_db = _polymarket_db_path(simulation_id)
        if os.path.exists(polymarket_db):
            try:
                import sqlite3
                with sqlite3.connect(polymarket_db) as con:
                    cur = con.cursor()
                    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if 'market' in tables:
                        rows = cur.execute(
                            "SELECT market_id, question, reserve_a, reserve_b FROM market"
                        ).fetchall()
                        market_lines = []
                        for mid, question, ra, rb in rows:
                            total = (ra or 0) + (rb or 0)
                            price_yes = round((rb / total) * 100, 1) if total > 0 else 50.0
                            market_lines.append(f'"{question}" — {price_yes}% YES')
                        market_summary = '; '.join(market_lines)
                    if 'trade' in tables:
                        # Biggest absolute price swing in a single trade (YES-normalized)
                        trade_rows = cur.execute(
                            "SELECT market_id, outcome, price, shares, created_at FROM trade "
                            "ORDER BY created_at ASC"
                        ).fetchall()
                        prev_yes = {}
                        biggest = None  # (abs_delta, mid, from_pct, to_pct, shares)
                        for mid, outcome, price, shares, _ts in trade_rows:
                            yes_price = (1 - price) if (outcome or '').upper() == 'NO' else price
                            yes_price = max(0.0, min(1.0, yes_price or 0))
                            prev = prev_yes.get(mid, 0.5)
                            delta = abs(yes_price - prev)
                            if biggest is None or delta > biggest[0]:
                                biggest = (delta, mid, prev, yes_price, shares)
                            prev_yes[mid] = yes_price
                        if biggest and biggest[0] > 0.02:
                            _d, _mid, _from, _to, _sh = biggest
                            market_swing_text = (
                                f"Largest single-trade swing: market {_mid} moved "
                                f"{round(_from * 100, 1)}% → {round(_to * 100, 1)}% YES "
                                f"on a {round(_sh or 0, 1)}-share trade."
                            )
            except Exception:
                pass

        market_block = ''
        if market_summary:
            market_block += f"\nPrediction market final prices: {market_summary}"
        if market_swing_text:
            market_block += f"\n{market_swing_text}"

        share_cta = (
            f"\n\n---\n*Explore this simulation yourself: {share_url}*"
            if share_url else ""
        )

        # --- LLM call ---
        trajectory_line = f"\n**Opinion trajectory:** {belief_shift_text}" if belief_shift_text else ""

        prompt = f"""You are a technology journalist writing a Substack-style dispatch about a multi-agent simulation you just witnessed. The tone is sharp, specific, and a little skeptical — not a press release, not a listicle. Target 500-750 words.

**Scenario the simulation explored:** {scenario or 'A multi-agent social simulation'}
**Scale:** {agent_count} autonomous AI agents, {total_rounds} rounds, {total_actions_all} total actions.
**Peak activity rounds:** {top_rounds_summary or 'N/A'}{trajectory_line}{market_block}

**Top influence leaders (by posts × engagement received):**
{leaders_text}

**Most-engaged posts (use at most one as a blockquote — quote ONLY the Content string, never the metadata line, and attribute the author in prose):**
{viral_posts_text}

## Writing instructions

Lead with a hook — the single most counterintuitive or striking finding from the data above, stated as a concrete number. Do not open with "In this simulation..." or any variation of "I watched X agents do Y".

Structure (no explicit headings — just flowing paragraphs):
1. **The hook (1-2 sentences).** One surprising number, stated plainly.
2. **The setup (1 paragraph).** What scenario was simulated, how many agents, what platforms — but woven into a narrative, not listed.
3. **The turn (1-2 paragraphs).** What actually happened — peak activity rounds, the moment opinion shifted, a viral post that changed the temperature. Quote one post verbatim (shortened if needed) with attribution. Use `**bold**` for punchy numbers.
4. **The dynamics (1 paragraph).** How did the top influencers drive it? Did they converge or did a minority hold the line?
5. **What it means (1 paragraph).** What does this tell us about the real-world scenario? Be specific and avoid platitudes. If the prediction market moved, say which way and why it matters.
6. **The caveat (2 sentences max).** AI agents are not people. Name one specific limitation of *this* simulation — not a generic disclaimer.

Style rules:
- Use concrete numbers from the data. "**42%**" beats "nearly half".
- Name specific agents. "*Mallku kept posting measured takes while the feed polarized*" beats "one agent stood apart".
- Exactly one blockquote, used only for a real post from the viral-posts list.
- No corporate hedging. No "it is important to note".
- No section headings, no bullet lists, no tables. This is a dispatch, not a report.
- Start with a title on its own line (one short sentence, specific, no clickbait), then a one-line italicized dek, then a blank line, then the body.
{share_cta}

Return only the article in Markdown."""

        llm = create_smart_llm_client(timeout=150.0)
        article_text = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=2200,
        )

        # --- Cache result ---
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({'article_text': article_text, 'generated_at': datetime.now(timezone.utc).isoformat()}, f)
        except Exception as e:
            logger.warning(f"Failed to cache generated article for {simulation_id}: {e}")

        return jsonify({
            "success": True,
            "data": {
                "article_text": article_text,
                "cached": False
            }
        })

    except Exception as e:
        logger.error(f"Failed to generate article for {simulation_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Trace Interview ==============


def _build_agent_trace(simulation_id: str, agent_name: str) -> dict:
    """
    Build a per-round trace of an agent's simulation activity from action JSONL logs.

    Returns:
        {
            'rounds': {round_num: {'posts': [...], 'other_actions': [...]}},
            'total_posts': int,
            'total_engagements_received': int,
            'platforms': [str, ...]
        }
    """
    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

    rounds: dict = {}
    total_posts = 0
    total_engagements = 0
    platforms_active: set = set()

    ENGAGEMENT_TYPES = frozenset({
        'LIKE_POST', 'REPOST', 'QUOTE_POST', 'LIKE_COMMENT', 'CREATE_COMMENT',
    })

    for platform in ('twitter', 'reddit'):
        actions_path = os.path.join(sim_dir, platform, 'actions.jsonl')
        if not os.path.exists(actions_path):
            continue

        with open(actions_path, 'r', encoding='utf-8') as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if event.get('event_type') in (
                    'simulation_start', 'round_start', 'round_end', 'simulation_end'
                ):
                    continue

                round_num = event.get('round', 0)

                # Track this agent's own actions
                if event.get('agent_name') == agent_name:
                    platforms_active.add(platform)
                    if round_num not in rounds:
                        rounds[round_num] = {'posts': [], 'other_actions': []}

                    action_type = event.get('action_type', '')
                    args = event.get('action_args') or {}

                    if action_type == 'CREATE_POST':
                        content = args.get('content', '')
                        rounds[round_num]['posts'].append({
                            'platform': platform,
                            'content': content,
                        })
                        total_posts += 1
                    elif action_type and action_type != 'DO_NOTHING':
                        rounds[round_num]['other_actions'].append({
                            'platform': platform,
                            'type': action_type,
                        })

                # Track engagements received by this agent
                elif event.get('action_type') in ENGAGEMENT_TYPES:
                    args = event.get('action_args') or {}
                    target = (
                        args.get('post_author_name')
                        or args.get('original_author_name')
                    )
                    if target == agent_name:
                        total_engagements += 1

    return {
        'rounds': rounds,
        'total_posts': total_posts,
        'total_engagements_received': total_engagements,
        'platforms': sorted(platforms_active),
    }


@simulation_bp.route('/<simulation_id>/agents/<agent_name>/trace-interview', methods=['POST'])
def trace_interview_agent(simulation_id: str, agent_name: str):
    """
    Post-simulation trace-grounded agent interview.

    Does NOT require the simulation environment to be running. Works on completed
    simulations by injecting the agent's round-by-round simulation trace as LLM context,
    enabling questions like "Why did you change your position in round 4?".

    Supports multi-turn: pass previous Q&A in the 'history' field to continue the
    conversation with full context.

    Request body (JSON):
        {
            "question": "Why did you post so aggressively in round 3?",
            "history": [                        // Optional: prior Q&A for multi-turn
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

    Returns:
        {
            "success": true,
            "data": {
                "agent_name": "AgentName",
                "question": "...",
                "answer": "...",
                "total_qa": 3           // total Q&A pairs saved for this agent
            }
        }
    """
    locale = get_locale(request)
    try:
        body = request.get_json(silent=True) or {}
        question = (body.get('question') or '').strip()
        history = body.get('history') or []

        if not question:
            return jsonify({"success": False, "error": _t(
                "Please provide a question",
                "请提供问题",
                locale,
            )}), 400

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        # --- Get simulation scenario ---
        scenario = ''
        config = SimulationManager().get_simulation_config(simulation_id)
        if config:
            scenario = config.get('simulation_requirement', '') or ''

        # --- Get agent profile ---
        profile_lines = []
        profiles_file = os.path.join(sim_dir, 'reddit_profiles.json')
        if os.path.exists(profiles_file):
            try:
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                for p in profiles:
                    pname = p.get('user_name') or p.get('username') or p.get('name') or ''
                    if pname.lower() == agent_name.lower():
                        bio = p.get('bio', '')
                        persona = p.get('persona', '')
                        profession = p.get('profession', '')
                        topics = p.get('interested_topics', [])
                        age = p.get('age', '')
                        country = p.get('country', '')

                        if bio:
                            profile_lines.append(f"Bio: {bio}")
                        if persona and isinstance(persona, str):
                            profile_lines.append(f"Persona: {persona[:300]}")
                        elif persona and isinstance(persona, dict):
                            if persona.get('archetype'):
                                profile_lines.append(f"Archetype: {persona['archetype']}")
                            if persona.get('bio'):
                                profile_lines.append(f"Persona bio: {persona['bio'][:200]}")
                        if profession:
                            profile_lines.append(f"Profession: {profession}")
                        if topics:
                            profile_lines.append(f"Interested topics: {', '.join(str(t) for t in topics[:6])}")
                        if age:
                            profile_lines.append(f"Age: {age}")
                        if country:
                            profile_lines.append(f"Country: {country}")
                        break
            except Exception as e:
                logger.warning(f"Could not load profile for {agent_name}: {e}")

        profile_summary = '\n'.join(profile_lines) if profile_lines else 'No profile data available.'

        # --- Build simulation trace ---
        trace = _build_agent_trace(simulation_id, agent_name)

        trace_lines = []
        for round_num in sorted(trace['rounds'].keys()):
            round_data = trace['rounds'][round_num]
            posts = round_data.get('posts', [])
            other_actions = round_data.get('other_actions', [])

            for post in posts:
                content = post['content'][:250] if post['content'] else ''
                if content:
                    trace_lines.append(f"Round {round_num} [{post['platform']}] POST: \"{content}\"")

            if other_actions:
                action_types = ', '.join(sorted({a['type'] for a in other_actions}))
                trace_lines.append(f"Round {round_num}: {action_types}")

        if not trace_lines:
            trace_text = "No recorded actions found for this agent in this simulation."
        else:
            trace_text = '\n'.join(trace_lines)

        # --- Build LLM messages ---
        system_content = (
            f"You are {agent_name}, an AI agent who just participated in a multi-agent "
            f"social media simulation about: \"{scenario or 'a prediction scenario'}\".\n\n"
            f"Your profile:\n{profile_summary}\n\n"
            f"Here is everything you did during the simulation, round by round:\n{trace_text}\n\n"
            f"Answer questions about your simulation experience IN CHARACTER as {agent_name}. "
            f"Cite specific posts you made and actions you took. Reference exact round numbers "
            f"when relevant. Be concise (2-4 paragraphs), specific, and stay true to your persona."
        )

        messages = [{"role": "system", "content": system_content}]

        # Append validated conversation history for multi-turn support
        for msg in history:
            if (
                isinstance(msg, dict)
                and msg.get('role') in ('user', 'assistant')
                and isinstance(msg.get('content'), str)
                and msg['content'].strip()
            ):
                messages.append({"role": msg['role'], "content": msg['content']})

        messages.append({"role": "user", "content": question})

        # --- LLM call ---
        llm = create_smart_llm_client(timeout=90.0)
        answer = llm.chat(messages=messages, temperature=0.75, max_tokens=800)

        # --- Persist transcript ---
        interviews_dir = os.path.join(sim_dir, 'interviews')
        os.makedirs(interviews_dir, exist_ok=True)

        safe_name = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in agent_name)
        transcript_path = os.path.join(interviews_dir, f'{safe_name}.json')

        transcript = []
        if os.path.exists(transcript_path):
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    transcript = existing.get('qa_pairs', [])
            except Exception:
                pass

        transcript.append({
            'question': question,
            'answer': answer,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })

        try:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'agent_name': agent_name,
                    'simulation_id': simulation_id,
                    'qa_pairs': transcript,
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save interview transcript for {agent_name}: {e}")

        return jsonify({
            "success": True,
            "data": {
                "agent_name": agent_name,
                "question": question,
                "answer": answer,
                "total_qa": len(transcript),
            }
        })

    except Exception as e:
        logger.error(f"Trace interview failed for {agent_name} in {simulation_id}: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/interviews/<agent_name>', methods=['GET'])
def get_agent_interview_transcript(simulation_id: str, agent_name: str):
    """
    Retrieve the saved interview transcript for an agent.

    Returns the full list of Q&A pairs previously saved for this agent,
    or an empty transcript if none exists yet.

    Returns:
        {
            "success": true,
            "data": {
                "agent_name": "AgentName",
                "qa_pairs": [
                    {"question": "...", "answer": "...", "timestamp": "..."},
                    ...
                ],
                "total_qa": 3
            }
        }
    """
    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        safe_name = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in agent_name)
        transcript_path = os.path.join(sim_dir, 'interviews', f'{safe_name}.json')

        if not os.path.exists(transcript_path):
            return jsonify({
                "success": True,
                "data": {
                    "agent_name": agent_name,
                    "qa_pairs": [],
                    "total_qa": 0,
                }
            })

        with open(transcript_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        qa_pairs = data.get('qa_pairs', [])
        return jsonify({
            "success": True,
            "data": {
                "agent_name": agent_name,
                "qa_pairs": qa_pairs,
                "total_qa": len(qa_pairs),
            }
        })

    except Exception as e:
        logger.error(f"Failed to get interview transcript for {agent_name}: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Browser Push Notification Endpoints ==============

@simulation_bp.route('/push/vapid-public-key', methods=['GET'])
def get_push_vapid_public_key():
    """
    Return the VAPID public key for the frontend applicationServerKey.

    The key is generated on first call and cached on disk in
    uploads/vapid_keys.json. Returns null if pywebpush is not installed.

    Returns:
        {
            "success": true,
            "data": {
                "public_key": "<url-safe base64 uncompressed EC point>"
            }
        }
    """
    try:
        from ..services.push_notification_service import get_vapid_public_key
        key = get_vapid_public_key()
        return jsonify({
            "success": True,
            "data": {"public_key": key}
        })
    except Exception as e:
        logger.error(f"Failed to get VAPID public key: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@simulation_bp.route('/push/subscribe', methods=['POST'])
def subscribe_push_notification():
    """
    Store a Web Push subscription for a simulation.

    The subscription is tied to a simulation_id so the backend can fire
    a notification when that specific simulation completes.

    Request body:
        {
            "simulation_id": "sim_xxxx",
            "subscription": {
                "endpoint": "https://fcm.googleapis.com/...",
                "keys": {
                    "p256dh": "...",
                    "auth": "..."
                }
            }
        }

    Returns:
        { "success": true }
    """
    locale = get_locale(request)
    try:
        data = request.get_json(force=True) or {}
        simulation_id = data.get('simulation_id', '').strip()
        subscription = data.get('subscription')

        if not simulation_id:
            return jsonify({"success": False, "error": _t(
                "simulation_id is required",
                "缺少 simulation_id",
                locale,
            )}), 400
        if not subscription or not isinstance(subscription, dict):
            return jsonify({"success": False, "error": _t(
                "subscription object is required",
                "缺少 subscription 对象",
                locale,
            )}), 400
        if not subscription.get('endpoint'):
            return jsonify({"success": False, "error": _t(
                "subscription.endpoint is required",
                "缺少 subscription.endpoint",
                locale,
            )}), 400

        try:
            validate_simulation_id(simulation_id)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        from ..services.push_notification_service import save_subscription
        save_subscription(simulation_id, subscription)

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Failed to store push subscription: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@simulation_bp.route('/push/test', methods=['POST'])
def test_push_notification():
    """
    Send a test push notification immediately.

    Useful for verifying that the browser permission and VAPID setup work
    before waiting for a long simulation to complete.

    Request body:
        { "simulation_id": "sim_xxxx" }

    Returns:
        { "success": true }
    """
    locale = get_locale(request)
    try:
        data = request.get_json(force=True) or {}
        simulation_id = data.get('simulation_id', '').strip()

        if not simulation_id:
            return jsonify({"success": False, "error": _t(
                "simulation_id is required",
                "缺少 simulation_id",
                locale,
            )}), 400

        try:
            validate_simulation_id(simulation_id)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        from ..services.push_notification_service import send_push_notification
        send_push_notification(
            simulation_id=simulation_id,
            title="MiroShark — test notification",
            body="Push notifications are working. You'll be notified when your simulation completes.",
            url=f'/simulation/{simulation_id}/start',
        )

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Failed to send test push notification: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============================================================
# Director Mode — Mid-Simulation Event Injection
# ============================================================

@simulation_bp.route('/<simulation_id>/director/inject', methods=['POST'])
def inject_director_event(simulation_id: str):
    """
    Inject a breaking event into a running simulation (Director Mode).

    The event is queued and consumed by the simulation loop at the next
    round boundary. All agents receive the event as context before
    generating their next round of actions.

    Request (JSON):
        {
            "event_text": "Central bank unexpectedly raised rates by 100bps"
        }

    Returns:
        {
            "success": true,
            "event": { ... },
            "total_events": 2
        }
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
    from director_events import add_event, get_event_count

    locale = get_locale(request)
    try:
        data = request.get_json() or {}
        event_text = (data.get('event_text') or '').strip()

        if not event_text:
            return jsonify({"success": False, "error": _t(
                "event_text is required",
                "缺少 event_text",
                locale,
            )}), 400

        if len(event_text) > 500:
            return jsonify({"success": False, "error": _t(
                "event_text must be under 500 characters",
                "event_text 不能超过 500 个字符",
                locale,
            )}), 400

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        # Check simulation is running
        state = SimulationRunner.get_run_state(simulation_id)
        if not state or state.runner_status not in [RunnerStatus.RUNNING]:
            return jsonify({"success": False, "error": _t(
                "Simulation is not currently running",
                "模拟当前未在运行",
                locale,
            )}), 400

        # Enforce max 10 events per simulation
        total = get_event_count(sim_dir)
        if total >= 10:
            return jsonify({"success": False, "error": _t(
                "Maximum 10 events per simulation reached",
                "每次模拟最多 10 个事件,已达上限",
                locale,
            )}), 400

        current_round = state.current_round or 0
        event = add_event(sim_dir, event_text, current_round)

        return jsonify({
            "success": True,
            "event": event,
            "total_events": total + 1,
        })

    except Exception as e:
        logger.error(f"Failed to inject director event: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/director/events', methods=['GET'])
def get_director_events(simulation_id: str):
    """
    Get all director events (injected + pending) for a simulation.

    Returns:
        {
            "success": true,
            "events": [ ... ],
            "pending": [ ... ]
        }
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts'))
    from director_events import get_event_history, get_pending_events

    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        return jsonify({
            "success": True,
            "events": get_event_history(sim_dir),
            "pending": get_pending_events(sim_dir),
        })

    except Exception as e:
        logger.error(f"Failed to get director events: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/interaction-network', methods=['GET'])
def get_interaction_network(simulation_id: str):
    """
    Build an agent interaction network from simulation action JSONL logs.

    Extracts agent-to-agent edges (likes, reposts, quotes, comments, follows),
    computes degree centrality, bridge score, and echo chamber metrics.
    Results are cached in network.json.
    """

    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        cache_path = os.path.join(sim_dir, "network.json")
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            return jsonify({"success": True, "data": cached})

        INTERACTION_TYPES = frozenset({
            'LIKE_POST', 'REPOST', 'QUOTE_POST', 'CREATE_COMMENT',
            'LIKE_COMMENT', 'DISLIKE_POST', 'DISLIKE_COMMENT', 'FOLLOW',
        })

        agents = {}
        edges = {}

        def _ensure_agent(name, platform):
            if name not in agents:
                agents[name] = {'name': name, 'platforms': set(), 'actions': 0}
            agents[name]['platforms'].add(platform)

        for platform in ('twitter', 'reddit', 'polymarket'):
            actions_path = os.path.join(sim_dir, platform, 'actions.jsonl')
            if not os.path.exists(actions_path):
                continue

            with open(actions_path, 'r', encoding='utf-8') as fh:
                for raw_line in fh:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    if event.get('event_type') in (
                        'simulation_start', 'round_start', 'round_end', 'simulation_end'
                    ):
                        continue

                    agent_name = event.get('agent_name')
                    if not agent_name:
                        continue

                    action_type = event.get('action_type', '')
                    args = event.get('action_args') or {}
                    _ensure_agent(agent_name, platform)
                    agents[agent_name]['actions'] += 1

                    if action_type == 'CREATE_POST':
                        continue

                    if action_type not in INTERACTION_TYPES:
                        continue

                    target = None
                    if action_type == 'FOLLOW':
                        target = args.get('target_user_name')
                    else:
                        target = (
                            args.get('post_author_name')
                            or args.get('original_author_name')
                            or args.get('comment_author_name')
                        )

                    if not target or target == agent_name:
                        continue

                    _ensure_agent(target, platform)

                    edge_key = (agent_name, target)
                    if edge_key not in edges:
                        edges[edge_key] = {
                            'source': agent_name,
                            'target': target,
                            'weight': 0,
                            'types': {},
                            'platforms': set(),
                        }
                    edges[edge_key]['weight'] += 1
                    edges[edge_key]['types'][action_type] = edges[edge_key]['types'].get(action_type, 0) + 1
                    edges[edge_key]['platforms'].add(platform)

        if not agents:
            return jsonify({
                "success": True,
                "data": None,
                "message": "No interaction data available."
            })

        # Read stance data from trajectory.json
        stance_map = {}
        trajectory_path = os.path.join(sim_dir, "trajectory.json")
        if os.path.exists(trajectory_path):
            try:
                with open(trajectory_path, 'r', encoding='utf-8') as f:
                    traj = json.load(f)
                snapshots = traj.get("snapshots", [])
                if snapshots:
                    last_snap = snapshots[-1]
                    for agent_id, positions in last_snap.get("belief_positions", {}).items():
                        if positions:
                            avg = sum(positions.values()) / len(positions)
                            stance_map[agent_id] = avg
            except Exception:
                pass

        # Build influence ranking for node sizing
        ranked = _compute_influence_ranked(simulation_id)
        influence_map = {a['agent_name']: a['influence_score'] for a in ranked}
        rank_map = {a['agent_name']: a['rank'] for a in ranked}

        # Map agent names to agent IDs from profiles for stance lookup
        agent_name_to_stance = {}
        profiles_path = os.path.join(sim_dir, "profiles.json")
        if os.path.exists(profiles_path) and stance_map:
            try:
                with open(profiles_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                if isinstance(profiles, list):
                    for p in profiles:
                        aid = str(p.get('agent_id', p.get('id', '')))
                        name = p.get('name', p.get('agent_name', ''))
                        if aid in stance_map and name:
                            agent_name_to_stance[name] = stance_map[aid]
            except Exception:
                pass

        # Compute graph metrics
        in_degree = {}
        out_degree = {}
        cross_platform_edges = 0
        total_edges = len(edges)

        for edge in edges.values():
            out_degree[edge['source']] = out_degree.get(edge['source'], 0) + edge['weight']
            in_degree[edge['target']] = in_degree.get(edge['target'], 0) + edge['weight']
            if len(edge['platforms']) > 1:
                cross_platform_edges += 1

        max_possible = max(len(agents) - 1, 1)

        # Build node list
        nodes = []
        for name, data in agents.items():
            total_degree = in_degree.get(name, 0) + out_degree.get(name, 0)
            stance_val = agent_name_to_stance.get(name)
            if stance_val is not None:
                stance = 'bullish' if stance_val > 0.2 else ('bearish' if stance_val < -0.2 else 'neutral')
            else:
                stance = 'neutral'

            nodes.append({
                'id': name,
                'name': name,
                'platforms': sorted(data['platforms']),
                'primary_platform': sorted(data['platforms'])[0] if data['platforms'] else 'unknown',
                'stance': stance,
                'influence_score': influence_map.get(name, 0),
                'rank': rank_map.get(name, len(agents)),
                'in_degree': in_degree.get(name, 0),
                'out_degree': out_degree.get(name, 0),
                'total_degree': total_degree,
                'degree_centrality': round(total_degree / max_possible, 4) if max_possible > 0 else 0,
            })

        # Serialize edges
        edge_list = []
        for edge in edges.values():
            edge_list.append({
                'source': edge['source'],
                'target': edge['target'],
                'weight': edge['weight'],
                'types': edge['types'],
                'platforms': sorted(edge['platforms']),
                'is_cross_platform': len(edge['platforms']) > 1,
            })

        edge_list.sort(key=lambda e: e['weight'], reverse=True)

        # Compute insights
        top_hub = max(nodes, key=lambda n: n['in_degree']) if nodes else None
        top_bridge = None
        if nodes:
            bridge_scores = []
            for n in nodes:
                cross = sum(
                    1 for e in edge_list
                    if (e['source'] == n['id'] or e['target'] == n['id']) and e['is_cross_platform']
                )
                bridge_scores.append((n, cross))
            bridge_scores.sort(key=lambda x: x[1], reverse=True)
            if bridge_scores and bridge_scores[0][1] > 0:
                top_bridge = {
                    'agent': bridge_scores[0][0]['name'],
                    'cross_platform_edges': bridge_scores[0][1],
                }

        # Platform clustering
        platform_agents = {}
        for n in nodes:
            for p in n['platforms']:
                platform_agents.setdefault(p, set()).add(n['id'])

        same_platform_edges = 0
        for e in edge_list:
            if not e['is_cross_platform']:
                same_platform_edges += 1

        echo_chamber_score = round(same_platform_edges / total_edges * 100, 1) if total_edges > 0 else 0

        insights = {
            'top_hub': {
                'agent': top_hub['name'],
                'in_degree': top_hub['in_degree'],
                'description': f"{top_hub['name']} received {top_hub['in_degree']} interactions — more than any other agent.",
            } if top_hub and top_hub['in_degree'] > 0 else None,
            'top_bridge': {
                'agent': top_bridge['agent'],
                'cross_platform_edges': top_bridge['cross_platform_edges'],
                'description': f"{top_bridge['agent']} had the highest cross-platform interaction rate ({top_bridge['cross_platform_edges']} cross-platform edges).",
            } if top_bridge else None,
            'echo_chamber': {
                'score': echo_chamber_score,
                'description': f"{echo_chamber_score}% of interactions were within the same platform." + (
                    " Agents mostly stayed in their silos." if echo_chamber_score > 80
                    else " Moderate cross-platform activity." if echo_chamber_score > 50
                    else " Strong cross-platform engagement."
                ),
            },
            'total_nodes': len(nodes),
            'total_edges': total_edges,
        }

        result = {
            'nodes': nodes,
            'edges': edge_list,
            'insights': insights,
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

        return jsonify({"success": True, "data": result})

    except Exception as e:
        logger.error(f"Failed to compute interaction network: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Demographic Breakdown ==============

# Age buckets in display order. "unknown" is appended at the end when populated.
_DEMO_AGE_BUCKETS = ["<18", "18-24", "25-34", "35-44", "45-54", "55+"]

# Entity-type classification (mirrors WonderwallProfileGenerator's taxonomy).
_INDIVIDUAL_ENTITY_TYPES = frozenset({
    "student", "alumni", "professor", "person", "publicfigure",
    "expert", "faculty", "official", "journalist", "activist",
    "politician", "scientist", "researcher", "athlete", "artist",
    "musician", "author", "entrepreneur", "investor", "diplomat",
    "celebrity", "ceo", "executive", "regulator",
})
_INDIVIDUAL_TYPE_KEYWORDS = (
    "founder", "forecaster", "user", "trader", "influencer",
    "analyst", "advisor", "leader", "critic", "advocate",
    "commentator", "blogger", "developer", "engineer",
)
_GROUP_ENTITY_TYPES = frozenset({
    "university", "governmentagency", "organization", "ngo",
    "mediaoutlet", "company", "institution", "group", "community",
    "agency", "platform", "network", "protocol", "framework",
    "fund", "exchange", "consortium", "coalition",
})


def _demo_age_bucket(age) -> str:
    try:
        a = int(age)
    except (TypeError, ValueError):
        return "unknown"
    if a < 18:
        return "<18"
    if a <= 24:
        return "18-24"
    if a <= 34:
        return "25-34"
    if a <= 44:
        return "35-44"
    if a <= 54:
        return "45-54"
    return "55+"


def _demo_classify_archetype(entity_type) -> str:
    if not entity_type:
        return "unknown"
    et = str(entity_type).lower().replace(" ", "").replace("_", "")
    if et in _INDIVIDUAL_ENTITY_TYPES:
        return "individual"
    if et in _GROUP_ENTITY_TYPES:
        return "institutional"
    for kw in _INDIVIDUAL_TYPE_KEYWORDS:
        if kw in et:
            return "individual"
    return "unknown"


def _demo_load_profiles(sim_dir: str) -> list:
    """Load agent profiles from reddit_profiles.json (primary) or twitter_profiles.csv.

    Returns a list of dicts with normalized demographic fields.
    """
    profiles = []
    reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
    if os.path.exists(reddit_path):
        try:
            with open(reddit_path, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load reddit_profiles.json: {e}")

    if not profiles:
        twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_path):
            try:
                with open(twitter_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    profiles = list(reader)
            except Exception as e:
                logger.warning(f"Failed to load twitter_profiles.csv: {e}")

    return profiles if isinstance(profiles, list) else []


def _demo_extract_stances(sim_dir: str):
    """Return (initial_stance_map, final_stance_map), keyed by string agent_id."""
    initial_map: dict = {}
    final_map: dict = {}
    trajectory_path = os.path.join(sim_dir, "trajectory.json")
    if not os.path.exists(trajectory_path):
        return initial_map, final_map

    try:
        with open(trajectory_path, 'r', encoding='utf-8') as f:
            traj = json.load(f)
    except Exception:
        return initial_map, final_map

    snapshots = traj.get("snapshots", [])
    if not snapshots:
        return initial_map, final_map

    def _avg_by_agent(snap):
        out = {}
        for aid, positions in (snap.get("belief_positions") or {}).items():
            if positions:
                out[str(aid)] = sum(positions.values()) / len(positions)
        return out

    initial_map = _avg_by_agent(snapshots[0])
    final_map = _avg_by_agent(snapshots[-1])
    return initial_map, final_map


def _demo_bucket_accumulator():
    return {
        "count": 0,
        "stances": [],
        "deltas": [],
        "influences": [],
        "bullish": 0,
        "neutral": 0,
        "bearish": 0,
    }


def _demo_finalize_bucket(acc: dict) -> dict:
    """Convert accumulator lists into summary statistics."""
    import math as _math
    n = acc["count"]
    result = {
        "count": n,
        "final_stance_mean": None,
        "final_stance_std": None,
        "stance_volatility": None,
        "influence_mean": None,
        "bullish_pct": 0.0,
        "neutral_pct": 0.0,
        "bearish_pct": 0.0,
        "dominant_stance": "neutral",
    }
    if n <= 0:
        return result

    if acc["stances"]:
        mean = sum(acc["stances"]) / len(acc["stances"])
        var = sum((s - mean) ** 2 for s in acc["stances"]) / len(acc["stances"])
        result["final_stance_mean"] = round(mean, 3)
        result["final_stance_std"] = round(_math.sqrt(var), 3)

    if acc["deltas"]:
        result["stance_volatility"] = round(
            sum(acc["deltas"]) / len(acc["deltas"]), 3
        )

    if acc["influences"]:
        result["influence_mean"] = round(
            sum(acc["influences"]) / len(acc["influences"]), 2
        )

    stance_total = acc["bullish"] + acc["neutral"] + acc["bearish"]
    if stance_total > 0:
        result["bullish_pct"] = round(acc["bullish"] / stance_total * 100, 1)
        result["neutral_pct"] = round(acc["neutral"] / stance_total * 100, 1)
        result["bearish_pct"] = round(acc["bearish"] / stance_total * 100, 1)
        pcts = [
            (result["bullish_pct"], "bullish"),
            (result["neutral_pct"], "neutral"),
            (result["bearish_pct"], "bearish"),
        ]
        pcts.sort(reverse=True)
        result["dominant_stance"] = pcts[0][1]

    return result


def _demo_top_divergence(breakdown: dict):
    """Pick the most striking subgroup divergence across all dimensions.

    Returns a dict with {dimension, segment_a, segment_b, delta, headline} or None.
    """
    best = None
    dimension_labels = {
        "by_age_range": "Age",
        "by_gender": "Gender",
        "by_country": "Country",
        "by_archetype": "Actor type",
        "by_platform": "Primary platform",
    }

    for dim_key, dim_label in dimension_labels.items():
        segments = breakdown.get(dim_key, {})
        entries = [
            (seg, data)
            for seg, data in segments.items()
            if data.get("final_stance_mean") is not None and data.get("count", 0) >= 2
        ]
        if len(entries) < 2:
            continue

        entries.sort(key=lambda x: x[1]["final_stance_mean"], reverse=True)
        top = entries[0]
        bottom = entries[-1]
        delta = round(top[1]["final_stance_mean"] - bottom[1]["final_stance_mean"], 3)

        if delta <= 0.05:
            continue

        if best is None or delta > best["delta"]:
            best = {
                "dimension": dim_label,
                "dimension_key": dim_key,
                "segment_a": top[0],
                "segment_a_mean": top[1]["final_stance_mean"],
                "segment_b": bottom[0],
                "segment_b_mean": bottom[1]["final_stance_mean"],
                "delta": delta,
                "headline": (
                    f"{dim_label.lower()}: {top[0]} agents landed {delta} more bullish "
                    f"than {bottom[0]} agents on average."
                ),
            }

    return best


@simulation_bp.route('/<simulation_id>/demographics', methods=['GET'])
def get_demographic_breakdown(simulation_id: str):
    """
    Cross-tab agent demographics (age range, gender, country, archetype, primary
    platform) against final stance, stance volatility, and influence score.

    Uses data that already exists — persona JSON + trajectory.json + action logs —
    so no extra collection is required. Results are cached in demographics.json
    inside the simulation directory.
    """
    locale = get_locale(request)
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": _t(
                f"Simulation not found: {simulation_id}",
                f"未找到模拟:{simulation_id}",
                locale,
            )}), 404

        force_refresh = request.args.get('refresh', '').lower() in ('1', 'true', 'yes')
        cache_path = os.path.join(sim_dir, "demographics.json")
        if os.path.exists(cache_path) and not force_refresh:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return jsonify({"success": True, "data": json.load(f)})

        profiles = _demo_load_profiles(sim_dir)
        if not profiles:
            return jsonify({
                "success": True,
                "data": None,
                "message": "No agent profiles available yet."
            })

        initial_stance, final_stance = _demo_extract_stances(sim_dir)
        influence_ranked = _compute_influence_ranked(simulation_id) or []
        influence_by_name = {
            a.get('agent_name'): a.get('influence_score', 0)
            for a in influence_ranked
            if a.get('agent_name')
        }
        primary_platform_by_name = {}
        for a in influence_ranked:
            name = a.get('agent_name')
            platforms = a.get('platforms') or []
            if name and platforms:
                primary_platform_by_name[name] = platforms[0]

        # Prepare bucket containers
        buckets = {
            "by_age_range": {b: _demo_bucket_accumulator() for b in _DEMO_AGE_BUCKETS},
            "by_gender": {},
            "by_country": {},
            "by_archetype": {
                "individual": _demo_bucket_accumulator(),
                "institutional": _demo_bucket_accumulator(),
            },
            "by_platform": {},
        }
        buckets["by_age_range"]["unknown"] = _demo_bucket_accumulator()
        buckets["by_archetype"]["unknown"] = _demo_bucket_accumulator()

        agents_in_profiles = 0
        agents_with_stance = 0

        for p in profiles:
            if not isinstance(p, dict):
                continue
            agents_in_profiles += 1

            # `x or y` misfires when user_id is 0 (legitimate id, falsy value).
            user_id = next(
                (p[k] for k in ('user_id', 'agent_id', 'id')
                 if p.get(k) is not None),
                None,
            )
            # `influence_by_name` / `primary_platform_by_name` are keyed by the
            # `agent_name` field in actions.jsonl, which matches the profile's
            # `name` (display) — NOT the handle (`user_name` / `username`).
            # Prefer display name; fall back to handle for the rare profile
            # that has only a handle.
            display_name = p.get('name') or ''
            handle = p.get('user_name') or p.get('username') or ''
            user_name = display_name or handle

            age_bucket = _demo_age_bucket(p.get('age'))
            gender_raw = p.get('gender') or 'unknown'
            gender = str(gender_raw).strip().lower() or 'unknown'
            country_raw = p.get('country') or 'unknown'
            country = str(country_raw).strip() or 'unknown'
            archetype = _demo_classify_archetype(p.get('source_entity_type'))
            # Try display first, handle as fallback (belt-and-suspenders for
            # sims whose runner happened to log handles instead of display).
            primary_platform = (
                primary_platform_by_name.get(display_name)
                or primary_platform_by_name.get(handle)
                or 'inactive'
            )

            # Lookup stance + delta
            stance_val = None
            delta_val = None
            if user_id is not None:
                key = str(user_id)
                if key in final_stance:
                    stance_val = final_stance[key]
                    agents_with_stance += 1
                    if key in initial_stance:
                        delta_val = abs(stance_val - initial_stance[key])

            influence = (
                influence_by_name.get(display_name)
                if display_name in influence_by_name
                else influence_by_name.get(handle)
            )

            if gender not in buckets["by_gender"]:
                buckets["by_gender"][gender] = _demo_bucket_accumulator()
            if country not in buckets["by_country"]:
                buckets["by_country"][country] = _demo_bucket_accumulator()
            if primary_platform not in buckets["by_platform"]:
                buckets["by_platform"][primary_platform] = _demo_bucket_accumulator()

            target_buckets = [
                buckets["by_age_range"][age_bucket],
                buckets["by_gender"][gender],
                buckets["by_country"][country],
                buckets["by_archetype"][archetype],
                buckets["by_platform"][primary_platform],
            ]

            for b in target_buckets:
                b["count"] += 1
                if stance_val is not None:
                    b["stances"].append(stance_val)
                    if stance_val > 0.2:
                        b["bullish"] += 1
                    elif stance_val < -0.2:
                        b["bearish"] += 1
                    else:
                        b["neutral"] += 1
                if delta_val is not None:
                    b["deltas"].append(delta_val)
                if influence is not None:
                    b["influences"].append(influence)

        # Drop unknown buckets if empty so UI stays clean
        for dim in ("by_age_range", "by_archetype"):
            if buckets[dim].get("unknown", {}).get("count", 0) == 0:
                buckets[dim].pop("unknown", None)

        def _finalize_dimension(dim_buckets, preferred_order=None):
            # Finalize each segment to a summary dict.
            result = {seg: _demo_finalize_bucket(data) for seg, data in dim_buckets.items()}

            if preferred_order is not None:
                ordered = {k: result[k] for k in preferred_order if k in result}
                extras = {k: v for k, v in result.items() if k not in ordered}
                if extras:
                    sorted_extras = sorted(
                        extras.items(), key=lambda kv: kv[1]["count"], reverse=True
                    )
                    for k, v in sorted_extras:
                        ordered[k] = v
                result = ordered
            else:
                # Sort by descending count for readability, then alphabetically on ties.
                result = dict(sorted(
                    result.items(),
                    key=lambda kv: (-kv[1]["count"], kv[0]),
                ))
            return result

        breakdown = {
            "by_age_range": _finalize_dimension(
                buckets["by_age_range"],
                preferred_order=_DEMO_AGE_BUCKETS + ["unknown"],
            ),
            "by_gender": _finalize_dimension(buckets["by_gender"]),
            "by_country": _finalize_dimension(buckets["by_country"]),
            "by_archetype": _finalize_dimension(
                buckets["by_archetype"],
                preferred_order=["individual", "institutional", "unknown"],
            ),
            "by_platform": _finalize_dimension(buckets["by_platform"]),
        }

        top_divergence = _demo_top_divergence(breakdown)

        # Cap country breakdown to the 10 largest segments to avoid noisy tails.
        if len(breakdown["by_country"]) > 10:
            top_countries = list(breakdown["by_country"].items())[:10]
            breakdown["by_country"] = dict(top_countries)

        result = {
            "dimensions": breakdown,
            "top_divergence": top_divergence,
            "meta": {
                "total_agents": agents_in_profiles,
                "agents_with_stance": agents_with_stance,
                "has_trajectory": bool(final_stance),
                "source": "reddit_profiles.json" if os.path.exists(
                    os.path.join(sim_dir, "reddit_profiles.json")
                ) else "twitter_profiles.csv",
            },
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

        return jsonify({"success": True, "data": result})

    except Exception as e:
        logger.error(f"Failed to compute demographic breakdown: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
