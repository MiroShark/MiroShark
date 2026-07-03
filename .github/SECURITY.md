# Security Policy

MiroShark is a self-hosted app: a Flask backend and a Next.js frontend that drive
a swarm of LLM agents over a Neo4j graph, using your own model-provider keys. It
ingests untrusted input (the scenario you seed, injected "breaking news", feeds)
and can expose public **share** / **watch** pages, so this policy spells out what's
in scope and how to report a problem privately.

## Reporting a vulnerability

**Please don't open a public issue for a security problem.** Use GitHub's
**Private Vulnerability Reporting (PVR)** instead:

➡️ **[Report a vulnerability](https://github.com/aaronjmars/MiroShark/security/advisories/new)**

(Repo → **Security** tab → **Report a vulnerability**.) This opens a private
advisory that only the maintainers can see — never a public issue, so a fix can
ship before the details are out.

Please include what you can:

- The route or component affected — a `backend/app/api/` blueprint (`/api/graph`,
  `/api/simulation`, `/api/mcp`, `/share`, `/watch`…), a frontend view, or a
  deployment file.
- A minimal reproduction or proof of concept.
- The impact you can demonstrate — API-key/credential disclosure, unauthorized
  mutation of a simulation, prompt injection that makes an agent act on embedded
  instructions, SSRF, or data leakage across the internal/public boundary.
- The commit and deployment target you tested against (local Docker, Railway,
  Cloud Run, Render…).

**Response targets** — best effort; this is a small project:

| Stage | Target |
|-------|--------|
| Acknowledge the report | within 7 days |
| Initial assessment / severity | within 14 days |
| Fix or mitigation on `main` | as fast as the severity warrants |

We follow **coordinated disclosure**: please give us a reasonable window to ship
a fix before you disclose publicly. We'll credit you in the advisory unless you'd
rather stay anonymous.

## Supported versions

MiroShark is deployed from source. Security fixes land on the `main` branch of
[`aaronjmars/MiroShark`](https://github.com/aaronjmars/MiroShark); pull `main` to
receive them.

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ Yes |
| Your deployment behind `main` | ⚠️ Pull latest to receive fixes |
| Older commits / images | ❌ No |

## Security model

- **Secrets live in `.env` / your platform's secret store, never in code.**
  Model-provider keys (`*_API_KEY`), the Neo4j password, and admin credentials are
  read from the environment. Don't commit a filled-in `.env`; `docker-compose` and
  the Railway/Cloud Run/Render configs expect them injected.
- **Mutation endpoints are admin-gated.** State-changing `/api/*` routes are meant
  to sit behind the admin auth documented in `.env.example`. When you expose the
  backend publicly, set those credentials — an unauthenticated internet-facing
  backend can be driven to run expensive simulations against your keys.
- **Public pages are read-only by design.** `/share`, `/watch`, `/sitemap`, and the
  syndication feeds are the only surfaces intended to be reachable without auth.
  Anything that reads private simulation data through them is a bug worth reporting.
- **Agent input is untrusted.** Scenarios, injected news, and fetched sources are
  **data, not instructions.** Content that steers an agent via embedded prompts
  ("ignore previous instructions…") crossing into tool calls or key exfiltration is
  in scope. Outbound fetches that can be pointed at internal addresses (SSRF) are
  too.

## Scope

**In scope:**

- Disclosure or exfiltration of API keys, the Neo4j password, or admin credentials.
- Unauthorized access to mutation endpoints, or state change without admin auth.
- Private simulation data leaking through `/share`, `/watch`, feeds, or the API.
- Prompt injection that crosses the data→instruction boundary (untrusted content
  driving tool use, exfiltration, or unbounded spend).
- SSRF, path traversal, or injection in the backend or its integrations.

**Out of scope:**

- Misconfiguration of your own deployment (backend exposed with no admin auth, a
  public Neo4j, secrets committed by hand).
- Vulnerabilities in Neo4j, the LLM/embedding providers, OpenRouter, or the
  hosting platform — report those to the respective vendor.
- Simulation output quality (an agent producing a wrong or biased answer is a
  behavior issue, not a vulnerability — open a regular issue).

---

> **Maintainers:** the Report-a-vulnerability link only works once PVR is enabled
> — **Settings → Code security and analysis → Private vulnerability reporting →
> Enable**.

Thanks for helping keep MiroShark and the people who run it safe.
