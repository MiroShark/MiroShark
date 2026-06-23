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
| `cost <sim_id>` | Estimated USD cost + token/call totals (the "$1" claim, per run) |
| `trending` | Pull RSS/Atom trending items |
| `health` | Ping `/health` |

All commands accept `--json` for scripting.

## Cost

`cost <sim_id>` surfaces the per-run cost estimate (the `/api/simulation/<id>/cost.json`
endpoint) at the command line, so the "$1 to simulate anything" claim is verifiable
from a script:

```bash
$ python backend/cli.py cost sim_abc123
~$0.9213  (1,284,902 tokens, 871 LLM calls)
  graph_build      ~$0.1204
  simulation       ~$0.7100
  report           ~$0.0909
```

The `~` prefix marks the figure as a lower-bound estimate — calls on models absent
from the price table count as `$0`. The simulation must be published (`publish <sim_id>`).
Exit codes: `0` on success, `1` on private/server error, `2` when cost is not yet
available (the run has logged no LLM calls). Add `--json` for the full breakdown.
