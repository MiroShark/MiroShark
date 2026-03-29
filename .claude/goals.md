# Project Goals

## Vision
MiroShark as a simulation-guided decision intelligence platform — upload any situation, define decision branches, simulate parallel futures through AI agent swarms, and see consequence trees that reveal unintended outcomes and causal chains.

## Active Goals

### G1: Get MiroShark running locally
_Status: Complete | Added: 2026-03-25_
Clone, configure, and run the full MiroShark stack (Flask backend + Vue frontend + Neo4j + Ollama) on the local workstation with RTX PRO 6000.

Sub-goals:
- [x] G1.1: Clone repo and set up project structure
- [x] G1.2: Start infrastructure (Neo4j via Docker, Ollama with models)
- [x] G1.3: Install all dependencies (npm + uv)
- [x] G1.4: Configure .env for local setup
- [x] G1.5: Resolve port conflict (frontend→3001, backend→5002)
- [x] G1.6: Verify full stack starts and serves UI

### G2: Harden the base platform
_Status: Complete | Added: 2026-03-25_
Fix critical reliability and security issues before building on top.

Sub-goals:
- [x] G2.1: Add URL input support (docs + links)
- [x] G2.2: Fix axios baseURL / CORS lockdown
- [x] G2.3: Add LLM retry logic to llm_client.py (commit c7bf020, F3)
- [x] G2.4: Make ontology generation async (commit 02c47ce, F8)
- [x] G2.5: Add real health checks (commit 409d0b4, F4)

### G3: Build Decision Lab — Foundation
_Status: Complete | Added: 2026-03-27_
Create the Decision Lab page with scenario setup, multi-branch definition, and parallel simulation execution.

Sub-goals:
- [x] G3.1: Backend — Decision Lab API blueprint + data model (lab_id, branches, decision_text)
- [x] G3.2: Backend — Branch config generator (inject decision text into simulation config)
- [x] G3.3: Backend — Parallel branch runner (orchestrate 2-3 concurrent simulations)
- [x] G3.4: Frontend — Decision Lab page with scenario builder + branch definition UI
- [x] G3.5: Frontend — Branch monitoring dashboard (parallel progress tracking)

### G4: Build Decision Lab — Consequence Engine
_Status: Complete | Added: 2026-03-27_
Extract causal consequence trees from simulation results and build comparison/injection UI.

Sub-goals:
- [x] G4.1: Backend — Consequence extractor service (3-stage: event graph → LLM scoring → tree construction)
- [x] G4.2: Backend — Branch comparison metrics (posts, comments, engagement, net sentiment, top posters)
- [x] G4.3: Frontend — Consequence tree visualization (D3.js horizontal collapsible tree)
- [x] G4.4: Frontend — Side-by-side branch comparison dashboard
- [x] G4.5: Backend + Frontend — "What-if" injection (add new info, re-run from injection point)

### G5: Autonomous Strategy Optimizer
_Status: Complete | Added: 2026-03-27_
Autoresearch-inspired loop that autonomously proposes, tests, and refines decision strategies.

Sub-goals:
- [x] G5.1: Backend — autonomous_lab.py service (propose → simulate → evaluate → iterate loop)
- [x] G5.2: Backend — /auto/start, /auto/status, /auto/stop API endpoints
- [x] G5.3: Frontend — Goal input, iteration config, live progress with KEEP/DISCARD verdicts

## Completed Goals

## Goal Log
<!-- Append-only log of goal evolution. Newest at top. -->
<!-- Format: {date} | {action} | {details} -->
2026-03-27 | completed | G4: Decision Lab — Consequence Engine (all 5 sub-goals)
2026-03-27 | completed | G3: Decision Lab — Foundation (all 5 sub-goals)
2026-03-27 | added | G4: Decision Lab — Consequence Engine
2026-03-27 | added | G3: Decision Lab — Foundation
2026-03-27 | restructured | G2: renamed from "Explore codebase" to "Harden base platform" — exploration done via audit
2026-03-25 | added | G2: Explore and understand the codebase
2026-03-25 | added | G1: Get MiroShark running locally
2026-03-25 | added | Vision defined
