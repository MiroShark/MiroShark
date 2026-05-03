# Education Pipeline Question Methodology

**Date:** 2026-05-02  
**Purpose:** Capture the questioning pattern that emerged from the gas-tax pilot so the system can apply the same method to any contested topic.

## Core insight

The product should not just research a topic. It should interrogate the *shape of the public claim* until it can teach the whole system behind that claim.

The user's questions in this session followed a repeatable escalation pattern:

1. Start with a public talking point.
2. Ask what the raw numbers show.
3. Ask what the normalized numbers show.
4. Ask where the money/power/incentives flow.
5. Ask why the obvious conclusion may not follow.
6. Ask what the system-level constraints are.
7. Turn the answer into simple public education artifacts.

That becomes the universal methodology below.

---

## Universal question sequence

### 1. What is the surface claim?

Ask:
- What exactly is being claimed?
- Who is saying it?
- What emotion is it trying to trigger: anger, fear, envy, distrust, urgency?
- Is it a number claim, causal claim, moral claim, prediction, or blame claim?

Gas-tax pilot examples:
- “Government spending has exploded.”
- “People are being taxed more.”
- “They collect more every year but do not pay down debt.”

Output:
- one-sentence claim
- implied claim
- emotional hook
- claim type

---

### 2. What is true in the claim?

Ask:
- What part is factually true?
- What source confirms it?
- What is the simplest number or event that supports it?
- What would a fair opponent concede?

Gas-tax pilot:
- Spending in dollars rose sharply.
- Tax collected per resident rose in nominal terms.
- Debt remains high despite higher revenue.

Output:
- “true part” card
- official-source facts
- confidence rating

---

### 3. What context is missing?

Ask:
- Compared with what baseline?
- Over what time period?
- Has population changed?
- Has inflation changed dollar values?
- Have wages, profits, asset prices, or GDP changed?
- Is the percentage share different, or only the raw dollar total?

Gas-tax pilot:
- Spending dollars rose, but category percentages changed less dramatically.
- Population rose.
- Tax per resident rose.
- Need percentage-burden comparisons, not only dollar totals.

Output:
- missing-context list
- normalization requirements

---

### 4. What normalization views are needed?

For every numeric claim, ask which transforms are required:

- nominal dollars
- real/inflation-adjusted dollars
- per capita
- per household
- per worker/taxpayer
- share of GDP
- share of total budget
- share of income/wages
- effective rate vs headline rate
- before/after policy change

Gas-tax pilot:
- total receipts
- tax per resident
- population growth
- spending by budget share
- future need: tax-to-income and tax-to-GDP

Output:
- normalization plan
- normalized comparison slides

---

### 5. Where is the extra money coming from?

Ask:
- Which revenue streams grew?
- Did growth come from explicit new taxes or automatic mechanisms?
- Is it income tax, company tax, GST, excise, royalties, resource taxes, debt, or asset sales?
- Is the base larger because there are more people, higher wages, higher prices, higher profits, or higher rates?

Gas-tax pilot:
- more receipts from workers' income tax
- company tax
- GST
- super taxes
- debt/deficit when spending exceeds receipts

Output:
- money-source flow diagram
- ranked revenue sources

---

### 6. Why can the burden rise without an obvious new tax?

Ask:
- Are tax brackets indexed to inflation?
- Does wage growth create bracket creep?
- Are prices higher, lifting GST/excise dollar amounts?
- Are company profits higher?
- Are compliance measures collecting more?
- Are governments choosing not to return bracket creep through tax cuts?

Gas-tax pilot:
- inflation
- wage growth
- bracket creep
- service-cost pressure
- debt repair

Output:
- “hidden mechanisms” slide
- what is policy choice vs automatic drift

---

### 7. Where is the money going?

Ask:
- Which spending categories absorb the money?
- Are they discretionary or structurally hard to cut?
- What programs are growing and why?
- Who benefits?
- What are the legitimate reasons for higher spending?
- What are the waste/fraud/inefficiency risks?

Gas-tax pilot:
- welfare
- health
- NDIS
- aged care
- state GST support
- defence
- debt interest

Output:
- spending bucket slide
- benefits vs pressures
- who benefits / who pays

---

### 8. If revenue is rising, why is the problem not solved?

Ask:
- Is revenue larger than spending?
- Are there annual deficits or only small surpluses?
- Is debt stock too large for short surpluses to erase?
- Is interest consuming part of revenue?
- Are new promises absorbing the extra money?
- What would paying down debt require politically?

Gas-tax pilot:
- higher revenue did not automatically pay debt down
- service costs and interest absorbed money
- sustained surpluses are politically hard
- debt reduction means taxes up, services down, slower benefit growth, or asset sales

Output:
- “why not paid down?” slide
- constraint map

---

### 9. Who has incentives to frame the story this way?

Ask:
- Who benefits from the talking point?
- Who funds the message?
- What does each side omit?
- What are the strongest good-faith arguments on each side?
- What would each side prefer the audience not ask?

Gas-tax pilot:
- industry warnings about investment
- pro-tax claims about public return
- government incentives around budget repair
- voters react to simple tax/spending frames

Output:
- stakeholder/incentive map
- steelman both sides
- omitted-context cards

---

### 10. What historical timeline explains the current state?

Ask:
- When did the system start changing?
- Which governments or institutions were responsible at each stage?
- What shocks happened?
- Which changes were choices vs inherited conditions?
- Which claims blame one actor for a multi-period trend?

Gas-tax pilot:
- Howard/Costello low debt baseline
- GFC
- Rudd/Gillard deficits
- Abbott/Turnbull/Morrison pre-COVID debt growth
- COVID jump
- Albanese/Chalmers surpluses but high inherited debt

Output:
- timeline cards
- “who was in power?” card
- shocks vs choices split

---

### 11. What would a fair conclusion say?

Ask:
- What is solid?
- What is misleading?
- What is still uncertain?
- What would a sensible compromise or next question be?
- What should citizens ask politicians or media figures for?

Gas-tax pilot:
- ask for percentage burden, not just raw totals
- ask whether increased revenue is funding services, interest, or new promises
- ask what exact debt-reduction trade-off is proposed
- ask for effective tax rates, not headline rates

Output:
- conclusion slide
- citizen checklist
- “questions to ask next” card

---

## Research agent prompt pattern

For any topic, the research agent should use this checklist:

```text
You are building an educational debunking package, not just a report.

For each public claim:
1. State the exact surface claim.
2. Identify implied claims and emotional hook.
3. Find what is true.
4. Find what is missing or misleading.
5. Identify required normalizations.
6. Find baseline and current numbers.
7. Explain where money/power/risk flows.
8. Explain why the obvious conclusion may not follow.
9. Map stakeholders and incentives.
10. Build a historical timeline.
11. Produce simple lesson beats with cited facts.

Prefer official, primary, or high-quality sources for numbers.
Separate:
- facts
- interpretations
- disputed claims
- political incentives
- unknowns

Never stop at a raw total. Ask: per capita, real dollars, percentage of income/GDP/budget, and effective vs headline rate.
```

---

## Data model additions

### ClaimAnalysis

```json
{
  "claim_id": "stable id",
  "surface_claim": "",
  "implied_claims": [],
  "emotional_hook": "",
  "claim_type": "numeric | causal | moral | blame | prediction | comparison",
  "true_parts": [],
  "missing_context": [],
  "misleading_parts": [],
  "normalizations_needed": [],
  "stakeholders": [],
  "evidence_requirements": [],
  "verdict": "true | mostly_true | misleading | disputed | false | unknown"
}
```

### EducationQuestion

```json
{
  "question_id": "",
  "question": "Why is debt not being paid down?",
  "question_type": "normalization | money_flow | incentive | timeline | constraint | verdict",
  "parent_claim_id": "",
  "facts_needed": [],
  "output_slide_type": "debt_why_not_paid_down"
}
```

### LessonBeat

```json
{
  "slide_id": "debt.why_not_paid_down",
  "title": "Why is debt not being paid down?",
  "teaching_goal": "Show why higher revenue does not automatically reduce accumulated debt.",
  "facts": [],
  "visual_metaphor": "leaky bucket",
  "voiceover": "More revenue does not pay debt down unless spending and interest leave a real surplus."
}
```

---

## Universal slide archetypes from this session

1. **Raw change** — “What changed in dollars?”
2. **Composition check** — “Did percentages change, or only totals?”
3. **Money source** — “Where did extra money come from?”
4. **Per-person burden** — “Is each person paying more?”
5. **Burden mechanism** — “Why can tax per person rise?”
6. **Money destination** — “Where did the money go?”
7. **Constraint check** — “Why did more revenue not solve the problem?”
8. **Timeline** — “Who was in power and what shocks hit?”
9. **Incentive map** — “Who wants this framed this way?”
10. **Verdict/checklist** — “What should citizens ask next?”

---

## Implementation implication

The next major backend refactor should not hard-code these as gas-tax slides. It should create an `education_planner.py` that:

1. takes claim objects,
2. generates this question sequence,
3. decides which question archetypes apply,
4. asks research for missing facts,
5. outputs lesson beats,
6. lets `infographic_planner.py` render those beats into slides.
