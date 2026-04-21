"""MiroShark CLI — thin HTTP client for a running MiroShark backend.

Run the server first (`./miroshark` from the repo root), then drive it with::

    python -m cli ask "Will the EU AI Act survive trilogue?"
    python -m cli list
    python -m cli status sim_abc123
    python -m cli report sim_abc123
    python -m cli publish sim_abc123 --public

The CLI hits ``MIROSHARK_API_URL`` (default ``http://localhost:5001``) — no
local Neo4j/LLM setup required beyond what the backend already has.

Deliberately dependency-light: uses only ``argparse`` + ``urllib`` so it can
run as ``python cli.py ...`` from a vanilla Python 3.11 with no extras.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Optional
from urllib import error as urlerror
from urllib import request as urlrequest


DEFAULT_BASE_URL = "http://localhost:5001"


def _base_url() -> str:
    return (os.environ.get("MIROSHARK_API_URL") or DEFAULT_BASE_URL).rstrip("/")


def _api(
    method: str,
    path: str,
    body: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = 120.0,
) -> dict:
    url = _base_url() + path
    if params:
        from urllib.parse import urlencode
        url += ("&" if "?" in url else "?") + urlencode(params)

    data: Optional[bytes] = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urlerror.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else "{}"
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"success": False, "error": f"HTTP {e.code}: {raw[:200]}"}
        parsed.setdefault("_http_status", e.code)
        return parsed
    except urlerror.URLError as e:
        return {"success": False, "error": f"connection error: {e.reason}"}

    try:
        return json.loads(raw)
    except Exception as e:
        return {"success": False, "error": f"invalid JSON from server: {e}"}


def _die(msg: str, code: int = 1) -> "NoReturn":  # noqa: F821
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_ask(args: argparse.Namespace) -> int:
    res = _api("POST", "/api/simulation/ask", body={"question": args.question})
    if not res.get("success"):
        _die(res.get("error", "unknown error"))
    d = res["data"]
    if args.json:
        _print_json(d)
        return 0
    print(f"title: {d['title']}")
    print(f"simulation_requirement:\n  {d['simulation_requirement']}")
    print(f"key_actors: {', '.join(d.get('key_actors', []))}")
    print(f"suggested_platforms: {', '.join(d.get('suggested_platforms', []))}")
    print(f"seed_document ({len(d['seed_document'])} chars):")
    print(d["seed_document"][:600] + ("..." if len(d["seed_document"]) > 600 else ""))
    print(f"\ncached: {d.get('cached', False)}  model: {d.get('model', '?')}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    res = _api("GET", "/api/simulation/list")
    if not res.get("success"):
        # Fall back to projects list — different backends expose different lists.
        res = _api("GET", "/api/graph/projects")
    if not res.get("success"):
        _die(res.get("error", "list failed"))
    if args.json:
        _print_json(res["data"])
        return 0
    items = res.get("data") or []
    if not isinstance(items, list):
        _print_json(items)
        return 0
    for it in items:
        sid = it.get("simulation_id") or it.get("project_id") or "?"
        status = it.get("status") or "?"
        name = it.get("name") or it.get("scenario") or ""
        print(f"{sid}  [{status}]  {name}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    res = _api("GET", f"/api/simulation/{args.simulation_id}/run-status")
    if args.json:
        _print_json(res)
        return 0
    if not res.get("success"):
        _die(res.get("error", "status failed"))
    d = res.get("data") or {}
    print(f"simulation_id: {args.simulation_id}")
    print(f"status:        {d.get('status') or d.get('runner_status')}")
    print(f"round:         {d.get('current_round')}/{d.get('total_rounds', '?')}")
    print(f"profiles:      {d.get('profiles_count')}")
    return 0


def cmd_frame(args: argparse.Namespace) -> int:
    params = {}
    if args.platforms:
        params["platforms"] = args.platforms
    res = _api(
        "GET",
        f"/api/simulation/{args.simulation_id}/frame/{args.round}",
        params=params or None,
    )
    if not res.get("success"):
        _die(res.get("error", "frame failed"))
    if args.json:
        _print_json(res["data"])
        return 0
    d = res["data"]
    print(f"round {d['round_num']}  active_agents={d['active_agents_count']}")
    print(f"action_counts: {d['action_counts']}")
    if d.get("market_prices"):
        for mp in d["market_prices"]:
            print(f"  market {mp['market_id']}: yes={mp['price_yes']} (as of r{mp.get('as_of_round')})")
    if d.get("belief"):
        b = d["belief"]
        print(f"belief r{b['round_num']}: {b['bullish_pct']}% bull / {b['neutral_pct']}% neut / {b['bearish_pct']}% bear")
    print(f"actions: {len(d['actions'])}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    res = _api(
        "POST",
        f"/api/simulation/{args.simulation_id}/publish",
        body={"public": not args.unpublish},
    )
    if args.json:
        _print_json(res)
        return 0
    if not res.get("success"):
        _die(res.get("error", "publish failed"))
    is_pub = res["data"]["is_public"]
    verb = "published" if is_pub else "unpublished"
    print(f"{args.simulation_id} {verb} — embed URL now {'active' if is_pub else '403'}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    res = _api("GET", f"/api/report/{args.simulation_id}")
    if args.json:
        _print_json(res)
        return 0
    if not res.get("success"):
        _die(res.get("error", "report failed"))
    d = res.get("data") or {}
    print(f"=== {d.get('title', 'Report')} ===\n")
    print(d.get("summary", ""))
    for s in d.get("sections", []) or []:
        print(f"\n## {s.get('title', '')}\n")
        print(s.get("content", ""))
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    try:
        with urlrequest.urlopen(_base_url() + "/health", timeout=5) as resp:
            print(resp.read().decode("utf-8"))
            return 0
    except Exception as e:
        _die(f"unreachable: {e}")
        return 1


def cmd_trending(args: argparse.Namespace) -> int:
    res = _api("GET", "/api/simulation/trending")
    if args.json:
        _print_json(res)
        return 0
    if not res.get("success"):
        _die(res.get("error", "trending failed"))
    for it in (res["data"].get("items") or [])[:10]:
        print(f"- {it.get('title', '')[:80]}  [{it.get('source', '?')}]")
        print(f"  {it.get('url', '')}")
    return 0


# ─── Entry point ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="miroshark",
        description="Thin CLI for a running MiroShark backend. "
                    "Set MIROSHARK_API_URL to override the default http://localhost:5001.",
    )
    p.add_argument("--json", action="store_true", help="Print raw JSON (for scripting).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ask = sub.add_parser("ask", help="Research a question → seed briefing.")
    p_ask.add_argument("question", help="Natural-language question.")
    p_ask.set_defaults(func=cmd_ask)

    p_list = sub.add_parser("list", help="List simulations / projects.")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="Show simulation run status.")
    p_status.add_argument("simulation_id")
    p_status.set_defaults(func=cmd_status)

    p_frame = sub.add_parser("frame", help="Compact snapshot for one round.")
    p_frame.add_argument("simulation_id")
    p_frame.add_argument("round", type=int)
    p_frame.add_argument("--platforms", help="comma-separated: twitter,reddit,polymarket")
    p_frame.set_defaults(func=cmd_frame)

    p_pub = sub.add_parser("publish", help="Toggle public embed for a simulation.")
    p_pub.add_argument("simulation_id")
    p_pub.add_argument("--unpublish", action="store_true", help="Unpublish instead.")
    p_pub.set_defaults(func=cmd_publish)

    p_report = sub.add_parser("report", help="Show rendered analytical report.")
    p_report.add_argument("simulation_id")
    p_report.set_defaults(func=cmd_report)

    p_trend = sub.add_parser("trending", help="Pull trending topics from RSS feeds.")
    p_trend.set_defaults(func=cmd_trending)

    p_health = sub.add_parser("health", help="Ping the backend /health endpoint.")
    p_health.set_defaults(func=cmd_health)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
