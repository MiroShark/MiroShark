# Security Policy

MiroShark spawns hundreds of agents over a Neo4j knowledge graph built from
whatever you drop in — a press release, a policy draft, unpublished research,
private documents. That graph, the OpenRouter keys that drive the swarm, and
any self-hosted deployment are all worth protecting. This document is how to
report a problem privately and what to expect back.

## Supported versions

MiroShark ships from `main`; there is no long-term-support branch yet. Security
fixes land on `main` and in the next tagged release.

| Version | Supported          |
| ------- | ------------------ |
| `0.1.x` (current) | :white_check_mark: |
| `< 0.1.0` (pre-release) | :x: |

If you are running a fork or a pinned older commit, confirm the fix is present
on `main` before assuming you're covered.

## Reporting a vulnerability

**Please do not open a public issue, pull request, or discussion for a
suspected vulnerability.** Public disclosure before a fix exists puts every
operator running MiroShark at risk — including production deployments.

Report privately through **GitHub's private vulnerability reporting**:

1. Go to the [Security tab](https://github.com/aaronjmars/MiroShark/security)
   of this repository.
2. Click **"Report a vulnerability"** to open a private advisory visible only
   to you and the maintainers.
3. Fill in the details below.

This keeps the report, the discussion, and the eventual fix coordinated in one
private place, and lets us credit you in the published advisory.

### What to include

A good report lets us reproduce the issue fast:

- **Component** — frontend, backend API, the simulation engine, the `./miroshark`
  launcher, Docker/compose config, or a deployment recipe (Railway / Render /
  Cloud Run).
- **Description** — what the weakness is and the impact (data exposure, RCE,
  auth bypass, SSRF, prompt-injection-to-tool-call, credential leak, etc.).
- **Reproduction** — minimal steps, a proof-of-concept request, and the
  affected version or commit SHA.
- **Environment** — local vs. hosted, Neo4j local vs. Aura, and which LLM
  provider/router you pointed it at.

## Response expectations

We aim to:

| Stage | Target |
| ----- | ------ |
| Acknowledge your report | within **3 business days** |
| Initial assessment + severity | within **7 days** |
| Fix or mitigation for confirmed high/critical issues | as fast as is safe; you'll get progress updates |

If you don't hear back within the acknowledgement window, please bump the
private advisory thread — it means the notification was missed, not ignored.

## Disclosure

We follow **coordinated disclosure**:

- We'll work with you on a fix and agree on a disclosure date.
- Once a fix is released, we publish a GitHub Security Advisory and credit the
  reporter (unless you ask to stay anonymous).
- We ask that you hold public details until the advisory is live so operators
  have time to upgrade.

This policy exists because it has already mattered. A hardcoded default Neo4j
password in the quickstart was found and reported in
[#88](https://github.com/aaronjmars/MiroShark/issues/88) and has since been
fixed — but that report came in over a public issue because no private channel
existed yet. This file is that channel.

## Operator hardening checklist

Most real-world risk in a self-hosted swarm engine comes from deployment, not
the code. Before exposing MiroShark to the internet:

- **Never expose Neo4j ports (7474 / 7687) publicly.** Keep the database on a
  private network; only expose the MiroShark frontend/API. The graph holds
  whatever documents you fed your simulations.
- **Set a strong `NEO4J_PASSWORD`.** Don't ship the example/default value.
- **Treat LLM/router keys as secrets.** Keep `LLM_API_KEY` / `SMART_API_KEY`
  and any OpenRouter key in `.env` or your platform's secret store, never in
  committed files or logs.
- **Treat every simulation input as untrusted.** Agents act on the documents,
  headlines, and chat you drop in — don't paste secrets you wouldn't want a
  model (or a tool the model can call) to see.
- **Lock down admin-token-gated endpoints** (webhook retry, delivery log, and
  other operator surfaces) behind a non-default admin token.

## Scope

In scope: the code in this repository (frontend, backend, engine, launcher,
Docker/deploy configs) and the documented APIs.

Out of scope: third-party services MiroShark talks to (OpenRouter and other LLM
providers, Neo4j Aura, hosting platforms) — report those to the respective
vendors. Findings that require a pre-compromised host, a malicious dependency
you installed yourself, or social engineering of a maintainer are also out of
scope.

Thanks for helping keep MiroShark and its operators safe.
