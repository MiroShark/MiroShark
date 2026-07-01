# Known issues

This page records issues found during a repo health check on 2026-07-01.
The checkout was updated to `origin/main` at commit `2895fb0`
(`chore(config): switch default model lineup (#223)`).

The goal of this document is to make the current problems easy to
understand before someone starts fixing them.

## Summary

| Priority | Area | Issue | Current impact |
| --- | --- | --- | --- |
| High | Frontend dependencies | `npm audit` reports a high-severity `form-data` advisory through `axios` | Dependency security scanners will fail or warn until the lockfile resolves a fixed package |
| Medium | Backend tests on Windows | `test_unit_feed_filters.py` has a path-separator assumption | The feed filter test fails on Windows even though the same logic is likely fine on Linux CI |
| Medium | Backend app startup in tests | Internal-auth tests try to initialize Neo4j through `create_app()` | Tests hang or run very slowly when Neo4j is not running locally |
| Low | Frontend build | Vite reports an ineffective dynamic import | The app still builds, but the intended code split is not happening |
| Low | Secret hygiene | Real keys must never be pasted into example env files | No committed live key was found, but `.env.example` is easy to edit by mistake |

## 1. Frontend dependency audit reports a high-severity advisory

**Command run**

```bash
cd frontend
npm ci
npm audit --json
```

**Observed result**

`npm ci` completed, but the audit reported one high-severity issue:

- Package: `form-data`
- Advisory: `GHSA-hmw2-7cc7-3qxx`
- Problem: CRLF injection through unescaped multipart field names or filenames
- Fixed range: `form-data >= 4.0.6`
- Dependency path: `axios@1.18.1 -> form-data@4.0.5`

`npm ls form-data` showed:

```text
frontend@0.1.0
+-- axios@1.18.1
    +-- form-data@4.0.5
```

**Why it matters**

Security scanners will keep flagging the frontend dependency tree while
the lockfile resolves `form-data@4.0.5`.

**Suggested fix**

Run `npm audit fix` in `frontend/`, or update the frontend lockfile so
the resolved `form-data` version is at least `4.0.6`. After updating,
rerun:

```bash
cd frontend
npm ci
npm audit
npm run build
```

## 2. Feed filter test fails on Windows because it assumes `/` paths

**Command run**

```bash
cd backend
uv run pytest tests/test_unit_feed_filters.py -q
```

**Observed result**

The file ran 17 tests. Sixteen passed and one failed:

```text
FAILED tests/test_unit_feed_filters.py::test_trending_sort_uses_surface_stats_reader
assert ['sim_c', 'sim_b', 'sim_a'] == ['sim_b', 'sim_a', 'sim_c']
```

**Likely cause**

The fake `surface_stats_reader` in `backend/tests/test_unit_feed_filters.py`
extracts the simulation id with:

```python
sim_id = sim_dir.rsplit("/", 1)[-1]
```

That works on Linux paths such as `tmp/sim_b`, but not on Windows paths
such as `tmp\sim_b`. On Windows, the lookup misses the fake serve counts,
all cards get a count of `0`, and the code falls back to date order.

**Why it matters**

This makes a backend test look broken on Windows even though the
production route passes a real directory to `surface_stats.read_surface_stats`.
It is a test portability issue.

**Suggested fix**

Change the test helper to use a platform-safe path API:

```python
from pathlib import Path

sim_id = Path(sim_dir).name
```

Then rerun the focused test file on Windows and Linux.

## 3. Internal-auth tests hang when Neo4j is not running

**Commands run**

```bash
cd backend
uv run pytest tests/test_unit_internal_auth.py -q
uv run pytest tests/test_unit_internal_auth.py::test_health_endpoint_without_auth -vv -s
```

**Observed result**

The focused auth test did not finish promptly. It repeatedly logged Neo4j
connection failures:

```text
Schema query failed (attempt 1): Couldn't connect to localhost:7687
```

The full unit command also stalled after reaching `test_unit_internal_auth.py`,
and had to be stopped locally.

**Likely cause**

`backend/app/__init__.py` initializes `Neo4jStorage()` inside `create_app()`.
That constructor calls `_ensure_schema()`, which attempts to connect to
Neo4j. The auth tests only need Flask request-guard behavior, but app
creation still tries to touch the graph database.

**Why it matters**

Tests that should be fast and offline become dependent on a local Neo4j
server. On a developer machine without Neo4j running, the suite can look
hung even before it reaches the route being tested.

**Suggested fix**

Make the app factory support a test mode that skips Neo4j startup, or
allow tests to inject a fake storage object. The important rule is:
tests for `/health` and internal auth should not need a live graph
database.

After changing this, rerun:

```bash
cd backend
uv run pytest tests/test_unit_internal_auth.py -q
uv run pytest -m "not integration"
```

## 4. Frontend build passes but Vite reports an ineffective dynamic import

**Command run**

```bash
cd frontend
npm run build
```

**Observed result**

The production build completed. Vite still warned:

```text
[INEFFECTIVE_DYNAMIC_IMPORT] src/store/pendingUpload.js is dynamically imported by src/views/Home.vue but also statically imported by src/components/TemplateGallery.vue, src/views/Home.vue, src/views/MainView.vue
```

**Why it matters**

This is not a correctness failure. It means the dynamic import cannot
split `pendingUpload.js` into a separate chunk because other files import
it statically.

**Suggested fix**

Pick one import style for `src/store/pendingUpload.js`. If lazy loading is
wanted, remove the static imports. If lazy loading is not useful here,
replace the dynamic import with a normal static import.

## 5. Secret hygiene note for env examples

**Command run**

```bash
rg -n "sk-or-v1|OPENAI_API_KEY=.*[A-Za-z0-9_-]{20,}|LLM_API_KEY=.*[A-Za-z0-9_-]{20,}|API_KEY=.*[A-Za-z0-9_-]{20,}" .
```

**Observed result**

The tracked repository only showed placeholders such as
`sk-or-v1-YOUR_KEY` and `your-llm-api-key-here`.

**Why it matters**

`.env.example` is tracked by git and should only contain placeholders.
Real secrets belong in `.env`, which is ignored locally.

**Suggested fix**

Keep `.env.example` placeholder-only. If a real key is ever pasted into a
tracked example file, remove it before committing and rotate the key.

## Checks that passed

The frontend production build passed:

```bash
cd frontend
npm run build
```

No committed live OpenRouter key was found in the tracked repository
during the simple text scan described above.
