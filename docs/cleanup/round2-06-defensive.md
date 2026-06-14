# Round 2 — Task 06: Defensive code / try-except cleanup

Agent: code-quality 06 (defensive). Mode: **auto-apply high-confidence only,
defer everything risky.** This is the highest-risk task in the sweep; the bar
for "high confidence" is set deliberately very high. When in doubt → DEFER.

## Methodology

1. Enumerated every `except` in the tree by area (AST/grep over `.py`):
   - `backend/app/` (production): **750** handlers
   - `backend/scripts/`: 133
   - `backend/lib/`: 1
   - `backend/wonderwall/` (VENDORED — treated read-only): 105
   - `backend/tests/`: 23
2. Focused on the error-*hiding* subset — `except ...: pass` and broad
   `except Exception:` that swallow silently. Production `backend/app/` had
   ~75 `except ...: pass` occurrences.
3. Read each candidate in context and classified it as **external-input guard
   (keep)** vs **no-purpose / over-broad silent swallow (fix)**.
4. Frontend: enumerated empty `catch (_) {}` in `frontend/src`.
5. Preferred remedy = **NARROW + log** (surface the error), never delete a
   guard around fallible I/O and never introduce a new silent fallback.

## Categorization

### external-input guard — KEEP (the overwhelming majority)

Confirmed legitimate and left untouched. Representative sample:

| file:line | what it guards |
|---|---|
| `services/telegram_notify.py:388` | parsing Telegram's HTTP error body (network + JSON) |
| `services/surface_stats.py:184` / `share_link_service.py:218` | tempfile cleanup on atomic-write failure (file I/O; share_link re-raises) |
| `services/oracle_seed.py:114` | `client.close()` on a network/RPC client |
| `services/reranker / storage/reranker_service.py:60` | optional `import torch` + `cuda.is_available()` (graceful degradation) |
| `utils/file_parser.py:41,50` | optional `charset_normalizer` / `chardet` imports |
| `utils/claude_code_client.py:173` | observability `emit` around an LLM call ("must never break LLM calls") |
| `utils/event_logger.py` (all) | logging/IPC best-effort; "never break the simulation for a logging failure" |
| `utils/url_fetcher.py`, `utils/i18n.py` | network DNS, request-arg parsing of external HTTP input |
| `api/observability.py:228,285,343` | reading persisted `events.jsonl` (file I/O + JSON of stored data) |
| `api/simulation.py:2524,2636,2902,8980,9590,…` | reading persisted `state.json`/project DB; graceful gallery/preview degradation |
| frontend `i18n.js`, `ComparisonView.vue`, `EmbedDialog.vue` | `localStorage` (throws in private mode/quota), `document.execCommand`, network `await` |

These all guard genuinely fallible I/O / network / LLM / DB / optional-import /
parsing-of-stored-or-external data. **Per the brief, all retained.**

### no-purpose / over-broad silent swallow — FIX

Exactly one cluster cleared the high-confidence bar: `_build_gallery_card_payload`
in `backend/app/api/simulation.py`. This single function reads five on-disk
artifacts and is **internally inconsistent**: one read (`quality.json`,
line 7886) already uses the codebase's preferred posture —
`except (OSError, json.JSONDecodeError) as e: logger.debug(...)` — while three
sibling reads in the *same function* silently `except Exception: pass`. The
fix makes the three siblings match the in-function exemplar so a corrupt
artifact surfaces in debug logs instead of vanishing.

This is not a removal of a guard (the reads are file I/O of stored data and a
handler is warranted); it is a **narrow + add log** so errors stop being hidden.
Control flow is unchanged — every guarded variable already defaults to a safe
value (`scenario=""`, `total_rounds=0`, `final_consensus=None`,
`resolution_outcome=None`) before the `try`.

## Findings — ranked

| rank | file:line | issue | action |
|---|---|---|---|
| HIGH | `api/simulation.py:7855` | `except Exception: pass` around `simulation_config.json` read+parse, inconsistent with sibling at :7886 | NARROW+log — APPLIED |
| HIGH | `api/simulation.py:7918` | `except Exception: pass` around `trajectory.json` read + belief-position arithmetic | NARROW+log — APPLIED |
| HIGH | `api/simulation.py:7928` | `except Exception: pass` around `resolution.json` read+parse | NARROW+log — APPLIED |
| LOW | `utils/i18n.py:60,66,72` | broad `except Exception: pass` around `request.args.get`/`headers.get`, which don't realistically raise on a real Flask request | DEFER (truly best-effort locale; narrowing surfaces nothing; risk a non-Flask/mock request object elsewhere) |
| LOW | `api/observability.py:228,285,343` | broad outer `except Exception: pass` around `events.jsonl` reads | DEFER (guards file I/O of stored data; already narrows inner JSON parse; consistent across all three) |

## APPLIED

`backend/app/api/simulation.py` — `_build_gallery_card_payload`, 3 handlers:

- **:7855** `simulation_config.json`: `except Exception: pass` →
  `except (OSError, ValueError, TypeError, json.JSONDecodeError) as e: logger.debug(...)`.
  Wrapped code is `open()` + `json.load()` + int coercion of stored config; the
  enumerated set covers every realistic failure. Not external-network/LLM input —
  it is a *local stored artifact*, and a corrupt one was being hidden.
- **:7918** `trajectory.json`: added `ZeroDivisionError` to the set (the block
  divides by `len(p)`/`total`), plus the file/parse exceptions, + debug log.
- **:7928** `resolution.json`: `except (OSError, json.JSONDecodeError) as e:
  logger.debug(...)` — byte-for-byte the same posture as the function's own
  `quality.json` reader at :7886.

Reasoning these are *not* a real external-input guard worth a silent swallow:
they read **first-party artifacts our own pipeline wrote**, in a cheap
read-only gallery-card builder. A failure means our serializer produced a
malformed file — a bug we want in the logs, not silenced. The narrowed sets
still let the function degrade gracefully (vars pre-defaulted), so behaviour for
the legitimate "missing/old artifact" case is unchanged.

## DEFERRED (and why)

- **`utils/i18n.py:60/66/72`** — `request.args.get` / `request.headers.get`
  don't raise on a genuine Flask request, so the guard is arguably purposeless,
  BUT it is pure best-effort locale resolution that already falls back to
  `DEFAULT`, and callers may pass mock/non-standard request objects in tests.
  Narrowing surfaces nothing of value and the deletion risk isn't worth it.
- **`api/observability.py` outer handlers** — guard file I/O of persisted JSONL;
  inner `json.JSONDecodeError` already handled per-line; the three are mutually
  consistent. Legitimate file-I/O guard → keep.
- **All `scripts/` and `wonderwall/` swallowers** — out of the high-confidence
  zone; `wonderwall/` is vendored (conservative). Not touched.
- **Everything in the KEEP table** — genuine external/I/O/LLM/DB/optional-import
  guards.

## Verification

- `ruff check backend/app/api/simulation.py` → **All checks passed!** (no new errors)
- `python3 -c "ast.parse(...)"` → syntax OK
- `git diff --stat` → 1 file, 6 insertions / 6 deletions (3 handlers narrowed)
- No control-flow change; no new silent fallback introduced; all changes
  *increase* error visibility (added `logger.debug`).
