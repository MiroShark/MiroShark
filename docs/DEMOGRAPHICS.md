# Demographic Grounding

MiroShark personas are normally graph-grounded: each agent is the LLM's
interpretation of an entity that came out of the knowledge-graph build
(an alumni group, a journalist, an exchange, a regulator…). That makes
them *narratively* grounded — the agent's worldview comes from real
relationships in the graph — but it doesn't constrain their demographic
shape.

Demographic grounding is an optional layer that pulls a real census-like
row from an NVIDIA **Nemotron-Personas** parquet dataset for each
entity and feeds it to the persona generator as an anchor. The LLM still
writes the persona; the seed just tells it the agent is, say, a 34-year-old
female teacher in Tampines with a bachelor's degree and an income in the
S$60–80k bracket. The graph context and web enrichment still drive the
agent's *worldview* — the seed only pins down the demographic baseline.

The feature is purely additive:
- when `DEMOGRAPHICS_COUNTRY` is empty, nothing changes
- when the country code is unknown, the sampler logs a warning and skips
- when `duckdb` / `huggingface_hub` aren't installed, the sampler skips
- when only N seeds are reachable for M entities (M > N), the first N
  agents get seeds and the rest fall back to graph-only generation

## Enable it

```bash
# .env
DEMOGRAPHICS_COUNTRY=sg     # or "us"
```

Then `pip install -r backend/requirements.txt` to pull `duckdb` and
`huggingface_hub`. On the first simulation run, the sampler will download
the Nemotron parquet for the selected country into
`backend/data/nemotron/<country>/` (~hundreds of MB) and cache it for
subsequent runs.

## Country packs

Country configs live in `backend/app/countries/*.json` — one file per
country, registered automatically. Each pack declares:

| field            | meaning                                              |
| ---------------- | ---------------------------------------------------- |
| `code`           | short code used by env / API (`sg`, `us`, …)         |
| `name`           | display name                                         |
| `flag_emoji`     | for the country picker UI                            |
| `dataset.repo_id`| HuggingFace dataset id                               |
| `dataset.local_paths` | parquet globs checked before downloading        |
| `dataset.download_dir` | where the HF snapshot lands                    |
| `geography.field` | column used to bucket personas (e.g. `planning_area`, `state`) |
| `geography.values`| valid values for that column                        |
| `geography.groups`| named multi-region presets (e.g. `north-east`)      |
| `filter_fields`  | UI hints for the cohort selector                     |
| `max_agents` / `default_agents` | agent-count caps                       |

To add a new country, drop a new JSON file in `backend/app/countries/`
alongside the existing two. The registry picks it up on the next process
start. No code changes required.

## API

- `GET /api/countries` — list of installed packs (public-safe summary)
- `GET /api/countries/<code>` — full filter schema for one pack (geography
  values, groups, filter fields, agent caps)

The active country (if any) is reported as `active_country` on the list
endpoint so the SPA can preselect it.

## How the seed reaches the LLM

`WonderwallProfileGenerator.generate_profiles_from_entities()` calls
`demographic_sampler.sample_seeds()` once per simulation, pairs the
returned rows with entities, and passes one row per entity into
`_build_individual_persona_prompt` / `_build_group_persona_prompt` as a
new `DEMOGRAPHIC ANCHOR` / `AUDIENCE ANCHOR` block in the prompt.

For individual entities, the seed is treated as the agent's own
demographic. For organizational entities, the seed is treated as a
typical follower in the target audience — used to localize voice and
tone, not to redefine the institution.

After the LLM responds, any unset fields (`age`, `gender`, `profession`,
`country`) fall back to the seed's values so the agent stays internally
consistent.

## Composability with existing layers

The seed is the fourth layer in the existing persona stack:

1. Graph attributes (Neo4j entity attrs)
2. Graph relationships (BFS-expanded neighborhood)
3. Web enrichment (LLM web research for thin personas)
4. **Demographic seed (new)** — Nemotron row, country-scoped

Each layer is independently optional. Disabling graph search or web
enrichment doesn't disable demographic grounding, and vice versa.

## Limitations

- Sampling is deterministic for a given `(country, seed)` pair, so two
  runs of the same scenario with the same country produce the same
  demographic mix. Vary `demographic_filters.seed` to reshuffle.
- The Nemotron schema isn't uniform across country splits; the sampler
  tolerates missing columns by skipping those filters silently.
- Pairing is positional (entity i ↔ seed i after a deterministic
  shuffle). It doesn't try to match entity type to demographic — e.g. an
  "exchange" entity may be paired with a teacher seed. The prompt's
  framing (`DEMOGRAPHIC ANCHOR` vs `AUDIENCE ANCHOR`) handles this for
  group entities; for individuals the LLM is asked to reconcile.
