from __future__ import annotations

from datetime import date

import pytest

from marketscope.facts import Fact
from marketscope.panel import previous_quarter_end, quarter_end, quarterly_panel


def _instant(tag: str, value: float, end: date, *, filed: date, taxonomy: str = "us-gaap") -> Fact:
    return Fact(
        taxonomy=taxonomy,
        tag=tag,
        unit="USD",
        value=value,
        period_start=None,
        period_end=end,
        filed=filed,
    )


def _duration(
    tag: str, value: float, start: date, end: date, *, filed: date, taxonomy: str = "us-gaap"
) -> Fact:
    return Fact(
        taxonomy=taxonomy,
        tag=tag,
        unit="USD",
        value=value,
        period_start=start,
        period_end=end,
        filed=filed,
    )


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2022, 1, 1), date(2022, 3, 31)),
        (date(2022, 3, 31), date(2022, 3, 31)),
        (date(2022, 5, 17), date(2022, 6, 30)),
        (date(2022, 8, 1), date(2022, 9, 30)),
        (date(2022, 12, 31), date(2022, 12, 31)),
    ],
)
def test_quarter_end(day: date, expected: date) -> None:
    assert quarter_end(day) == expected


def test_previous_quarter_end_crosses_the_year_boundary() -> None:
    assert previous_quarter_end(date(2023, 3, 31)) == date(2022, 12, 31)


def test_previous_quarter_end_within_a_year() -> None:
    assert previous_quarter_end(date(2022, 9, 30)) == date(2022, 6, 30)


def test_balances_are_taken_from_instants() -> None:
    facts = [_instant("Deposits", 100.0, date(2022, 12, 31), filed=date(2023, 2, 1))]

    assert quarterly_panel(facts) == {date(2022, 12, 31): {"Deposits": 100.0}}


def test_a_balance_reported_as_a_duration_is_ignored() -> None:
    """A deposit base is a position at a date. A duration tagged under a balance concept is
    not the same measure and must not reach the denominator."""
    facts = [
        _duration("Deposits", 100.0, date(2022, 10, 1), date(2022, 12, 31), filed=date(2023, 2, 1))
    ]

    assert quarterly_panel(facts) == {}


def test_expenses_are_taken_from_quarterly_durations() -> None:
    facts = [
        _duration(
            "InterestExpenseDeposits",
            5.0,
            date(2022, 10, 1),
            date(2022, 12, 31),
            filed=date(2023, 2, 1),
        )
    ]

    assert quarterly_panel(facts) == {date(2022, 12, 31): {"InterestExpenseDeposits": 5.0}}


def test_the_fourth_quarter_is_derived_where_a_filer_files_no_fourth_ten_q() -> None:
    """Most banks publish a 10-K rather than a fourth 10-Q, so Q4 exists only as the
    residual of the fiscal year against the nine months already reported."""
    facts = [
        _duration(
            "InterestExpenseDeposits",
            30.0,
            date(2022, 1, 1),
            date(2022, 9, 30),
            filed=date(2022, 11, 1),
        ),
        _duration(
            "InterestExpenseDeposits",
            50.0,
            date(2022, 1, 1),
            date(2022, 12, 31),
            filed=date(2023, 2, 1),
        ),
    ]

    panel = quarterly_panel(facts)

    assert panel[date(2022, 12, 31)]["InterestExpenseDeposits"] == pytest.approx(20.0)


def test_a_restated_value_replaces_the_original() -> None:
    facts = [
        _instant("Deposits", 100.0, date(2022, 12, 31), filed=date(2023, 2, 1)),
        _instant("Deposits", 110.0, date(2022, 12, 31), filed=date(2023, 8, 1)),
    ]

    assert quarterly_panel(facts)[date(2022, 12, 31)]["Deposits"] == 110.0


def test_an_extension_concept_sharing_a_standard_name_is_not_read_as_the_standard_one() -> None:
    """A filer may declare a concept in its own namespace under a name the standard
    taxonomy also uses. The two are not the same concept."""
    facts = [
        _instant("Deposits", 100.0, date(2022, 12, 31), filed=date(2023, 2, 1)),
        _instant("Deposits", 999.0, date(2022, 12, 31), filed=date(2023, 2, 1), taxonomy="jpm"),
    ]

    assert quarterly_panel(facts)[date(2022, 12, 31)]["Deposits"] == 100.0


def test_reading_every_namespace_is_available_for_profiling() -> None:
    facts = [
        _instant("Deposits", 999.0, date(2022, 12, 31), filed=date(2023, 2, 1), taxonomy="jpm")
    ]

    assert quarterly_panel(facts, taxonomy=None)[date(2022, 12, 31)]["Deposits"] == 999.0


def test_concepts_the_metric_does_not_consume_are_left_out() -> None:
    facts = [
        _instant("Assets", 1000.0, date(2022, 12, 31), filed=date(2023, 2, 1)),
        _instant("Deposits", 100.0, date(2022, 12, 31), filed=date(2023, 2, 1)),
    ]

    assert quarterly_panel(facts)[date(2022, 12, 31)] == {"Deposits": 100.0}
