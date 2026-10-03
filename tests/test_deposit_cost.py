from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from marketscope.deposit_cost import (
    DEPOSIT_COST_COLUMNS,
    FACT_FIELDS,
    bank_quarter_rows,
    deposit_cost_frame,
    facts_from_rows,
)
from marketscope.panel import Panel

FILED = date(2023, 2, 1)


def _row(
    cik: int,
    tag: str,
    value: float,
    end: date,
    start: date | None = None,
) -> tuple[Any, ...]:
    record: dict[str, Any] = {
        "cik": cik,
        "taxonomy": "us-gaap",
        "tag": tag,
        "unit": "USD",
        "value": value,
        "period_start": start,
        "period_end": end,
        "filed": FILED,
        "accession": None,
        "form": "10-Q",
        "fiscal_year": end.year,
        "fiscal_period": None,
        "frame": None,
    }
    return tuple(record[field] for field in FACT_FIELDS)


def _tier_one_quarter(cik: int, end: date, start: date) -> list[tuple[Any, ...]]:
    return [
        _row(cik, "InterestExpenseDeposits", 10.0, end, start),
        _row(cik, "InterestBearingDepositLiabilities", 1_000.0, end),
    ]


def test_facts_are_grouped_by_filer_with_fields_in_place() -> None:
    rows = [
        _row(1, "InterestExpenseDeposits", 10.0, date(2022, 6, 30), date(2022, 4, 1)),
        _row(2, "Deposits", 500.0, date(2022, 6, 30)),
    ]

    grouped = facts_from_rows(rows)

    assert set(grouped) == {1, 2}
    (expense,) = grouped[1]
    assert expense.period_start == date(2022, 4, 1)
    assert expense.period_end == date(2022, 6, 30)
    assert expense.filed == FILED
    assert expense.value == 10.0


def test_a_row_with_missing_fields_is_rejected() -> None:
    with pytest.raises(ValueError):
        facts_from_rows([_row(1, "Deposits", 500.0, date(2022, 6, 30))[:-1]])


def test_opening_balance_comes_from_the_previous_quarter() -> None:
    frame = deposit_cost_frame(
        [
            *_tier_one_quarter(1, date(2022, 3, 31), date(2022, 1, 1)),
            _row(1, "InterestExpenseDeposits", 12.0, date(2022, 6, 30), date(2022, 4, 1)),
            _row(1, "InterestBearingDepositLiabilities", 1_400.0, date(2022, 6, 30)),
        ]
    )

    assert list(frame.columns) == list(DEPOSIT_COST_COLUMNS)
    second = frame[frame["quarter_end"] == date(2022, 6, 30)].iloc[0]
    assert second["avg_method"] == "endpoint"
    assert second["metric_tier"] == "1"
    assert second["cost_of_deposits"] == pytest.approx(12.0 * 4 / 1_200.0)


def test_each_filer_is_resolved_against_its_own_facts() -> None:
    frame = deposit_cost_frame(
        [
            *_tier_one_quarter(1, date(2022, 6, 30), date(2022, 4, 1)),
            *_tier_one_quarter(2, date(2022, 9, 30), date(2022, 7, 1)),
        ]
    )

    assert sorted(zip(frame["cik"], frame["quarter_end"], strict=True)) == [
        (1, date(2022, 6, 30)),
        (2, date(2022, 9, 30)),
    ]
    assert set(frame["avg_method"]) == {"closing_only"}


def test_a_quarter_without_a_denominator_produces_no_row() -> None:
    panel = Panel(values={date(2022, 6, 30): {"InterestExpenseDeposits": 10.0}}, derived={})

    assert bank_quarter_rows(1, panel) == []


def _fiscal_2022(cik: int, tag: str, nine_month: float, annual: float) -> list[tuple[Any, ...]]:
    return [
        _row(cik, tag, nine_month, date(2022, 9, 30), date(2022, 1, 1)),
        _row(cik, tag, annual, date(2022, 12, 31), date(2022, 1, 1)),
    ]


def test_a_derived_fourth_quarter_numerator_is_flagged() -> None:
    frame = deposit_cost_frame(
        [
            *_tier_one_quarter(1, date(2022, 9, 30), date(2022, 7, 1)),
            *_fiscal_2022(1, "InterestExpenseDeposits", 25.0, 40.0),
            _row(1, "InterestBearingDepositLiabilities", 1_000.0, date(2022, 12, 31)),
        ]
    )

    flags = dict(zip(frame["quarter_end"], frame["q4_derived"], strict=True))
    assert flags == {date(2022, 9, 30): False, date(2022, 12, 31): True}


def test_a_reconstructed_numerator_is_flagged_when_any_component_is_derived() -> None:
    frame = deposit_cost_frame(
        [
            *_fiscal_2022(1, "InterestExpenseTimeDeposits", 15.0, 24.0),
            _row(1, "InterestExpenseSavingsDeposits", 4.0, date(2022, 12, 31), date(2022, 10, 1)),
            _row(1, "InterestBearingDepositLiabilities", 1_000.0, date(2022, 12, 31)),
        ]
    )

    (row,) = frame.itertuples()
    assert row.expense_provenance == "summed_components"
    assert row.q4_derived


def test_a_derived_concept_outside_the_numerator_does_not_flag_the_row() -> None:
    """Total interest expense is derived for the completeness check, not the numerator."""
    frame = deposit_cost_frame(
        [
            *_tier_one_quarter(1, date(2022, 12, 31), date(2022, 10, 1)),
            *_fiscal_2022(1, "InterestExpense", 60.0, 80.0),
        ]
    )

    (row,) = frame.itertuples()
    assert not row.q4_derived


def test_no_facts_give_an_empty_frame_with_the_expected_columns() -> None:
    frame = deposit_cost_frame([])

    assert frame.empty
    assert list(frame.columns) == list(DEPOSIT_COST_COLUMNS)
