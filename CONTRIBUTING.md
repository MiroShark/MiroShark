# Contributing

<sup>English · [中文](CONTRIBUTING.zh-CN.md)</sup>

Thanks for helping make swarm simulation cheaper and more credible. This guide covers local setup, the test suite, and how to land a PR.

## Development setup

**Prerequisites:** Node.js ≥ 18, [uv](https://docs.astral.sh/uv/) for the Python backend, and Docker (for Neo4j).

1. Install both the frontend and backend dependencies in one step:

   ```bash
   npm run setup:all
   ```

   This runs `npm install`, installs the `frontend/` deps, then `cd backend && uv sync`.

2. Create your environment file and fill in at least one LLM key:

   ```bash
   cp .env.example .env
   ```

   Defaults target OpenRouter — paste a key into the `*_API_KEY` slots, or switch to a fully local Ollama setup using the "Alternatives" block in `.env.example`. Every variable is documented in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

3. Start Neo4j (the graph store behind the memory pipeline). `NEO4J_PASSWORD` must be set in `.env` first:

   ```bash
   docker compose up -d neo4j
   ```

4. Run the backend (`:5001`) and frontend (`:3000`) together:

   ```bash
   npm run dev
   ```

   `predev` first frees ports 3000 and 5001 if a stale process is holding them.

## Testing

A pytest suite lives at `backend/tests/`.

### Fast offline unit suite

```bash
cd backend && pytest -m "not integration"
```

### Integration tests

Integration tests hit a live backend at `MIROSHARK_API_URL` (default `http://localhost:5001`). Legacy E2E scripts wrap as `slow` tests:

```bash
pytest -m integration                # endpoint contracts (seconds)
pytest -m "integration and slow"     # full pipeline smoke tests (minutes)
```

Some integration tests need a pre-existing simulation — set `MIROSHARK_TEST_SIM_ID=sim_xxx`.

The hand-run scripts in `backend/scripts/test_*.py` still work as stand-alone programs; the pytest layer just registers them for discovery.

### CI

The `.github/workflows/tests.yml` workflow runs the unit suite (`pytest -m "not integration"`) on every push and PR to `main`.

## Submitting a PR

- **Branch off `main`** with a typed prefix: `feat/…`, `fix/…`, `docs/…`, `test/…`, or `chore/…`.
- **Title the PR as a [Conventional Commit](https://www.conventionalcommits.org/)** — the same prefixes the merged history uses, e.g. `feat: …`, `fix: …`, `docs: …`. Add a scope when it sharpens intent: `feat(api): …`.
- **Keep it focused.** One change per PR — don't bundle unrelated edits.
- **Run the fast unit suite before pushing** (`cd backend && pytest -m "not integration"`); CI runs the same suite, so a green local run is the quickest way to a green PR.
- **Keep translations in sync.** If you touch a doc that has a `*.zh-CN.md` / `*.ja.md` counterpart (README, this file), update it too — or note in the PR that it still needs translating.

## Adding an API endpoint

The backend's HTTP surface is documented in `backend/openapi.yaml`, and a drift test (`backend/tests/test_unit_openapi.py`) **fails CI if the spec and the real Flask routes disagree** — so the spec and the code stay in lockstep. To add an endpoint:

1. **Register the route** on the right blueprint in `backend/app/api/` (e.g. `@simulation_bp.route('/<simulation_id>/your-surface')`). A brand-new blueprint must be registered in `backend/app/__init__.py` and given a prefix entry in the drift test's `_BLUEPRINT_PREFIXES` map.
2. **Document the path** in `backend/openapi.yaml` under `paths:`, using a tag that is also declared at the top level. Internal/debug routes belong on the test's `_UNDOCUMENTED_ALLOWLIST` instead.
3. **Add a unit test** at `backend/tests/test_unit_<feature>.py`. Keep it offline (no live Flask app, no Neo4j) so it runs in the bare CI environment — mirror an existing `test_unit_*.py` file.

A documented endpoint shows up for free in the Swagger UI at `/api/docs` and the JSON spec at `/api/openapi.json`, both served from the same `openapi.yaml`.
