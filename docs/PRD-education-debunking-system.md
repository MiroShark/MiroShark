# Education & Debunking System PRD

**Date:** 2026-05-02  
**Status:** Draft v0.1 — replaces the narrower Seed Chat framing as the product north star  
**Current exemplar use case:** Australian gas/resource tax, spending, debt, and media talking points

## 1. Product thesis

Public debates are dominated by short, emotionally charged talking points. Those talking points often contain a partial truth, but hide the bigger system: history, incentives, budget trade-offs, who benefits, who pays, what evidence exists, and what remains uncertain.

This product turns any contested public claim into a clear, evidence-grounded education sequence: chat intake → claim map → research → system map → simple infographics/audio/video → shareable rebuttal/explainer artifacts.

The goal is not to produce partisan propaganda. The goal is to make simplistic claims harder to hide behind by giving audiences a deeper, easier-to-understand model of the whole system.

## 2. Target user

- A citizen trying to understand a policy/media debate without reading 50 sources.
- A creator who wants to respond to viral simplistic claims with substance.
- An educator/journalist/advocate who wants neutral, cited, visual explainers.
- A small team building public-information content without a newsroom budget.

## 3. Core jobs to be done

1. **Decode a talking point.**  
   “I saw claim X. Is it true, misleading, missing context, or just a slogan?”

2. **Teach the system behind the claim.**  
   “Explain the bigger picture simply: history, money flows, stakeholders, incentives, trade-offs.”

3. **Create public-friendly artifacts.**  
   “Turn the analysis into slides, narration, short videos, citations, and counterpoints.”

4. **Respond to viral media.**  
   “Take a clip/transcript of someone making a claim and produce a split-screen educational response that pauses/quotes the claim, explains context, and shows supporting visuals.”

## 4. Product principles

- **Nuance over dunking.** Always separate true, false, misleading, disputed, and unknown.
- **System understanding before rebuttal.** A claim response should teach the underlying machinery, not only say “wrong”.
- **Simple visuals, deep backing.** The public artifact is easy; the internal research trail is deep.
- **Citations and uncertainty are first-class.** Every factual slide needs sourceable facts and confidence labels.
- **Universal topic model.** Gas tax is just the pilot. The same pipeline should work for housing, migration, energy, health, AI, defence, climate, debt, crime, etc.
- **Transformative media use.** For response videos, use transcripts/short excerpts/user-provided clips and add commentary, critique, context, and original educational material. Avoid building a “rip and repost” tool.

## 5. Universal pipeline

### Stage A — Intake

Input can be:
- free-form user topic
- pasted article/social post/transcript
- uploaded/user-provided video clip
- URL/source set
- existing session continuation

The system extracts:
- topic
- user intent
- audience level
- contested claims
- stakeholders
- source/clip metadata
- desired output format
- tone boundaries

### Stage B — Claim decomposition

For each talking point:
- exact claim
- implied claim
- emotional hook
- missing context
- factual dependencies
- stakeholder interests
- likely counterclaims
- required historical/system background

Example from current use case:
- Surface claim: “Government spending exploded.”
- Better decomposition:
  - spending dollars rose sharply
  - percentages by category may not change as much
  - population rose
  - inflation/wages rose
  - tax receipts per person rose
  - deficits/debt fill the remaining gap
  - the useful question is not “spending big?” but “who pays, who benefits, and is the system sustainable?”

### Stage C — Research and evidence ledger

For each claim and subclaim:
- retrieve sources
- extract relevant numbers/quotes
- classify source type: official, academic, industry, advocacy, media, social
- score confidence/contestedness/salience
- record what would change the conclusion

### Stage D — System map

Build a concept/causal map:
- upstream causes
- downstream effects
- beneficiaries and harmed groups
- historical precedents
- incentives
- money flows
- legal/institutional constraints
- disputed assumptions

### Stage E — Education plan

Generate a structured lesson sequence:
- hook: what claim are we unpacking?
- basic facts
- timeline/history
- system model
- claim-by-claim debunk/context
- opposing steelman
- what is true / misleading / unknown
- conclusion or “how to think about it”

### Stage F — Artifact generation

Artifacts:
- briefing document
- claim verdict cards
- educational infographic slides
- narration beats
- audio clips
- short-form video storyboard
- split-screen response plan
- citations package
- downloadable JSON/Markdown

## 6. Current feature inventory

Already built or partially built:
- seed chat/session persistence
- media-landscape brief writer
- web research via SearXNG/DDG fallback
- per-claim research
- decision/system tree
- node synthesis/scoring
- foresight compiler
- infographic planner
- OpenAI/Nano Banana image renderers
- local Piper audio renderer
- story timeline modal/player
- render accounting

## 7. Gap analysis from current gas-tax pilot

### What we learned

- The important product is no longer just “research a topic”; it is “educate against shallow media claims.”
- Users need the bigger system, not isolated pros/cons.
- Per-capita and baseline normalization matter. Raw totals can mislead.
- The slide plan must support “why this changed” and “what changed after adjusting for population/inflation.”
- The artifact should be modular enough to respond to a specific viral clip.

### Gaps

1. **Universal claim schema is too weak.**  
   Need explicit fields for implied claims, missing context, normalizations, and common misleading frames.

2. **Normalization layer missing.**  
   Need standard transforms: per capita, real dollars, share of GDP, share of budget, per household, per worker, marginal/effective tax rates.

3. **Source ledger not visible enough.**  
   Need a UI showing which facts power each slide and whether they are official/advocacy/media.

4. **Video-response workflow not modeled.**  
   Need clip/transcript intake, segment selection, response beats, split-screen timing, and rights/safety constraints.

5. **Regeneration invalidates renders/audio.**  
   Need stable slide IDs and dependency tracking so inserting a slide does not wipe everything after it.

## 8. Proposed system architecture additions

### 8.1 Universal Claim Object

```json
{
  "claim_id": "stable id",
  "surface_claim": "Government spending has exploded",
  "implied_claims": [
    "Government is wasting money",
    "People are being taxed more to fund it"
  ],
  "claim_type": "causal | numeric | moral | prediction | attribution | comparison",
  "emotional_hook": "anger about waste/tax burden",
  "known_true_parts": [],
  "misleading_parts": [],
  "missing_context": [],
  "normalizations_needed": ["per_capita", "real_dollars", "share_of_gdp"],
  "evidence_requirements": [],
  "verdict": "true | mostly_true | misleading | disputed | false | unknown"
}
```

### 8.2 Normalization Engine

Reusable transforms:
- nominal total
- inflation-adjusted total
- per capita
- per household
- per worker/taxpayer
- share of GDP
- share of budget
- effective rate vs headline rate
- before/after policy change

This is critical for the “are people being taxed more?” question.

### 8.3 Education Slide Types

Reusable slide archetypes:
- Talking point card
- What is true / missing / misleading
- Population-adjusted view
- Inflation-adjusted view
- Per-person burden
- Money-flow diagram
- Timeline/history
- Who benefits / who pays
- Steelman both sides
- Evidence confidence matrix
- “How to think about it” conclusion

### 8.4 Split-screen Response Video Workflow

Inputs:
- user-provided clip or transcript
- start/end timestamps selected by user
- claim transcript
- target duration
- tone: calm educator, satirical, serious, youth/TikTok, etc.

Output:
- top half: original clip excerpt or transcript-highlight card
- bottom half: generated educational slide sequence
- generated voiceover or captions
- source/citation overlay
- “claim → context → evidence → bigger picture” structure

Important guardrail:
- The system should prioritize commentary/critique/education and avoid encouraging wholesale reuse of copyrighted videos. Default to short excerpts, transcript-based references, source attribution, and user-confirmed rights/permission where needed.

## 9. MVP v2 scope

### Must have

- Universal claim schema
- Normalization engine with per-capita and inflation-ready facts
- Slide plan with stable slide IDs
- Source ledger per slide
- “Open directly to infographics” route/state
- Regenerate plan without losing valid renders where slide IDs match

### Should have

- Clip/transcript intake for response videos
- Split-screen storyboard JSON
- Export timeline to an editing format
- Batch “render next 5” button
- Fact/source review panel before rendering

### Later

- Automatic video assembly with FFmpeg
- Speech-to-text from uploaded clips
- Face/voice-safe parody modes
- Multi-topic public library
- Community fact-check review

## 10. Success metrics

- User can input a viral claim and get a cited explanation in under 5 minutes.
- User can understand the bigger system without reading the full research file.
- Every slide has traceable facts and confidence labels.
- Generated content reduces oversimplification, not just creates counter-propaganda.
- Same pipeline works across at least 5 unrelated policy topics.

## 11. Near-term implementation plan

1. Add normalization facts and slide types to the gas-tax pilot: per capita, real dollars, share of GDP/budget.
2. Introduce stable `slide_id` and `depends_on` fields so inserted slides do not break existing renders.
3. Add a source/fact drawer for each slide.
4. Create a `response_video_planner.py` that takes a clip transcript and maps claims to educational counter-slides.
5. Add frontend route/query state for infographics-first review.
6. Convert this PRD into tracked implementation tasks after the current infographic flow stabilizes.
