from __future__ import annotations

import pathlib
from typing import Any

import httpx
import pytest
import respx

from marketscope.config import Settings
from marketscope.ingestion import fdic
from marketscope.ingestion.fdic import FDIC_HOST, FdicClient
from marketscope.regulatory import REFERENCE_MAP, group_filter, mapped_registrants

FINANCIALS_URL = f"{FDIC_HOST}/financials"


def _client(cache_dir: pathlib.Path) -> FdicClient:
    return FdicClient(
        Settings(
            sec_user_agent="MarketScope tests tests@example.com",
            cache_dir=cache_dir,
            max_retries=0,
        )
    )


def _page(*certs: int) -> dict[str, Any]:
    return {"data": [{"data": {"CERT": cert, "DEPI": 1000}} for cert in certs]}


@respx.mock
def test_pages_are_followed_until_one_comes_back_short(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fdic, "PAGE_SIZE", 2)
    route = respx.get(FINANCIALS_URL).mock(
        side_effect=[
            httpx.Response(200, json=_page(1, 2)),
            httpx.Response(200, json=_page(3)),
        ]
    )

    with _client(tmp_path) as client:
        rows = client.financials("RSSDHCR:1039502")

    assert [row["CERT"] for row in rows] == [1, 2, 3]
    assert route.call_count == 2
    assert route.calls[1].request.url.params["offset"] == "2"


@respx.mock
def test_the_filter_and_fields_are_passed_through(tmp_path: pathlib.Path) -> None:
    route = respx.get(FINANCIALS_URL).mock(return_value=httpx.Response(200, json=_page()))

    with _client(tmp_path) as client:
        assert client.financials("CERT:2270", fields=("CERT", "DEPI")) == []

    params = route.calls[0].request.url.params
    assert params["filters"] == "CERT:2270"
    assert params["fields"] == "CERT,DEPI"


@respx.mock
def test_a_failed_request_raises_rather_than_returning_a_partial_load(
    tmp_path: pathlib.Path,
) -> None:
    respx.get(FINANCIALS_URL).mock(return_value=httpx.Response(400))

    with _client(tmp_path) as client, pytest.raises(httpx.HTTPStatusError):
        client.financials("RSSDHCR:1039502")


def test_a_holder_key_selects_on_the_regulatory_high_holder() -> None:
    assert group_filter("HC:1039502") == "RSSDHCR:1039502"


def test_an_institution_key_selects_on_its_certificate() -> None:
    """Zions dissolved its holding company in 2018, so the FDIC records no holder for it."""
    assert group_filter("BANK:2270") == "CERT:2270"


def test_an_unrecognised_key_is_refused() -> None:
    with pytest.raises(ValueError, match="Unrecognised"):
        group_filter("RSSD:1039502")


def test_only_groups_reachable_through_edgar_map_to_a_registrant() -> None:
    mapped = mapped_registrants()

    assert mapped["HC:1039502"] == 19617
    assert "BANK:59017" not in mapped
    assert len(mapped) == sum(1 for mapping in REFERENCE_MAP.values() if mapping.cik)
