from __future__ import annotations

import pytest

from marketscope.ingestion.sec import _expand_filing_table, format_cik


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (19617, "CIK0000019617"),
        ("19617", "CIK0000019617"),
        ("0000019617", "CIK0000019617"),
        ("CIK0000019617", "CIK0000019617"),
    ],
)
def test_format_cik(value: int | str, expected: str) -> None:
    assert format_cik(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "CIK", "12a34"])
def test_format_cik_rejects_invalid_input(value: str) -> None:
    with pytest.raises(ValueError):
        format_cik(value)


def test_expand_filing_table_produces_rows() -> None:
    table = {
        "accessionNumber": ["0000019617-23-000001", "0000019617-23-000002"],
        "form": ["10-K", "10-Q"],
        "reportDate": ["2022-12-31", "2023-03-31"],
    }

    assert _expand_filing_table(table) == [
        {
            "accessionNumber": "0000019617-23-000001",
            "form": "10-K",
            "reportDate": "2022-12-31",
        },
        {
            "accessionNumber": "0000019617-23-000002",
            "form": "10-Q",
            "reportDate": "2023-03-31",
        },
    ]


def test_expand_filing_table_handles_empty_table() -> None:
    assert _expand_filing_table({}) == []


def test_expand_filing_table_rejects_ragged_columns() -> None:
    table = {"form": ["10-K", "10-Q"], "reportDate": ["2022-12-31"]}

    with pytest.raises(ValueError, match="Ragged filing table"):
        _expand_filing_table(table)
