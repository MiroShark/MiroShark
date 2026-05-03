import pytest

from app.services.fact_packs.australia_budget import (
    fact_value,
    facts_as_dicts,
    get_fact,
    normalization_inputs_for_tax_per_resident,
)
from app.services.normalization_engine import build_normalized_comparison


def test_fact_pack_exposes_source_metadata():
    fact = get_fact("tax_receipts_2024_25")

    assert fact.value == pytest.approx(657.844)
    assert fact.unit == "AUD_billion"
    assert fact.reference_period == "2024-25"
    assert fact.source_type == "official_budget"
    assert fact.source_url.startswith("https://")


def test_fact_pack_can_return_dict_facts_for_fact_ledger():
    facts = facts_as_dicts("tax_receipts_2006_07", "population_2007")

    assert [f["fact_id"] for f in facts] == ["tax_receipts_2006_07", "population_2007"]
    assert all(f["source_name"] for f in facts)
    assert all(f["reference_period"] for f in facts)


def test_tax_per_resident_inputs_feed_normalization_engine():
    inputs = normalization_inputs_for_tax_per_resident()
    comparison = build_normalized_comparison(
        inputs["label"],
        start=inputs["start"],
        end=inputs["end"],
        denominators=inputs["denominators"],
    )

    assert fact_value("population_2007") == pytest.approx(21.0172)
    assert comparison["start"]["per_capita"] == pytest.approx(10.366, abs=0.001)
    assert comparison["end"]["per_capita"] == pytest.approx(23.822, abs=0.001)
    assert {f["fact_id"] for f in inputs["source_facts"]} == {
        "tax_receipts_2006_07",
        "tax_receipts_2024_25",
        "population_2007",
        "population_2025",
    }
