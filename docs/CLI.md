# CLI

<sup>English · [中文](CLI.zh-CN.md)</sup>

A dependency-light HTTP client for a running MiroShark backend.

## Install

```bash
# From a checkout with the backend installed:
pip install -e backend/
miroshark-cli ask "Will the EU AI Act survive trilogue?"

# Or run directly — no install, no third-party deps:
python backend/cli.py --help
```

Set `MIROSHARK_API_URL` to point at a remote deployment.

## Commands

| Command | What it does |
|---|---|
| `ask "<question>"` | Synthesize a seed briefing from a question |
| `list` | List simulations / projects |
| `status <sim_id>` | Runner status + round/total |
| `frame <sim_id> <round>` | Compact per-round snapshot |
| `publish <sim_id> [--unpublish]` | Toggle the embed public flag |
| `report <sim_id>` | Render the analytical report |
| `trending` | Pull RSS/Atom trending items |
| `health` | Ping `/health` |

All commands accept `--json` for scripting.
