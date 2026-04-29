"""
Observability API — SSE streaming, event history, and aggregated stats.

Endpoints:
    GET /api/observability/events/stream   — SSE live event stream
    GET /api/observability/events          — Paginated event history
    GET /api/observability/stats           — Aggregated token/cost/latency stats
    GET /api/observability/llm-calls       — LLM call history with filtering
"""

import json
import os
import time
from datetime import datetime

from flask import request, Response, stream_with_context

from . import observability_bp
from ..config import Config
from ..utils.event_logger import EventLogger, FileTailer


_event_logger = EventLogger()


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

@observability_bp.route('/events/stream')
def stream_events():
    """Server-Sent Events endpoint for live event streaming.

    Uses file-tailing as the primary mechanism (reliable across Flask
    debug reloader processes).  The in-memory subscriber is kept as a
    fast-path for same-process events but the global JSONL file is
    always tailed so no events are missed.
    """
    sim_id = request.args.get('simulation_id')
    raw_types = request.args.get('event_types', '')
    event_types = set(t.strip() for t in raw_types.split(',') if t.strip()) or None

    subscriber = _event_logger.subscribe(simulation_id=sim_id, event_types=event_types)

    # Always tail the global events file (handles cross-process visibility)
    from ..utils.event_logger import LOG_DIR
    global_tailer = FileTailer(os.path.join(LOG_DIR, 'events.jsonl'))

    # Also tail simulation-specific file when filtered
    sim_tailer = None
    if sim_id:
        events_file = os.path.join(
            Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id, 'events.jsonl'
        )
        sim_tailer = FileTailer(events_file)

    # Track event IDs to deduplicate between in-memory bus and file tailer
    seen_ids = set()

    def _emit(event):
        eid = event.get('event_id')
        if eid and eid in seen_ids:
            return None
        if eid:
            seen_ids.add(eid)
            # Keep seen_ids bounded
            if len(seen_ids) > 5000:
                seen_ids.clear()
        # Apply filters
        if sim_id and event.get('simulation_id') and event['simulation_id'] != sim_id:
            return None
        if event_types and event.get('event_type') not in event_types:
            return None
        return f"event: {event['event_type']}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    def generate():
        try:
            last_heartbeat = time.time()
            while True:
                emitted = False

                # In-memory events (fast path, same process)
                for event in subscriber.poll(timeout=0.5):
                    chunk = _emit(event)
                    if chunk:
                        yield chunk
                        emitted = True

                # Global JSONL file (cross-process reliable)
                for event in global_tailer.read_new_events():
                    chunk = _emit(event)
                    if chunk:
                        yield chunk
                        emitted = True

                # Simulation-specific JSONL (subprocess events)
                if sim_tailer:
                    for event in sim_tailer.read_new_events():
                        chunk = _emit(event)
                        if chunk:
                            yield chunk
                            emitted = True

                # Heartbeat every 15 seconds
                now = time.time()
                if now - last_heartbeat >= 15:
                    hb = json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat() + 'Z'})
                    yield f"event: heartbeat\ndata: {hb}\n\n"
                    last_heartbeat = now

                if not emitted:
                    time.sleep(0.5)
        finally:
            subscriber.close()
            _event_logger.unsubscribe(subscriber)

    resp = Response(stream_with_context(generate()), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    resp.headers['Connection'] = 'keep-alive'
    return resp


# ---------------------------------------------------------------------------
# Paginated event history
# ---------------------------------------------------------------------------

@observability_bp.route('/events')
def get_events():
    """Return paginated events from JSONL file."""
    sim_id = request.args.get('simulation_id')
    raw_types = request.args.get('event_types', '')
    event_types = set(t.strip() for t in raw_types.split(',') if t.strip()) or None
    # Use Flask's type-coerced get so a malformed query string (e.g. ?limit=abc)
    # falls back to the default rather than 500-ing the endpoint.
    from_line = request.args.get('from_line', default=0, type=int)
    limit = request.args.get('limit', default=200, type=int)
    filter_agent = request.args.get('agent_id', type=int)
    filter_round = request.args.get('round_num', type=int)
    filter_platform = request.args.get('platform')

    # Decide which file to read
    if sim_id:
        path = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id, 'events.jsonl')
    else:
        from ..utils.event_logger import LOG_DIR
        path = os.path.join(LOG_DIR, 'events.jsonl')

    events, total_lines = _read_jsonl_paginated(
        path, from_line, limit,
        event_types=event_types,
        agent_id=filter_agent,
        round_num=filter_round,
        platform=filter_platform,
    )

    return {
        'success': True,
        'events': events,
        'from_line': from_line,
        'total_lines': total_lines,
        'has_more': total_lines > from_line + limit,
    }


# ---------------------------------------------------------------------------
# Aggregated stats
# ---------------------------------------------------------------------------

@observability_bp.route('/stats')
def get_stats():
    """Return aggregated observability statistics."""
    sim_id = request.args.get('simulation_id')

    if sim_id:
        path = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id, 'events.jsonl')
    else:
        from ..utils.event_logger import LOG_DIR
        path = os.path.join(LOG_DIR, 'events.jsonl')

    stats = {
        'total_events': 0,
        'llm_calls': 0,
        'tokens_input': 0,
        'tokens_output': 0,
        'tokens_total': 0,
        'total_latency_ms': 0,
        'avg_latency_ms': 0,
        'errors': 0,
        'events_by_type': {},
        'models_used': {},
    }

    if not os.path.exists(path):
        return {'success': True, 'stats': stats}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                stats['total_events'] += 1
                et = event.get('event_type', 'unknown')
                stats['events_by_type'][et] = stats['events_by_type'].get(et, 0) + 1

                if et == 'llm_call':
                    data = event.get('data', {})
                    stats['llm_calls'] += 1
                    stats['tokens_input'] += data.get('tokens_input') or 0
                    stats['tokens_output'] += data.get('tokens_output') or 0
                    stats['tokens_total'] += data.get('tokens_total') or 0
                    stats['total_latency_ms'] += data.get('latency_ms') or 0

                    model = data.get('model', 'unknown')
                    stats['models_used'][model] = stats['models_used'].get(model, 0) + 1

                    if data.get('error'):
                        stats['errors'] += 1

                elif et == 'error':
                    stats['errors'] += 1
    except Exception:
        pass

    if stats['llm_calls'] > 0:
        stats['avg_latency_ms'] = round(stats['total_latency_ms'] / stats['llm_calls'], 1)

    return {'success': True, 'stats': stats}


# ---------------------------------------------------------------------------
# LLM call history
# ---------------------------------------------------------------------------

@observability_bp.route('/llm-calls')
def get_llm_calls():
    """Return LLM call events with filtering."""
    sim_id = request.args.get('simulation_id')
    caller_filter = request.args.get('caller')
    model_filter = request.args.get('model')
    min_latency = request.args.get('min_latency_ms', type=float)
    from_line = request.args.get('from_line', default=0, type=int)
    limit = request.args.get('limit', default=100, type=int)

    if sim_id:
        path = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id, 'events.jsonl')
    else:
        from ..utils.event_logger import LOG_DIR
        path = os.path.join(LOG_DIR, 'events.jsonl')

    calls = []
    line_num = 0
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_num += 1
                    if line_num <= from_line:
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get('event_type') != 'llm_call':
                        continue
                    data = event.get('data', {})
                    if caller_filter and caller_filter not in (data.get('caller') or ''):
                        continue
                    if model_filter and model_filter != data.get('model'):
                        continue
                    if min_latency and (data.get('latency_ms') or 0) < min_latency:
                        continue
                    calls.append(event)
                    if len(calls) >= limit:
                        break
        except Exception:
            pass

    return {
        'success': True,
        'calls': calls,
        'count': len(calls),
        'from_line': from_line,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_jsonl_paginated(
    path: str,
    from_line: int,
    limit: int,
    event_types=None,
    agent_id=None,
    round_num=None,
    platform=None,
):
    """Read and filter JSONL events with pagination."""
    events = []
    total_lines = 0

    if not os.path.exists(path):
        return events, total_lines

    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                total_lines += 1
                if total_lines <= from_line:
                    continue
                if len(events) >= limit:
                    continue  # keep counting total_lines

                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event_types and event.get('event_type') not in event_types:
                    continue
                if agent_id is not None and event.get('agent_id') != agent_id:
                    continue
                if round_num is not None and event.get('round_num') != round_num:
                    continue
                if platform and event.get('platform') != platform:
                    continue

                events.append(event)
    except Exception:
        pass

    return events, total_lines
