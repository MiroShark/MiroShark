"""Australian Commonwealth budget/population fact pack.

Values are intentionally stored as structured facts rather than prose so the
normalization engine, slide planners, and future research ledger can reuse the
same source-tagged inputs.

Unit conventions:
- money facts use AUD billions unless otherwise noted
- population facts use millions of residents
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Fact:
    fact_id: str
    label: str
    value: float
    unit: str
    reference_period: str
    source_name: str
    source_url: str
    source_type: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "reference_period": self.reference_period,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "notes": self.notes,
        }


BUDGET_PAPER_1_2025_26 = "https://budget.gov.au/content/bp1/index.htm"
FINAL_BUDGET_OUTCOME_2006_07 = "https://archive.budget.gov.au/2006-07/fbo/html/index.htm"
ABS_POPULATION_CLOCK = "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population"

FACTS: dict[str, Fact] = {
    "tax_receipts_2006_07": Fact(
        fact_id="tax_receipts_2006_07",
        label="Australian Government taxation receipts",
        value=217.866,
        unit="AUD_billion",
        reference_period="2006-07",
        source_name="Final Budget Outcome 2006-07",
        source_url=FINAL_BUDGET_OUTCOME_2006_07,
        source_type="official_budget",
        notes="Used as the baseline tax receipts figure for per-resident normalization.",
    ),
    "tax_receipts_2024_25": Fact(
        fact_id="tax_receipts_2024_25",
        label="Australian Government taxation receipts",
        value=657.844,
        unit="AUD_billion",
        reference_period="2024-25",
        source_name="Budget Paper No. 1 2025-26",
        source_url=BUDGET_PAPER_1_2025_26,
        source_type="official_budget",
        notes="Estimated/current-year taxation receipts used in the gas-tax pilot.",
    ),
    "cash_receipts_2006_07": Fact(
        fact_id="cash_receipts_2006_07",
        label="Australian Government cash receipts",
        value=236.7,
        unit="AUD_billion",
        reference_period="2006-07",
        source_name="Final Budget Outcome 2006-07",
        source_url=FINAL_BUDGET_OUTCOME_2006_07,
        source_type="official_budget",
    ),
    "cash_receipts_2024_25": Fact(
        fact_id="cash_receipts_2024_25",
        label="Australian Government cash receipts",
        value=717.0,
        unit="AUD_billion",
        reference_period="2024-25",
        source_name="Budget Paper No. 1 2025-26",
        source_url=BUDGET_PAPER_1_2025_26,
        source_type="official_budget",
    ),
    "expenses_2006_07": Fact(
        fact_id="expenses_2006_07",
        label="Australian Government total expenses",
        value=219.4,
        unit="AUD_billion",
        reference_period="2006-07",
        source_name="Final Budget Outcome 2006-07",
        source_url=FINAL_BUDGET_OUTCOME_2006_07,
        source_type="official_budget",
    ),
    "expenses_2025_26": Fact(
        fact_id="expenses_2025_26",
        label="Australian Government total expenses",
        value=785.7,
        unit="AUD_billion",
        reference_period="2025-26",
        source_name="Budget Paper No. 1 2025-26",
        source_url=BUDGET_PAPER_1_2025_26,
        source_type="official_budget",
    ),
    "population_2007": Fact(
        fact_id="population_2007",
        label="Australia resident population",
        value=21.0172,
        unit="million_people",
        reference_period="30 June 2007",
        source_name="Australian Bureau of Statistics, National/state population",
        source_url=ABS_POPULATION_CLOCK,
        source_type="official_statistics",
    ),
    "population_2025": Fact(
        fact_id="population_2025",
        label="Australia resident population",
        value=27.614411,
        unit="million_people",
        reference_period="30 June 2025",
        source_name="Australian Bureau of Statistics, National/state population",
        source_url=ABS_POPULATION_CLOCK,
        source_type="official_statistics",
    ),
    "net_debt_2006_07": Fact(
        fact_id="net_debt_2006_07",
        label="Australian Government net debt",
        value=-24.0,
        unit="AUD_billion",
        reference_period="2006-07",
        source_name="Final Budget Outcome 2006-07",
        source_url=FINAL_BUDGET_OUTCOME_2006_07,
        source_type="official_budget",
        notes="Negative net debt indicates net financial assets on this measure.",
    ),
    "net_debt_2025_26": Fact(
        fact_id="net_debt_2025_26",
        label="Australian Government net debt",
        value=556.0,
        unit="AUD_billion",
        reference_period="2025-26",
        source_name="Budget Paper No. 1 2025-26",
        source_url=BUDGET_PAPER_1_2025_26,
        source_type="official_budget",
        notes="Rounded budget estimate used for debt-context slides.",
    ),
}


def get_fact(fact_id: str) -> Fact:
    try:
        return FACTS[fact_id]
    except KeyError as exc:
        raise KeyError(f"Unknown Australia budget fact: {fact_id}") from exc


def fact_value(fact_id: str) -> float:
    return get_fact(fact_id).value


def facts_as_dicts(*fact_ids: str) -> list[dict[str, Any]]:
    ids = fact_ids or tuple(FACTS.keys())
    return [FACTS[fact_id].to_dict() for fact_id in ids]


def normalization_inputs_for_tax_per_resident() -> dict[str, Any]:
    """Return inputs for the pilot's tax-per-resident comparison."""

    return {
        "label": "Australian Government taxation receipts",
        "start": fact_value("tax_receipts_2006_07"),
        "end": fact_value("tax_receipts_2024_25"),
        "denominators": {
            "start": {"population": fact_value("population_2007")},
            "end": {"population": fact_value("population_2025")},
        },
        "source_facts": facts_as_dicts(
            "tax_receipts_2006_07",
            "tax_receipts_2024_25",
            "population_2007",
            "population_2025",
        ),
    }
