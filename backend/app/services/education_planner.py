"""Generic education/debunking lesson planner.

This module captures the methodology from docs/education-question-methodology.md
as reusable lesson beats. It intentionally avoids topic-specific facts; specialist
planners can enrich these beats with sourced numbers and rendered slide prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re


@dataclass
class ClaimAnalysis:
    claim_id: str
    surface_claim: str
    implied_claims: list[str] = field(default_factory=list)
    emotional_hook: str = ""
    claim_type: str = "unknown"
    true_parts: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)
    misleading_parts: list[str] = field(default_factory=list)
    normalizations_needed: list[str] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    verdict: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "surface_claim": self.surface_claim,
            "implied_claims": self.implied_claims,
            "emotional_hook": self.emotional_hook,
            "claim_type": self.claim_type,
            "true_parts": self.true_parts,
            "missing_context": self.missing_context,
            "misleading_parts": self.misleading_parts,
            "normalizations_needed": self.normalizations_needed,
            "stakeholders": self.stakeholders,
            "evidence_requirements": self.evidence_requirements,
            "verdict": self.verdict,
        }


@dataclass
class EducationQuestion:
    question_id: str
    question: str
    question_type: str
    parent_claim_id: str = ""
    facts_needed: list[str] = field(default_factory=list)
    output_slide_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "question_type": self.question_type,
            "parent_claim_id": self.parent_claim_id,
            "facts_needed": self.facts_needed,
            "output_slide_type": self.output_slide_type,
        }


@dataclass
class LessonBeat:
    slide_id: str
    title: str
    teaching_goal: str
    question_id: str
    facts_needed: list[str]
    visual_metaphor: str
    voiceover: str
    slide_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "title": self.title,
            "teaching_goal": self.teaching_goal,
            "question_id": self.question_id,
            "facts_needed": self.facts_needed,
            "visual_metaphor": self.visual_metaphor,
            "voiceover": self.voiceover,
            "slide_type": self.slide_type,
        }


QUESTION_ARCHETYPES: list[dict[str, Any]] = [
    {
        "id": "surface_claim",
        "question": "What exactly is being claimed?",
        "type": "claim",
        "slide_type": "talking_point_card",
        "facts": ["claim text", "speaker/source", "date/context"],
        "title": "The talking point",
        "goal": "Make the claim precise before arguing about it.",
        "visual": "quote card with implied claim and emotional hook",
        "voiceover": "First, pin down the exact claim. Vague slogans are easier to spread than clear statements.",
    },
    {
        "id": "true_part",
        "question": "What is true in the claim?",
        "type": "evidence",
        "slide_type": "true_part_card",
        "facts": ["best supporting fact", "highest-quality source", "confidence rating"],
        "title": "What is true here?",
        "goal": "Concede the part the audience can verify so the response stays fair.",
        "visual": "green check beside sourced facts",
        "voiceover": "Start with what is true. A good explanation does not pretend the other side has no evidence.",
    },
    {
        "id": "missing_context",
        "question": "What context is missing?",
        "type": "context",
        "slide_type": "missing_context_card",
        "facts": ["baseline", "time period", "comparison frame"],
        "title": "What context is missing?",
        "goal": "Show the comparison frame needed to understand the claim.",
        "visual": "before/after frame with missing labels highlighted",
        "voiceover": "Then ask: compared with what? Time period, baseline and denominator change the story.",
    },
    {
        "id": "normalization",
        "question": "What normalized views are needed?",
        "type": "normalization",
        "slide_type": "normalization_check",
        "facts": ["per-capita denominator", "inflation index", "GDP or budget total", "income/wage baseline"],
        "title": "What does the fair comparison show?",
        "goal": "Prevent raw totals from doing all the persuasive work.",
        "visual": "raw dollars split into per-person, real-dollar and percentage views",
        "voiceover": "Raw totals are only layer one. Check per person, real dollars and percentage burden.",
    },
    {
        "id": "money_source",
        "question": "Where is the extra money coming from?",
        "type": "money_flow",
        "slide_type": "money_source_flow",
        "facts": ["revenue streams", "explicit policy changes", "automatic revenue changes"],
        "title": "Where does the extra money come from?",
        "goal": "Separate explicit tax hikes from growth in tax bases, prices, wages and profits.",
        "visual": "flow diagram from revenue sources into government receipts",
        "voiceover": "Trace the money source. Is it a new tax, a bigger base, higher prices, higher wages, or debt?",
    },
    {
        "id": "burden_mechanism",
        "question": "Why can the burden rise without an obvious new tax?",
        "type": "mechanism",
        "slide_type": "burden_mechanism",
        "facts": ["bracket/indexation rules", "inflation", "wage growth", "profit growth"],
        "title": "Why can the burden rise?",
        "goal": "Explain hidden mechanisms such as bracket creep and nominal growth.",
        "visual": "cause board: inflation, wages, bracket creep, profits",
        "voiceover": "Sometimes no one announces a new tax. Inflation, wages and brackets can lift the take quietly.",
    },
    {
        "id": "money_destination",
        "question": "Where is the money going?",
        "type": "money_flow",
        "slide_type": "money_destination_flow",
        "facts": ["major spending buckets", "beneficiaries", "growth drivers"],
        "title": "Where does the money go?",
        "goal": "Show which programs, people and obligations absorb revenue.",
        "visual": "spending bucket map",
        "voiceover": "Now follow the money out: services, transfers, infrastructure, defence and interest.",
    },
    {
        "id": "constraint_check",
        "question": "If revenue is rising, why is the problem not solved?",
        "type": "constraint",
        "slide_type": "constraint_check",
        "facts": ["receipts", "expenses", "deficit/surplus", "debt stock", "interest cost"],
        "title": "Why does the problem remain?",
        "goal": "Show why higher revenue may not solve the claimed problem.",
        "visual": "leaky bucket or balance scale",
        "voiceover": "More revenue only solves the problem if it is bigger than spending, interest and new promises.",
    },
    {
        "id": "incentive_map",
        "question": "Who has incentives to frame the story this way?",
        "type": "incentive",
        "slide_type": "stakeholder_incentive_map",
        "facts": ["stakeholders", "funding", "benefits", "omissions"],
        "title": "Who benefits from this framing?",
        "goal": "Reveal why each side emphasizes some facts and omits others.",
        "visual": "stakeholder map with incentives and omissions",
        "voiceover": "Every public message has incentives behind it. Ask who gains if you believe this framing.",
    },
    {
        "id": "timeline",
        "question": "What historical timeline explains the current state?",
        "type": "timeline",
        "slide_type": "historical_timeline",
        "facts": ["baseline year", "key shocks", "policy changes", "who was responsible"],
        "title": "How did we get here?",
        "goal": "Separate inherited conditions, shocks and choices across time.",
        "visual": "timeline with shocks and decision points",
        "voiceover": "Put the history on a line. Blame gets clearer when timing is visible.",
    },
    {
        "id": "fair_conclusion",
        "question": "What would a fair conclusion say?",
        "type": "verdict",
        "slide_type": "fair_conclusion",
        "facts": ["solid findings", "misleading parts", "unknowns", "questions to ask next"],
        "title": "What should we conclude?",
        "goal": "End with a citizen checklist rather than a slogan.",
        "visual": "verdict card: true, missing, misleading, ask next",
        "voiceover": "A useful ending says what is solid, what is misleading, and what citizens should ask next.",
    },
]


def plan_education_sequence(
    *,
    topic: str,
    claims: list[str | dict[str, Any]] | None = None,
    audience_level: str = "general_public",
) -> dict[str, Any]:
    """Return a generic education/debunking question sequence."""

    claim_objects = [_normalise_claim(c, idx) for idx, c in enumerate(claims or [])]
    primary_claim_id = claim_objects[0].claim_id if claim_objects else ""
    questions = [_question_from_archetype(a, primary_claim_id) for a in QUESTION_ARCHETYPES]
    beats = [_beat_from_archetype(a) for a in QUESTION_ARCHETYPES]
    return {
        "schema_version": "education-plan/v1",
        "topic": topic or "Untitled topic",
        "audience_level": audience_level,
        "claims": [c.to_dict() for c in claim_objects],
        "questions": [q.to_dict() for q in questions],
        "lesson_beats": [b.to_dict() for b in beats],
        "methodology": "claim -> truth -> missing context -> normalization -> money/power flow -> constraints -> incentives -> timeline -> fair conclusion",
    }


def _normalise_claim(claim: str | dict[str, Any], idx: int) -> ClaimAnalysis:
    if isinstance(claim, dict):
        surface = str(claim.get("surface_claim") or claim.get("claim") or claim.get("text") or "").strip()
        claim_id = str(claim.get("claim_id") or _slug(surface or f"claim {idx + 1}"))
        return ClaimAnalysis(
            claim_id=claim_id,
            surface_claim=surface,
            implied_claims=list(claim.get("implied_claims") or []),
            emotional_hook=str(claim.get("emotional_hook") or ""),
            claim_type=str(claim.get("claim_type") or _infer_claim_type(surface)),
            true_parts=list(claim.get("true_parts") or []),
            missing_context=list(claim.get("missing_context") or []),
            misleading_parts=list(claim.get("misleading_parts") or []),
            normalizations_needed=list(claim.get("normalizations_needed") or _infer_normalizations(surface)),
            stakeholders=list(claim.get("stakeholders") or []),
            evidence_requirements=list(claim.get("evidence_requirements") or _default_evidence_requirements(surface)),
            verdict=str(claim.get("verdict") or "unknown"),
        )
    surface = str(claim or "").strip()
    return ClaimAnalysis(
        claim_id=_slug(surface or f"claim {idx + 1}"),
        surface_claim=surface,
        claim_type=_infer_claim_type(surface),
        normalizations_needed=_infer_normalizations(surface),
        evidence_requirements=_default_evidence_requirements(surface),
    )


def _question_from_archetype(archetype: dict[str, Any], claim_id: str) -> EducationQuestion:
    return EducationQuestion(
        question_id=archetype["id"],
        question=archetype["question"],
        question_type=archetype["type"],
        parent_claim_id=claim_id,
        facts_needed=list(archetype["facts"]),
        output_slide_type=archetype["slide_type"],
    )


def _beat_from_archetype(archetype: dict[str, Any]) -> LessonBeat:
    return LessonBeat(
        slide_id=f"education.{archetype['id']}",
        title=archetype["title"],
        teaching_goal=archetype["goal"],
        question_id=archetype["id"],
        facts_needed=list(archetype["facts"]),
        visual_metaphor=archetype["visual"],
        voiceover=archetype["voiceover"],
        slide_type=archetype["slide_type"],
    )


def _infer_claim_type(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("$", "%", "more", "less", "increase", "decrease", "spending", "tax", "debt")):
        return "numeric"
    if any(token in lowered for token in ("because", "caused", "will", "leads to")):
        return "causal"
    if any(token in lowered for token in ("blame", "fault", "responsible")):
        return "blame"
    return "unknown"


def _infer_normalizations(text: str) -> list[str]:
    lowered = text.lower()
    normalizations: list[str] = []
    if any(token in lowered for token in ("spending", "tax", "revenue", "debt", "more", "increase")):
        normalizations.extend(["per_capita", "real_dollars", "share_of_gdp", "share_of_budget"])
    if any(token in lowered for token in ("tax", "wages", "income")):
        normalizations.append("share_of_income")
    return list(dict.fromkeys(normalizations))


def _default_evidence_requirements(text: str) -> list[str]:
    lowered = text.lower()
    requirements = ["high-quality source for the surface claim"]
    if any(token in lowered for token in ("spending", "tax", "revenue", "debt")):
        requirements.extend(["baseline number", "current number", "denominator for fair comparison"])
    return requirements


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:80] or "claim"
