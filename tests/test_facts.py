from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from marketscope.facts import (
    Fact,
    Periodicity,
    classify_period,
    derive_fourth_quarter,
    extract_facts,
    latest_filed,
    superseded,
)


def observation(
    *,
    val: float,
    end: str,
    start: str | None = None,
    filed: str = "2023-02-01",
    accn: str = "0000019617-23-000001",
    form: str = "10-K",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "val": val,
        "end": end,
        "filed": filed,
        "accn": accn,
        "form": form,
        "fy": 2022,
        "fp": "FY",
    }
    if start is not None:
        payload["start"] = start
    return payload


def payload_with(
    units: dict[str, list[dict[str, Any]]], *, taxonomy: str = "us-gaap"
) -> dict[str, Any]:
    return {"facts": {taxonomy: {"Deposits": {"units": units}}}}


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (None, date(2022, 12, 31), Periodicity.INSTANT),
        (date(2022, 10, 1), date(2022, 12, 31), Periodicity.QUARTERLY),
        (date(2022, 1, 1), date(2022, 6, 30), Periodicity.SEMIANNUAL),
        (date(2022, 1, 1), date(2022, 9, 30), Periodicity.NINE_MONTH),
        (date(2022, 1, 1), date(2022, 12, 31), Periodicity.ANNUAL),
        (date(2022, 1, 1), date(2022, 2, 15), Periodicity.OTHER),
    ],
)
def test_classify_period(start: date | None, end: date, expected: Periodicity) -> None:
    assert classify_period(start, end) is expected


def test_extract_facts_reads_instant_and_duration_observations() -> None:
    payload = payload_with(
        {
            "USD": [
                observation(val=100.0, end="2022-12-31"),
                observation(val=25.0, start="2022-10-01", end="2022-12-31"),
            ]
        }
    )

    facts = extract_facts(payload)

    assert [fact.periodicity for fact in facts] == [Periodicity.INSTANT, Periodicity.QUARTERLY]
    assert facts[0].period_start is None
    assert facts[1].value == 25.0


def test_extract_facts_filters_by_tag_and_unit() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "Deposits": {"units": {"USD": [observation(val=1.0, end="2022-12-31")]}},
                "Assets": {"units": {"USD": [observation(val=2.0, end="2022-12-31")]}},
            }
        }
    }

    facts = extract_facts(payload, tags=["Deposits"])

    assert [fact.tag for fact in facts] == ["Deposits"]


def test_extract_facts_ignores_unrequested_units() -> None:
    payload = payload_with(
        {
            "USD": [observation(val=1.0, end="2022-12-31")],
            "shares": [observation(val=5.0, end="2022-12-31")],
        }
    )

    facts = extract_facts(payload)

    assert [fact.unit for fact in facts] == ["USD"]


def test_extract_facts_reads_every_taxonomy_when_none_requested() -> None:
    payload = {
        "facts": {
            "us-gaap": {"Deposits": {"units": {"USD": [observation(val=1.0, end="2022-12-31")]}}},
            "jpm": {"Deposits": {"units": {"USD": [observation(val=2.0, end="2022-12-31")]}}},
        }
    }

    facts = extract_facts(payload, taxonomy=None)

    assert {fact.taxonomy for fact in facts} == {"us-gaap", "jpm"}


def test_extract_facts_returns_nothing_for_a_missing_taxonomy() -> None:
    assert extract_facts({"facts": {}}) == []


def test_latest_filed_keeps_the_most_recent_value_for_a_period() -> None:
    payload = payload_with(
        {
            "USD": [
                observation(val=100.0, end="2022-12-31", filed="2023-02-01", accn="a"),
                observation(val=110.0, end="2022-12-31", filed="2023-08-01", accn="b"),
            ]
        }
    )

    current = latest_filed(extract_facts(payload))

    assert [fact.value for fact in current] == [110.0]


def test_superseded_returns_the_replaced_value() -> None:
    payload = payload_with(
        {
            "USD": [
                observation(val=100.0, end="2022-12-31", filed="2023-02-01", accn="a"),
                observation(val=110.0, end="2022-12-31", filed="2023-08-01", accn="b"),
            ]
        }
    )

    replaced = superseded(extract_facts(payload))

    assert [fact.value for fact in replaced] == [100.0]


def test_superseded_is_empty_when_nothing_was_restated() -> None:
    payload = payload_with({"USD": [observation(val=100.0, end="2022-12-31")]})

    assert superseded(extract_facts(payload)) == []


def duration(value: float, start: str, end: str) -> Fact:
    return Fact(
        taxonomy="us-gaap",
        tag="InterestExpenseDeposits",
        unit="USD",
        value=value,
        period_start=date.fromisoformat(start),
        period_end=date.fromisoformat(end),
        filed=date(2023, 2, 1),
        accession="0000019617-23-000001",
        form="10-K",
    )


def test_derive_fourth_quarter_uses_the_nine_month_figure() -> None:
    facts = [
        duration(1000.0, "2022-01-01", "2022-12-31"),
        duration(600.0, "2022-01-01", "2022-09-30"),
    ]

    derived = derive_fourth_quarter(facts)

    assert len(derived) == 1
    assert derived[0].value == 400.0
    assert derived[0].period_start == date(2022, 10, 1)
    assert derived[0].period_end == date(2022, 12, 31)
    assert derived[0].derived is True
    assert derived[0].fiscal_period == "Q4"


def test_derive_fourth_quarter_falls_back_to_summing_quarters() -> None:
    facts = [
        duration(1000.0, "2022-01-01", "2022-12-31"),
        duration(200.0, "2022-01-01", "2022-03-31"),
        duration(250.0, "2022-04-01", "2022-06-30"),
        duration(150.0, "2022-07-01", "2022-09-30"),
    ]

    derived = derive_fourth_quarter(facts)

    assert [fact.value for fact in derived] == [400.0]
    assert derived[0].period_start == date(2022, 10, 1)


def test_derive_fourth_quarter_prefers_nine_month_over_summed_quarters() -> None:
    facts = [
        duration(1000.0, "2022-01-01", "2022-12-31"),
        duration(600.0, "2022-01-01", "2022-09-30"),
        duration(200.0, "2022-01-01", "2022-03-31"),
        duration(250.0, "2022-04-01", "2022-06-30"),
    ]

    derived = derive_fourth_quarter(facts)

    assert [fact.value for fact in derived] == [400.0]


def test_derive_fourth_quarter_skips_years_with_a_gap_in_the_quarters() -> None:
    facts = [
        duration(1000.0, "2022-01-01", "2022-12-31"),
        duration(200.0, "2022-01-01", "2022-03-31"),
        duration(150.0, "2022-07-01", "2022-09-30"),
    ]

    assert derive_fourth_quarter(facts) == []


def test_derive_fourth_quarter_ignores_instant_facts() -> None:
    balance = Fact(
        taxonomy="us-gaap",
        tag="Deposits",
        unit="USD",
        value=5000.0,
        period_end=date(2022, 12, 31),
        filed=date(2023, 2, 1),
    )

    assert derive_fourth_quarter([balance]) == []
