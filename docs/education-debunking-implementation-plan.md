# Education & Debunking System — Implementation Plan

**Date:** 2026-05-02  
**Source PRD:** `docs/PRD-education-debunking-system.md`  
**Current pilot session:** `b41b4775-891d-49b9-a5c6-a7f9c4d64493`  
**Goal:** Convert the current gas-tax infographic/research prototype into a reusable education/debunking system that can unpack shallow media talking points on any topic.

## North-star outcome

A user can paste a topic, claim, article, transcript, or clip context and get:

1. a structured claim map,
2. evidence and source ledger,
3. normalized context like per-capita / real-dollar / share-of-budget views,
4. a system map of causes, incentives, beneficiaries, costs, and history,
5. public-friendly infographics, narration, and video-response storyboards.

## Key sequencing decision

Build this as a layered refactor, not as a separate product rewrite. Preserve the existing working session and pipeline while extracting universal primitives:

1. stable slide identity,
2. fact/source ledger,
3. normalization engine,
4. universal claim schema,
5. response-video planner.

---

## Phase 0 — Stabilise the current infographic workflow

### Task 0.1 — Add stable slide IDs and dependency metadata

**Why:** We already hit the problem where inserting a slide invalidates later render/audio indexes. The product cannot evolve if every plan edit destroys generated media.

**Files:**
- `backend/app/services/infographic_planner.py`
- `backend/tests/test_infographic_planner.py`
- `frontend/src/views/DecisionTreeView.vue`

**Implementation:**
- Add to every slide:
  - `slide_id`: deterministic stable string, e.g. `money.extra_sources`, `money.tax_per_person`, `spending.period.howard_1996_2007`
  - `depends_on`: list of upstream slide IDs or fact IDs
  - `sequence_index`: generated at plan time for display only
- Keep `slide_type` for backward compatibility.
- Change render/audio maps to support both:
  - old: `{ "9": render }`
  - new: `{ "money.tax_per_person": render }`
- Add migration helper when loading old sessions.

**Acceptance:**
- Insert a new slide before index 10 and previously rendered slides with unchanged `slide_id` still display correctly.
- Tests prove slide IDs remain stable across plan regeneration.

### Task 0.2 — Add “render next 5” batch UI

**Why:** Rendering one slide at a time is too manual; rendering all at once is too risky/costly.

**Files:**
- `frontend/src/views/DecisionTreeView.vue`
- `frontend/src/api/seedChat.js`
- `backend/app/api/seed_chat.py` if batch endpoint is needed
- `backend/tests/test_seed_chat_api.py`

**Implementation:**
- Button: `Render next 5 unrendered`.
- Select next unrendered slide IDs, not indexes.
- Respect `OPENAI_IMAGE_DAILY_LIMIT`.
- Stop with a clear message if any render fails.

**Acceptance:**
- With 46-slide plan and 9 rendered slides, button targets slides 10-14.
- UI shows progress `1/5`, `2/5`, etc.
- Budget errors are shown as JSON/UI state, not HTML 500.

### Task 0.3 — Make infographics-first route explicit

**Status:** Partially done. Current reload auto-opens infographics when a session has a plan.

**Files:**
- `frontend/src/router/index.js`
- `frontend/src/views/DecisionTreeView.vue`

**Implementation:**
- Add route alias or query convention:
  - `/decision-tree/:sessionId?infographics=1`
  - optional later: `/infographics/:sessionId`
- Opening/closing modal should update query state.
- Reload should restore selected slide if `slide_id` or `slide` query is present.

**Acceptance:**
- Reload opens directly to infographics modal.
- Link can open directly to `tax_per_person` slide.

---

## Phase 1 — Normalization engine

### Task 1.1 — Create normalization service

**Why:** The product’s debunking value often comes from asking “compared to what?” Raw totals are usually misleading.

**New file:**
- `backend/app/services/normalization_engine.py`

**Tests:**
- `backend/tests/test_normalization_engine.py`

**Core API:**

```python
def per_capita(total: float, population: float) -> float: ...
def growth_rate(start: float, end: float) -> float: ...
def ratio(start: float, end: float) -> float: ...
def share_of_total(part: float, total: float) -> float: ...
def inflation_adjust(value: float, cpi_start: float, cpi_end: float) -> float: ...
def build_normalized_comparison(label, start, end, denominators, cpi=None) -> dict: ...
```

**Initial supported transforms:**
- nominal total
- per capita
- population growth
- share of budget
- share of GDP placeholder field
- inflation-adjusted once CPI table is added

**Acceptance:**
- Given taxation receipts `$217.866b`, population `21.0172m`, returns about `$10.4k/person`.
- Given taxation receipts `$657.844b`, population `27.614411m`, returns about `$23.8k/person`.
- Tests cover rounding and invalid denominator handling.

### Task 1.2 — Move gas-tax budget/population facts into data module

**Why:** Current constants live inside `infographic_planner.py`. Universal system needs reusable fact packs.

**New file:**
- `backend/app/services/fact_packs/australia_budget.py`

**Move data:**
- 2006-07 receipts
- 2024-25 receipts
- 2025-26 estimated spending
- population 2007/2025
- debt milestones
- source URLs and source types

**Acceptance:**
- `infographic_planner.py` imports fact packs instead of owning all raw constants.
- Each fact has `source_url`, `source_name`, `source_type`, `reference_period`.

### Task 1.3 — Add normalization slide archetypes

**Files:**
- `backend/app/services/infographic_planner.py`
- `backend/tests/test_infographic_planner.py`

**Slide types:**
- `population_adjusted_view`
- `tax_per_person`
- `real_dollar_view` once CPI is available
- `share_of_budget_view`
- `what_changed_vs_what_did_not`

**Acceptance:**
- Current pilot includes:
  - raw spending change,
  - where extra money comes from,
  - tax per resident,
  - at least one “what this does / does not prove” caution slide.

---

## Phase 2 — Source and fact ledger

### Task 2.1 — Define fact ledger schema

**New file:**
- `backend/app/services/fact_ledger.py`

**Fact object:**

```json
{
  "fact_id": "budget.receipts.taxation.2006_07",
  "text": "Taxation receipts were $217.866b in 2006-07",
  "value": 217.866,
  "unit": "AUD_billion",
  "period": "2006-07",
  "source_name": "Final Budget Outcome 2006-07",
  "source_url": "https://archive.budget.gov.au/2006-07/fbo/FBO_2006-07.pdf",
  "source_type": "official",
  "confidence": "high",
  "used_by_slide_ids": []
}
```

**Acceptance:**
- Every deterministic fact in the infographic plan can be represented as a fact ledger item.
- Facts can be linked to slides through `fact_ids`.

### Task 2.2 — Add slide fact/source drawer

**Files:**
- `frontend/src/views/DecisionTreeView.vue`

**Implementation:**
- In infographic modal, add “Facts & sources” panel.
- Show each fact text, source, period, confidence, source type.
- Flag facts without a source.

**Acceptance:**
- User can click a slide and see which official/source facts power it.
- Current budget/population slides show source URLs.

---

## Phase 3 — Universal claim schema

### Task 3.1 — Add claim model service

**New file:**
- `backend/app/services/claim_model.py`

**Schema fields:**
- `claim_id`
- `surface_claim`
- `implied_claims`
- `claim_type`
- `emotional_hook`
- `known_true_parts`
- `misleading_parts`
- `missing_context`
- `normalizations_needed`
- `evidence_requirements`
- `verdict`
- `confidence`
- `sources`

**Acceptance:**
- Can represent “Government spending exploded” as a structured claim with required normalizations.
- Can represent “A 25% gas tax will scare investors away” with causal/prediction fields.

### Task 3.2 — Upgrade seed extraction to collect talking points

**Files:**
- `backend/app/services/seed_extractor.py`
- `backend/tests/test_seed_extractor.py`
- `frontend/src/components/SeedSlotsPanel.vue`

**Implementation:**
- Add slot category: `talking_points` / `claims_to_unpack`.
- Prompt Claude to distinguish topic from claims.
- Preserve current `contested_claims` for compatibility, but map into claim objects.

**Acceptance:**
- User can start with “I saw someone say government spending exploded” and the session stores it as a claim object, not just topic text.

### Task 3.3 — Claim decomposition endpoint

**Files:**
- `backend/app/api/seed_chat.py`
- `backend/app/services/claim_decomposer.py`
- `backend/tests/test_seed_chat_api.py`

**Endpoint:**
- `POST /api/seed-chat/claims/decompose`

**Acceptance:**
- Given a claim, returns implied claims, missing context, normalizations needed, and evidence requirements.
- Stores decomposed claims in session.

---

## Phase 4 — Education planner refactor

### Task 4.1 — Extract generic education planner

**New file:**
- `backend/app/services/education_planner.py`

**Why:** `infographic_planner.py` is currently gas-tax-specific. We need a generic layer that can plan lesson beats from claim objects and evidence.

**Inputs:**
- topic
- claim objects
- system tree
- fact ledger
- audience level
- output format

**Outputs:**
- generic `LessonPlan`
- `LessonBeat` objects that can later become slides, narration, videos, docs

**Acceptance:**
- Existing gas-tax plan can be generated through education planner + topic-specific fact pack.
- Non-gas sample topic test can generate a plausible generic lesson plan without gas-specific slides.

### Task 4.2 — Keep infographic planner as renderer-specific adapter

**Implementation:**
- `education_planner.py` decides lesson structure.
- `infographic_planner.py` turns lesson beats into image prompts and slide objects.

**Acceptance:**
- Tests prove no gas-tax-specific labels appear for an unrelated topic unless supplied by facts/claims.

---

## Phase 5 — Split-screen response video planner

### Task 5.1 — Create response video planner service

**New file:**
- `backend/app/services/response_video_planner.py`

**Input schema:**

```json
{
  "source_kind": "transcript | user_clip | url",
  "source_title": "",
  "segments": [
    {"start": 12.4, "end": 18.2, "transcript": "Government spending has exploded"}
  ],
  "claims": [],
  "tone": "calm_educator | satirical | serious | youth_tiktok",
  "target_duration_seconds": 60
}
```

**Output schema:**

```json
{
  "format": "split_screen_vertical",
  "beats": [
    {
      "time_range": [0, 5],
      "top": {"kind": "source_excerpt", "segment_id": "..."},
      "bottom": {"kind": "educational_slide", "slide_id": "..."},
      "voiceover": "He is right that spending dollars rose, but that is only the first layer...",
      "captions": []
    }
  ],
  "rights_note": "Use short excerpts/commentary or transcript cards unless rights are confirmed."
}
```

**Acceptance:**
- Given a transcript segment and existing tax-per-person slide, produces a split-screen storyboard that references that slide.
- Does not require downloading/reposting copyrighted content.

### Task 5.2 — Add frontend response-video draft UI

**Files:**
- `frontend/src/views/DecisionTreeView.vue` or new component `ResponseVideoModal.vue`
- `frontend/src/api/seedChat.js`

**Implementation:**
- Textarea for transcript/claim.
- Optional timestamp fields.
- Generate storyboard button.
- Show split-screen beats as cards.

**Acceptance:**
- User can paste a TikTok quote and get a draft response-video structure using existing education slides.

---

## Phase 6 — Verification and universal-topic test set

### Task 6.1 — Add five-topic smoke fixtures

**Tests:**
- `backend/tests/test_education_planner.py`

**Topics:**
- gas/resource tax
- housing affordability
- migration/population pressure
- electricity prices / renewables
- health spending / Medicare

**Acceptance:**
- Each topic produces a claim map and education plan without hard-coded gas-tax leakage.

### Task 6.2 — End-to-end manual checklist

**Checklist:**
1. Start from a raw talking point.
2. Decompose claims.
3. Generate research/evidence.
4. Generate education plan.
5. Inspect fact ledger.
6. Render 1-3 slides.
7. Generate narration.
8. Draft response-video storyboard.

---

## Recommended immediate next task

Start with **Task 0.1 — stable slide IDs and dependency metadata**.

Reason: it removes the most painful friction in the current workflow and makes every later PRD task safer. Normalization and response-video work will keep inserting/reordering slides, so stable IDs must come first.
