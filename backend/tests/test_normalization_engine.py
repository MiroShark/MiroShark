import math

import pytest

from app.services.normalization_engine import (
    NormalizationError,
    build_normalized_comparison,
    growth_rate,
    inflation_adjust,
    per_capita,
    ratio,
    share_of_total,
)


def test_core_normalization_helpers():
    assert per_capita(217.866, 21.0172) == pytest.approx(10.366, abs=0.001)
    assert growth_rate(100, 125) == pytest.approx(0.25)
    assert ratio(100, 250) == pytest.approx(2.5)
    assert share_of_total(25, 100) == pytest.approx(0.25)
    assert inflation_adjust(100, 80, 120) == pytest.approx(150)


@pytest.mark.parametrize(
    "fn,args,error",
    [
        (per_capita, (100, 0), "population must be greater than zero"),
        (growth_rate, (0, 100), "start must not be zero"),
        (ratio, (0, 100), "start must not be zero"),
        (share_of_total, (10, 0), "total must be greater than zero"),
        (inflation_adjust, (100, 0, 120), "cpi_start must be greater than zero"),
    ],
)
def test_invalid_denominators_raise_clear_errors(fn, args, error):
    with pytest.raises(NormalizationError, match=error):
        fn(*args)


def test_build_normalized_comparison_for_australian_tax_per_person_acceptance_numbers():
    comparison = build_normalized_comparison(
        "Australian Government taxation receipts",
        start=217.866,
        end=657.844,
        denominators={
            "start": {"population": 21.0172},
            "end": {"population": 27.614411},
        },
    )

    assert comparison["schema_version"] == "normalization-comparison/v1"
    assert comparison["start"]["per_capita"] == pytest.approx(10.366, abs=0.001)
    assert comparison["end"]["per_capita"] == pytest.approx(23.822, abs=0.001)
    assert comparison["changes"]["population_growth_rate"] == pytest.approx(0.314, abs=0.001)
    assert comparison["changes"]["per_capita_ratio"] == pytest.approx(2.298, abs=0.001)
    assert "per_capita" in comparison["available_views"]
    assert "population_growth" in comparison["available_views"]


def test_build_normalized_comparison_supports_flat_denominators_and_shares():
    comparison = build_normalized_comparison(
        "Program spending",
        start={"value": 20, "budget_total": 200},
        end={"value": 30},
        denominators={"end_budget_total": 300, "start_gdp": 1000, "end_gdp": 1500},
        cpi={"start": 100, "end": 125},
    )

    assert comparison["start"]["share_of_budget"] == pytest.approx(0.10)
    assert comparison["end"]["share_of_budget"] == pytest.approx(0.10)
    assert comparison["changes"]["share_of_budget_change_pp"] == pytest.approx(0.0)
    assert comparison["start"]["share_of_gdp"] == pytest.approx(0.02)
    assert comparison["end"]["share_of_gdp"] == pytest.approx(0.02)
    assert comparison["changes"]["real_start_in_end_dollars"] == pytest.approx(25)
    assert comparison["changes"]["real_growth_rate"] == pytest.approx(0.2)
    assert "real_dollars" in comparison["available_views"]
