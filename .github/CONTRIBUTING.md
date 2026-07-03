# Contributing to MiroShark

<sup>English · [中文](CONTRIBUTING.zh-CN.md)</sup>

Thanks for helping make swarm simulation cheaper and more credible. This guide
covers local setup, the test suite, and how to land a PR.

## Ways to contribute

- **A bug fix or feature** in the Flask backend (`backend/`) or the Next.js
  frontend (`frontend/`).
- **A new API endpoint** — see the checklist below; the OpenAPI spec and a drift
  test keep code and docs in lockstep.
- **Docs and translations** — the README and this file have `*.zh-CN.md` /
  `*.ja.md` / `*.fr.md` counterparts; keep them in sync.

## Before you start

- **Branch from `main`** with a typed prefix: `feat/…`, `fix/…`, `docs/…`,
  `test/…`, or `chore/…`.
- **One change per PR.** Don't bundle unrelated edits.
- **Title as a [Conventional Commit](https://www.conventionalcommits.org/)** —
  `feat: …`, `fix: …`, `docs: …`; add a scope when it sharpens intent
  (`feat(api): …`). PRs are squash-merged, so the title becomes the commit subject.

## Development setup

**Prerequisites:** Node.js ≥ 18, [uv](https://docs.astral.sh/uv/) for the Python
backend, and Docker (for Neo4j).

1. Install frontend and backend dependencies in one step (`npm install`, the
   `frontend/` deps, then `cd backend && uv sync`):

   ```bash
   npm run setup:all
   ```

2. Create your environment file and fill in at least one LLM key:

   ```bash
   cp .env.example .env
   ```

   Defaults target OpenRouter — paste a key into the `*_API_KEY` slots, or switch
   to a fully local Ollama setup using the "Alternatives" block in `.env.example`.
   Every variable is documented in [docs/CONFIGURATION.md](../docs/CONFIGURATION.md).

3. Start Neo4j (`NEO4J_PASSWORD` must be set in `.env` first):

   ```bash
   docker compose up -d neo4j
   ```

4. Run the backend (`:5001`) and frontend (`:3000`) together (`predev` frees the
   ports if a stale process holds them):

   ```bash
   npm run dev
   ```

## Testing & CI

A pytest suite lives at `backend/tests/`.

```bash
cd backend && pytest -m "not integration"      # fast offline unit suite
pytest -m integration                           # endpoint contracts (needs a live backend)
pytest -m "integration and slow"                # full pipeline smoke tests (minutes)
```

Integration tests hit a live backend at `MIROSHARK_API_URL` (default
`http://localhost:5001`); some need a pre-existing simulation via
`MIROSHARK_TEST_SIM_ID=sim_xxx`. The `.github/workflows/tests.yml` workflow runs
the unit suite (`pytest -m "not integration"`) on every push and PR to `main`, so
**a green local unit run is the quickest path to a green PR.**

### Adding an API endpoint

The backend's HTTP surface is documented in `backend/openapi.yaml`, and a drift
test (`backend/tests/test_unit_openapi.py`) **fails CI if the spec and the real
Flask routes disagree.** To add an endpoint:

1. **Register the route** on the right blueprint in `backend/app/api/`. A brand-new
   blueprint must be registered in `backend/app/__init__.py` and given a prefix
   entry in the drift test's `_BLUEPRINT_PREFIXES` map.
2. **Document the path** in `backend/openapi.yaml` under `paths:`, using a
   top-level-declared tag. Internal/debug routes go on the test's
   `_UNDOCUMENTED_ALLOWLIST` instead.
3. **Add an offline unit test** at `backend/tests/test_unit_<feature>.py` (no live
   Flask, no Neo4j) — mirror an existing `test_unit_*.py`.

A documented endpoint shows up for free in the Swagger UI at `/api/docs`.

## Submitting a pull request

- Keep the diff focused and the title conventional; it becomes the squash commit.
- Explain **what** changed and **why**; link the issue (`Fixes #123`).
- **Run the fast unit suite before pushing** — CI runs the same one.
- **Keep translations in sync.** If you touch a doc with a `*.zh-CN.md` / `*.ja.md`
  / `*.fr.md` counterpart, update it too — or note in the PR that it still needs
  translating.

## Reporting bugs & requesting features

Open an issue with repro steps, what you expected, what happened, and your
environment (OS, Node/Python versions, deployment target).

**Found a security problem?** Don't open an issue — follow
[`SECURITY.md`](SECURITY.md) and report it privately.

## License

By contributing, you agree that your contributions are licensed under the
repository's [LICENSE](LICENSE).
