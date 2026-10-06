from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from marketscope.facts import FACT_FIELDS, Fact
from marketscope.restatements import (
    REVISION_COLUMNS,
    RevisionKind,
    classify_revision,
    revision_frame,
    revision_rows,
)

END = date(2022, 12, 31)


def _fact(
    value: float, filed: date, accession: str, *, tag: str = "Deposits", taxonomy: str = "us-gaap"
) -> Fact:
    return Fact(
        taxonomy=taxonomy,
        tag=tag,
        unit="USD",
        value=value,
        period_end=END,
        filed=filed,
        accession=accession,
        form="10-K",
    )


def _row(cik: int, fact: Fact) -> tuple[Any, ...]:
    record = {"cik": cik, **{field: getattr(fact, field) for field in FACT_FIELDS[1:]}}
    return tuple(record[field] for field in FACT_FIELDS)


def test_revisions_are_numbered_within_a_period_and_the_last_is_current() -> None:
    facts = [
        _fact(100.0, date(2023, 2, 1), "a"),
        _fact(110.0, date(2023, 8, 1), "b"),
        _fact(105.0, date(2024, 2, 1), "c"),
    ]

    rows = [dict(zip(REVISION_COLUMNS, row, strict=True)) for row in revision_rows(1, facts)]

    assert [(r["revision_number"], r["revised_value"], r["is_current"]) for r in rows] == [
        (1, 110.0, False),
        (2, 105.0, True),
    ]
    assert rows[0]["previous_value"] == 100.0
    assert rows[0]["periodicity"] == "instant"


def test_numbering_restarts_for_each_period() -> None:
    facts = [
        _fact(100.0, date(2023, 2, 1), "a"),
        _fact(110.0, date(2023, 8, 1), "b"),
        _fact(5.0, date(2023, 2, 1), "a", tag="Assets"),
        _fact(6.0, date(2023, 8, 1), "b", tag="Assets"),
    ]

    rows = [dict(zip(REVISION_COLUMNS, row, strict=True)) for row in revision_rows(1, facts)]

    assert sorted((r["tag"], r["revision_number"], r["is_current"]) for r in rows) == [
        ("Assets", 1, True),
        ("Deposits", 1, True),
    ]


def test_concepts_of_one_name_in_two_taxonomies_are_not_compared() -> None:
    """One name in two taxonomies is two concepts, so a different value under the other
    taxonomy is not a revision."""
    facts = [
        _fact(100.0, date(2023, 2, 1), "a"),
        _fact(999.0, date(2023, 8, 1), "b", taxonomy="srt"),
    ]

    assert revision_rows(1, facts) == []


def test_the_frame_covers_every_filer_in_the_staged_rows() -> None:
    rows = [
        _row(1, _fact(100.0, date(2023, 2, 1), "a")),
        _row(1, _fact(110.0, date(2023, 8, 1), "b")),
        _row(2, _fact(50.0, date(2023, 2, 1), "c")),
        _row(2, _fact(50.0, date(2024, 2, 1), "d")),
    ]

    frame = revision_frame(rows)

    assert list(frame.columns) == list(REVISION_COLUMNS)
    assert frame["cik"].tolist() == [1]


@pytest.mark.parametrize(
    ("previous", "revised", "form", "expected"),
    [
        (53_263_000.0, 53_000_000.0, "10-K", RevisionKind.PRECISION),
        (8_592_000.0, 9_000_000.0, "10-Q", RevisionKind.PRECISION),
        (-1_455_000.0, -1_000_000.0, "10-Q", RevisionKind.PRECISION),
        (66_000.0, 0.0, "10-Q", RevisionKind.SUBSTANTIVE),
        (0.0, 400_000_000.0, "10-Q", RevisionKind.SUBSTANTIVE),
        (12_500_000.0, -12_500_000.0, "10-K", RevisionKind.SIGN),
        (418_000_000_000.0, 418_000_000.0, "10-K", RevisionKind.SCALE),
        (2_464_000.0, 4_015_000.0, "10-Q/A", RevisionKind.AMENDMENT),
        (206_000_000.0, 441_000_000.0, "10-Q", RevisionKind.SUBSTANTIVE),
    ],
)
def test_revisions_are_classified_by_what_changed(
    previous: float, revised: float, form: str, expected: RevisionKind
) -> None:
    assert classify_revision(previous, revised, form) is expected


def test_a_change_beyond_the_rounding_unit_is_not_precision() -> None:
    """$53.3m republished as $54m moves by more than the half-million a rounding to millions
    can account for."""
    assert classify_revision(53_263_000.0, 54_000_000.0, "10-K") is RevisionKind.SUBSTANTIVE
