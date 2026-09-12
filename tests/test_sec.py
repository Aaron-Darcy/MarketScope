from __future__ import annotations

import pathlib

import httpx
import pytest
import respx

from marketscope.config import Settings
from marketscope.ingestion.sec import (
    BROWSE_URL,
    COMPANY_FACTS_URL,
    FRAME_URL,
    SecClient,
    _expand_filing_table,
    format_cik,
)


def _sec_client(cache_dir: pathlib.Path) -> SecClient:
    """A client cached into a per-test directory, so no response outlives its test."""
    return SecClient(
        Settings(
            sec_user_agent="MarketScope tests tests@example.com",
            cache_dir=cache_dir,
            max_retries=0,
        )
    )


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


ATOM_PAGE = """<?xml version="1.0" encoding="ISO-8859-1" ?>
  <feed xmlns="http://www.w3.org/2005/Atom">
    <entry title="ARRAY(0x55d34a6269d8)">
      <content type="text/xml">
        <company-info name="ARRAY(0x55d34a6a1850)">
          <cik>{first}</cik>
          <sic>6022</sic>
        </company-info>
      </content>
    </entry>
    <entry title="ARRAY(0x55d34a6b7078)">
      <content type="text/xml">
        <company-info name="ARRAY(0x55d34a6c1130)">
          <cik>{second}</cik>
          <sic>6022</sic>
        </company-info>
      </content>
    </entry>
  </feed>"""


@respx.mock
def test_companies_by_sic_follows_pages_until_one_comes_back_empty(tmp_path: pathlib.Path) -> None:
    route = respx.get(BROWSE_URL).mock(
        side_effect=[
            httpx.Response(200, text=ATOM_PAGE.format(first="0000000019", second="0000000831")),
            httpx.Response(200, text=ATOM_PAGE.format(first="0000000036", second="0000000092")),
            httpx.Response(200, text="<feed></feed>"),
        ]
    )

    with _sec_client(tmp_path) as client:
        assert client.companies_by_sic("6022") == [19, 831, 36, 92]

    assert route.call_count == 3


@respx.mock
def test_companies_by_sic_does_not_repeat_a_cik_seen_on_an_earlier_page(
    tmp_path: pathlib.Path,
) -> None:
    """EDGAR pages by offset, so a filing lodged mid-scan can shift a company onto two
    pages. Returning it twice would double count the SIC population."""
    respx.get(BROWSE_URL).mock(
        side_effect=[
            httpx.Response(200, text=ATOM_PAGE.format(first="0000000019", second="0000000831")),
            httpx.Response(200, text=ATOM_PAGE.format(first="0000000831", second="0000000036")),
            httpx.Response(200, text="<feed></feed>"),
        ]
    )

    with _sec_client(tmp_path) as client:
        assert client.companies_by_sic("6022") == [19, 831, 36]


@respx.mock
def test_frame_maps_each_filer_to_its_reported_value(tmp_path: pathlib.Path) -> None:
    respx.get(
        FRAME_URL.format(taxonomy="us-gaap", tag="Assets", unit="USD", frame="CY2022Q4I")
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"cik": 19617, "entityName": "JPMORGAN CHASE & CO", "val": 3665743000000},
                    {"cik": 70858, "entityName": "BANK OF AMERICA", "val": 3051375000000},
                ]
            },
        )
    )

    with _sec_client(tmp_path) as client:
        assert client.frame("Assets", "CY2022Q4I") == {
            19617: 3665743000000.0,
            70858: 3051375000000.0,
        }


@respx.mock
def test_frame_or_empty_treats_a_missing_concept_period_as_nobody_reporting(
    tmp_path: pathlib.Path,
) -> None:
    """The frames endpoint publishes a document per concept and period, so a 404 while
    sweeping a candidate concept list is an answer rather than a fault."""
    respx.get(
        FRAME_URL.format(
            taxonomy="us-gaap", tag="InterestExpenseDemandDeposits", unit="USD", frame="CY2019"
        )
    ).mock(return_value=httpx.Response(404))

    with _sec_client(tmp_path) as client:
        assert client.frame_or_empty("InterestExpenseDemandDeposits", "CY2019") == {}


@respx.mock
def test_frame_or_empty_still_raises_on_other_client_errors(tmp_path: pathlib.Path) -> None:
    respx.get(FRAME_URL.format(taxonomy="us-gaap", tag="Assets", unit="USD", frame="CY2019")).mock(
        return_value=httpx.Response(403)
    )

    with _sec_client(tmp_path) as client, pytest.raises(httpx.HTTPStatusError):
        client.frame_or_empty("Assets", "CY2019")


@respx.mock
def test_has_company_facts_is_false_for_a_registrant_that_never_filed_in_xbrl(
    tmp_path: pathlib.Path,
) -> None:
    """First Republic Bank is reachable in EDGAR through ownership forms alone and returns
    404 from company facts, which is not the same as absence from EDGAR."""
    respx.get(COMPANY_FACTS_URL.format(cik="CIK0001132979")).mock(return_value=httpx.Response(404))

    with _sec_client(tmp_path) as client:
        assert client.has_company_facts(1132979) is False


@respx.mock
def test_has_company_facts_propagates_a_non_404_failure(tmp_path: pathlib.Path) -> None:
    respx.get(COMPANY_FACTS_URL.format(cik="CIK0000019617")).mock(return_value=httpx.Response(403))

    with _sec_client(tmp_path) as client, pytest.raises(httpx.HTTPStatusError):
        client.has_company_facts(19617)
