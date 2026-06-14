# Round 2 — Task 01: Deduplicate & consolidate (DRY)

Fresh audit of duplication across `backend/`, `frontend/`, with `backend/wonderwall/`
in scope. Builds on round 1 (`docs/cleanup/01-dry.md`), which applied two surgical
helper extractions (`_build_badge_document`, `_build_event`) and deferred the rest as
either intentional or semantically divergent. This round re-verified the deferrals from
scratch and found **one large, genuinely-safe consolidation round 1 missed**: the
byte-identical `_safe_load_json` artifact reader duplicated across 11 service modules.

## Methodology

- `grep`/`rg` for module-level function names defined in ≥3 files
  (`grep -rhno "^def …" | sort | uniq -c`), then read every body to separate
  *byte-identical* duplication from *coincidentally-named-but-divergent* helpers.
- For each consolidation candidate: grep-verified zero external references
  (imports, `__all__`, tests, monkeypatch, frontend, SQL, dynamic refs) before touching it.
- Static-only verification (no venv): `ruff check` each changed file, `python3 -m
  py_compile`, plus a standalone functional-equivalence harness for the extracted helper
  against the original semantics (missing path / empty path / valid / corrupt / directory).

## Headline finding — `_safe_load_json` (APPLIED)

`_safe_load_json(path)` was defined **11 times** across the read-only "project a sim's
on-disk artifacts into an API response/export" services, with a **byte-identical body**
(only docstrings varied):

```python
if not path or not os.path.exists(path):
    return None
try:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
except Exception:
    return None
```

Locations: `trajectory_export.py:62`, `thread_formatter.py:59`, `transcript.py:84`,
`agent_export.py:119`, `project_stats.py:110`, `activity_feed.py:115`,
`platform_status.py:89`, `platform_stats.py:96`, `outcome_distribution.py:112`,
`agent_sparklines_service.py:72`, `batch_status.py:116`.

- Zero external references / tests / monkeypatches (`grep -rn _safe_load_json
  backend/tests backend/scripts frontend` → empty). All 11 are private, local-only.
- Signature varied only cosmetically (`-> Any` vs `-> Optional[Any]`, which are the same
  type). Bodies identical down to the bytes.

**Applied:** extracted to `backend/app/utils/json_io.py::safe_load_json` and replaced each
local definition with `from ..utils.json_io import safe_load_json as _safe_load_json`. Every
call site stays `_safe_load_json(path)` — byte-identical call shape, no behaviour change.
Removed the now-orphaned `import json` (5 files) / `typing.Any` (1 file) the helper was the
sole user of, and one orphaned `# ── On-disk readers ──` section divider whose only member
was removed. **Net: −192 / +17 across 11 files + a 39-line shared module.**

This is the textbook DRY win: 11 identical I/O primitives → one. It *reduces* complexity
(a future hardening of the read path — e.g. narrowing `except Exception`, adding a size
guard — now happens once) without adding any indirection, since the call sites are unchanged.

## Findings table

| # | Candidate | Files | Confidence | Disposition |
|---|-----------|-------|-----------|-------------|
| 1 | `_safe_load_json` byte-identical artifact reader | 11 services | **HIGH** | **APPLIED** — `utils/json_io.safe_load_json` |
| 2 | ISO-8601 UTC "now" helper (`_iso_utc_now`/`_utc_iso8601`/`_now_iso`), body identical | 7 services | MED (safe but cross-file) | **DEFERRED** — see below |
| 3 | `_resolve_base_url()` byte-identical (feed/sitemap + share's `_resolve_oembed_base_url`) | 3 api | MED | **DEFERRED** — watch.py/webhook variants deliberately differ |
| 4 | `_avg_position` belief-mean | 4 services | LOW | **DEFERRED** — `transcript.py` counts `True` as 1.0; others exclude bool |
| 5 | `_safe_str` / `_safe_int` coercers | 6 / 4 services | LOW | **DEFERRED** — divergent (`max(0,…)` clamp, `default` params, `isinstance` shortcut) |
| 6 | `_format_pct` | 5 services | LOW | **DEFERRED** — two distinct algos; 3 are in the notify cluster |
| 7 | `_sha256_hex` | 4 services | LOW | **DEFERRED** — half prefix `"sha256:"`, half don't |
| 8 | `_cache_header` | 4 api | LOW | **DEFERRED** — each returns a *different* `max-age` constant |
| 9 | `replay_gif.py` ↔ `share_card.py` font/text helpers | 2 services | LOW | **DEFERRED** — `_FONT_CANDIDATES` differ; visual-regression risk |
| 10 | Notify-channel cluster (`_truncate`/`belief_bar`/`_status_verb`/`BAR_*`) | 4 services | — | **DEFERRED (intentional)** — documented decoupling, do not merge |
| 11 | Vue view CSS/`<script>` helpers (`addLog`/`toggleMaximize`/`formatTime`) | 5+ .vue | — | **DEFERRED** — frontend-agent territory, behaviour-affecting, can't compile-verify |

## DEFERRED — detail

**2. ISO-8601 UTC timestamp helper.** Body is byte-identical in all 7 sites
(`return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`) under three names
(`_iso_utc_now` ×3, `_utc_iso8601` ×3, `_now_iso` ×1). The docstrings already
cross-reference each other ("same shape every other export surface uses"). This is a
*genuinely safe* consolidation — but it spans 7 export-service files that round 1 flagged
as high conflict-risk (the slop/types/legacy agents are likely editing them), and it
requires renaming call sites + removing defs in each, which is more churn than the value of
collapsing a one-line function. Deferred to a single-owner follow-up to avoid merge
collisions in this parallel-agent round. Home would be `utils/json_io.py` (rename module) or
a small `utils/timefmt.py`.

**3. `_resolve_base_url()`.** Three byte-identical bodies (`api/feed.py:46`,
`api/sitemap.py:46`, and `api/share.py:298` as `_resolve_oembed_base_url`) prefer
`Config.PUBLIC_BASE_URL` then fall back to proxy-aware request host. Safe to share. But the
sibling variants are *deliberately* different: `api/watch.py:204` has **no**
`PUBLIC_BASE_URL` preference (request-only), and `webhook_service.py:921` is **config-only**
(no request context — fires from a background thread). Round 1 deferred this for the same
reason (needs a new web-helpers module, only 3 clean callers). Low complexity-reduction vs.
the risk of someone later assuming all five share one helper. Left for the `api/`-layout owner.

**4. `_avg_position`.** Confirmed round 1's finding: `transcript.py:66` filters
`isinstance(v, (int, float))` and therefore **counts `True` as `1.0`**, whereas
`thread_formatter.py`/`trajectory_export.py` exclude `bool`, and
`agent_sparklines_service.py` additionally guards `isinstance(positions, dict)`. Merging
would change `transcript.py` output for any snapshot with a boolean position. Requires a
deliberate bool-semantics decision first — out of scope for a behaviour-preserving pass.

**5–9.** Each verified individually as semantically divergent (`_safe_int`'s `max(0,…)`
clamp; `_sha256_hex`'s `"sha256:"` prefix; `_format_pct`'s integer-when-clean vs `.1f`;
`_cache_header`'s per-endpoint TTL; the font candidate lists). Consolidating any of these
would change behaviour at some call site. Not done.

**10–11.** Intentional / out-of-scope per round 1 and the cleanup safety rules.

## APPLIED — summary

- **New:** `backend/app/utils/json_io.py` — `safe_load_json(path) -> Optional[Any]`.
- **Edited (11):** `trajectory_export.py`, `thread_formatter.py`, `transcript.py`,
  `agent_export.py`, `project_stats.py`, `activity_feed.py`, `platform_status.py`,
  `platform_stats.py`, `outcome_distribution.py`, `agent_sparklines_service.py`,
  `batch_status.py` — each now imports the shared helper under the local name
  `_safe_load_json`; orphaned `import json`/`typing.Any`/section divider cleaned up.

## Verification

- `ruff check` on all 12 changed files + the new module: **All checks passed!** (no new errors).
- `python3 -m py_compile` on all 12: OK.
- Functional-equivalence harness on `safe_load_json`: missing path → `None`, empty/`None`
  path → `None`, valid JSON → parsed dict, corrupt JSON → `None`, directory path → `None`.
  Byte-identical to the 11 originals.

## Conflict-risk notes for the integrator

- The 11 edited service files are read-only API/export modules. The types/weak-types and
  slop agents may also touch them (annotations, comments). The diff here is confined to
  the import block + removal of one function each, so a 3-way merge should be clean, but
  watch `outcome_distribution.py` / `platform_stats.py` / `activity_feed.py` (also flagged
  by round 1).
- `backend/app/utils/json_io.py` is new — no collision unless another agent also creates a
  json/io util; none observed.
