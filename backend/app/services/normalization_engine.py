"""Numeric normalization helpers for education/debunking plans.

The education product should not compare raw totals alone. This module provides
small deterministic transforms that can be used by topic-specific fact packs,
slide planners, and tests before an LLM or image model writes the explanation.

Conventions:
- Rates and shares are returned as fractions, not percentages. Example: 0.25 = 25%.
- ``per_capita`` preserves the units supplied by the caller. If ``total`` is in
  billions and ``population`` is in millions, the result is thousands per person.
- CPI adjustment converts a value from the start CPI period into end-period dollars:
  ``value * cpi_end / cpi_start``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class NormalizationError(ValueError):
    """Raised when a normalization cannot be computed safely."""


@dataclass(frozen=True)
class PeriodSnapshot:
    """A single period's normalized values."""

    nominal_total: float
    population: float | None = None
    budget_total: float | None = None
    gdp: float | None = None
    income: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"nominal_total": self.nominal_total}
        if self.population is not None:
            data["population"] = self.population
            data["per_capita"] = per_capita(self.nominal_total, self.population)
        if self.budget_total is not None:
            data["budget_total"] = self.budget_total
            data["share_of_budget"] = share_of_total(self.nominal_total, self.budget_total)
        if self.gdp is not None:
            data["gdp"] = self.gdp
            data["share_of_gdp"] = share_of_total(self.nominal_total, self.gdp)
        if self.income is not None:
            data["income"] = self.income
            data["share_of_income"] = share_of_total(self.nominal_total, self.income)
        return data


def per_capita(total: float, population: float) -> float:
    """Return total divided by population with denominator validation."""

    return _number(total, "total") / _positive(population, "population")


def growth_rate(start: float, end: float) -> float:
    """Return fractional growth from start to end: (end - start) / start."""

    start_value = _nonzero(start, "start")
    return (_number(end, "end") - start_value) / start_value


def ratio(start: float, end: float) -> float:
    """Return end/start with denominator validation."""

    return _number(end, "end") / _nonzero(start, "start")


def share_of_total(part: float, total: float) -> float:
    """Return part/total as a fraction."""

    return _number(part, "part") / _positive(total, "total")


def inflation_adjust(value: float, cpi_start: float, cpi_end: float) -> float:
    """Convert ``value`` from the start CPI period into end-period dollars."""

    return _number(value, "value") * _positive(cpi_end, "cpi_end") / _positive(cpi_start, "cpi_start")


def build_normalized_comparison(
    label: str,
    start: float | Mapping[str, Any],
    end: float | Mapping[str, Any],
    denominators: Mapping[str, Any] | None = None,
    cpi: Mapping[str, float] | tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Build a reusable normalized comparison between two periods.

    ``start`` and ``end`` can be raw numeric totals or dictionaries containing
    ``value``/``total`` plus optional denominators. ``denominators`` can be
    nested by period::

        {"start": {"population": 21.0}, "end": {"population": 27.6}}

    or flat::

        {"start_population": 21.0, "end_population": 27.6}

    Supported denominator keys: ``population``, ``budget_total``, ``gdp``,
    ``income``. The output is intentionally verbose so slide planners can choose
    the most useful teaching angle without recomputing numbers.
    """

    denominators = denominators or {}
    start_snapshot = _snapshot(start, denominators, "start")
    end_snapshot = _snapshot(end, denominators, "end")
    start_data = start_snapshot.to_dict()
    end_data = end_snapshot.to_dict()

    changes: dict[str, Any] = {
        "absolute_change": end_snapshot.nominal_total - start_snapshot.nominal_total,
        "nominal_growth_rate": growth_rate(start_snapshot.nominal_total, end_snapshot.nominal_total),
        "nominal_ratio": ratio(start_snapshot.nominal_total, end_snapshot.nominal_total),
    }

    if start_snapshot.population is not None and end_snapshot.population is not None:
        start_pc = start_data["per_capita"]
        end_pc = end_data["per_capita"]
        changes.update({
            "population_growth_rate": growth_rate(start_snapshot.population, end_snapshot.population),
            "population_ratio": ratio(start_snapshot.population, end_snapshot.population),
            "per_capita_change": end_pc - start_pc,
            "per_capita_growth_rate": growth_rate(start_pc, end_pc),
            "per_capita_ratio": ratio(start_pc, end_pc),
        })

    for key in ("share_of_budget", "share_of_gdp", "share_of_income"):
        if key in start_data and key in end_data:
            changes[f"{key}_change_pp"] = (end_data[key] - start_data[key]) * 100
            changes[f"{key}_growth_rate"] = growth_rate(start_data[key], end_data[key])

    cpi_pair = _cpi_pair(cpi)
    if cpi_pair is not None:
        cpi_start, cpi_end = cpi_pair
        real_start = inflation_adjust(start_snapshot.nominal_total, cpi_start, cpi_end)
        changes.update({
            "cpi_start": cpi_start,
            "cpi_end": cpi_end,
            "real_start_in_end_dollars": real_start,
            "real_end": end_snapshot.nominal_total,
            "real_absolute_change": end_snapshot.nominal_total - real_start,
            "real_growth_rate": growth_rate(real_start, end_snapshot.nominal_total),
            "real_ratio": ratio(real_start, end_snapshot.nominal_total),
        })
        if start_snapshot.population is not None and end_snapshot.population is not None:
            real_start_pc = per_capita(real_start, start_snapshot.population)
            end_pc = end_data["per_capita"]
            changes.update({
                "real_start_per_capita_in_end_dollars": real_start_pc,
                "real_per_capita_change": end_pc - real_start_pc,
                "real_per_capita_growth_rate": growth_rate(real_start_pc, end_pc),
                "real_per_capita_ratio": ratio(real_start_pc, end_pc),
            })

    return {
        "schema_version": "normalization-comparison/v1",
        "label": str(label or "Comparison"),
        "start": start_data,
        "end": end_data,
        "changes": changes,
        "available_views": _available_views(start_data, end_data, changes),
        "warnings": _warnings(start_data, end_data, cpi_pair),
    }


def format_money(value: float, *, prefix: str = "$", suffix: str = "", decimals: int = 1) -> str:
    """Small formatting helper for deterministic slide labels/tests."""

    return f"{prefix}{_number(value, 'value'):,.{decimals}f}{suffix}"


def format_percent(rate: float, *, decimals: int = 1) -> str:
    return f"{_number(rate, 'rate') * 100:.{decimals}f}%"


def _snapshot(source: float | Mapping[str, Any], denominators: Mapping[str, Any], period: str) -> PeriodSnapshot:
    if isinstance(source, Mapping):
        nominal = _extract_first(source, ("value", "total", "nominal_total"), required=True, label=f"{period}.value")
        local = source
    else:
        nominal = source
        local = {}

    return PeriodSnapshot(
        nominal_total=_number(nominal, f"{period}.nominal_total"),
        population=_optional_denominator(local, denominators, period, "population"),
        budget_total=_optional_denominator(local, denominators, period, "budget_total"),
        gdp=_optional_denominator(local, denominators, period, "gdp"),
        income=_optional_denominator(local, denominators, period, "income"),
    )


def _optional_denominator(local: Mapping[str, Any], denominators: Mapping[str, Any], period: str, key: str) -> float | None:
    value = local.get(key)
    if value is None:
        period_map = denominators.get(period)
        if isinstance(period_map, Mapping):
            value = period_map.get(key)
    if value is None:
        value = denominators.get(f"{period}_{key}")
    if value is None:
        return None
    return _positive(value, f"{period}.{key}")


def _extract_first(source: Mapping[str, Any], keys: tuple[str, ...], *, required: bool, label: str) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    if required:
        raise NormalizationError(f"{label} required")
    return None


def _cpi_pair(cpi: Mapping[str, float] | tuple[float, float] | None) -> tuple[float, float] | None:
    if cpi is None:
        return None
    if isinstance(cpi, tuple):
        if len(cpi) != 2:
            raise NormalizationError("cpi tuple must be (start, end)")
        return (_positive(cpi[0], "cpi_start"), _positive(cpi[1], "cpi_end"))
    return (_positive(cpi.get("start"), "cpi.start"), _positive(cpi.get("end"), "cpi.end"))


def _available_views(start: Mapping[str, Any], end: Mapping[str, Any], changes: Mapping[str, Any]) -> list[str]:
    views = ["nominal_total"]
    if "per_capita" in start and "per_capita" in end:
        views.append("per_capita")
    if "population_growth_rate" in changes:
        views.append("population_growth")
    for key in ("share_of_budget", "share_of_gdp", "share_of_income"):
        if key in start and key in end:
            views.append(key)
    if "real_growth_rate" in changes:
        views.append("real_dollars")
    if "real_per_capita_growth_rate" in changes:
        views.append("real_per_capita")
    return views


def _warnings(start: Mapping[str, Any], end: Mapping[str, Any], cpi_pair: tuple[float, float] | None) -> list[str]:
    warnings: list[str] = []
    if "per_capita" not in start or "per_capita" not in end:
        warnings.append("population denominator missing; per-capita view unavailable")
    if cpi_pair is None:
        warnings.append("CPI not supplied; real-dollar view unavailable")
    if "share_of_gdp" not in start or "share_of_gdp" not in end:
        warnings.append("GDP denominator missing; share-of-GDP view unavailable")
    return warnings


def _number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise NormalizationError(f"{label} must be numeric") from exc
    return number


def _positive(value: Any, label: str) -> float:
    number = _number(value, label)
    if number <= 0:
        raise NormalizationError(f"{label} must be greater than zero")
    return number


def _nonzero(value: Any, label: str) -> float:
    number = _number(value, label)
    if number == 0:
        raise NormalizationError(f"{label} must not be zero")
    return number
