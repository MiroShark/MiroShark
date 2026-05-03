from app.services.education_planner import plan_education_sequence


def test_plan_education_sequence_generates_universal_question_methodology():
    plan = plan_education_sequence(
        topic="Government debt and tax burden",
        claims=["They collect more tax every year but never pay down debt"],
    )

    assert plan["schema_version"] == "education-plan/v1"
    assert plan["topic"] == "Government debt and tax burden"
    assert plan["claims"][0]["claim_type"] == "numeric"
    assert "per_capita" in plan["claims"][0]["normalizations_needed"]

    question_ids = [q["question_id"] for q in plan["questions"]]
    assert question_ids == [
        "surface_claim",
        "true_part",
        "missing_context",
        "normalization",
        "money_source",
        "burden_mechanism",
        "money_destination",
        "constraint_check",
        "incentive_map",
        "timeline",
        "fair_conclusion",
    ]

    beat_by_question = {beat["question_id"]: beat for beat in plan["lesson_beats"]}
    assert beat_by_question["constraint_check"]["slide_type"] == "constraint_check"
    assert "More revenue only solves" in beat_by_question["constraint_check"]["voiceover"]


def test_plan_education_sequence_accepts_structured_claims():
    plan = plan_education_sequence(
        topic="Housing affordability",
        claims=[
            {
                "claim_id": "housing.supply_only",
                "surface_claim": "Housing is expensive only because of supply",
                "claim_type": "causal",
                "implied_claims": ["Demand policy does not matter"],
                "normalizations_needed": ["price_to_income", "dwellings_per_capita"],
            }
        ],
        audience_level="beginner",
    )

    claim = plan["claims"][0]
    assert claim["claim_id"] == "housing.supply_only"
    assert claim["claim_type"] == "causal"
    assert claim["implied_claims"] == ["Demand policy does not matter"]
    assert claim["normalizations_needed"] == ["price_to_income", "dwellings_per_capita"]
    assert plan["audience_level"] == "beginner"

from app.services.infographic_planner import plan_generic_education_infographics


def test_generic_education_plan_can_be_adapted_to_infographic_slides():
    plan = plan_generic_education_infographics(
        "Government debt and tax burden",
        ["They collect more tax every year but never pay down debt"],
        format="tiktok",
    )

    assert plan["planner"] == "generic_education"
    assert plan["slide_count"] == 11
    assert plan["education_plan"]["questions"][0]["question_id"] == "surface_claim"

    sequence = plan["sequence"]
    slide_ids = [slide["slide_id"] for slide in sequence]
    assert "education.surface_claim" in slide_ids
    assert "education.constraint_check" in slide_ids

    constraint_slide = next(slide for slide in sequence if slide["slide_id"] == "education.constraint_check")
    assert constraint_slide["slide_type"] == "constraint_check"
    assert constraint_slide["chapter"] == "Education method"
    assert any("deficit/surplus" in fact["text"] for fact in constraint_slide["facts"])
    assert constraint_slide["image_prompt"].startswith("Create one simple educational infographic slide")
