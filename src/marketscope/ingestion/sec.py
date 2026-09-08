from __future__ import annotations

import re
from datetime import timedelta
from types import TracebackType
from typing import Any

import httpx

from marketscope.config import Settings, get_settings
from marketscope.ingestion.http import JsonApiClient, RateLimiter, ResponseCache

DATA_HOST = "https://data.sec.gov"
WWW_HOST = "https://www.sec.gov"

COMPANY_TICKERS_URL = f"{WWW_HOST}/files/company_tickers.json"
COMPANY_FACTS_URL = f"{DATA_HOST}/api/xbrl/companyfacts/{{cik}}.json"
SUBMISSIONS_URL = f"{DATA_HOST}/submissions/{{cik}}.json"
SUBMISSIONS_PAGE_URL = f"{DATA_HOST}/submissions/{{filename}}"
FRAME_URL = f"{DATA_HOST}/api/xbrl/frames/{{taxonomy}}/{{tag}}/{{unit}}/{{frame}}.json"
BROWSE_URL = f"{WWW_HOST}/cgi-bin/browse-edgar"

BROWSE_PAGE_SIZE = 100
BROWSE_MAX_PAGES = 200

_CIK_PATTERN = re.compile(r"<cik>(\d+)</cik>")


def format_cik(cik: int | str) -> str:
    """Return a CIK in the zero-padded form the SEC APIs expect."""
    digits = str(cik).lstrip("CIK").lstrip("cik").strip()
    if not digits.isdigit():
        raise ValueError(f"Not a valid CIK: {cik!r}")
    return f"CIK{int(digits):010d}"


def normalise_entity_name(name: str) -> str:
    """Collapse the irregular whitespace and casing EDGAR uses in registrant names."""
    return re.sub(r"\s+", " ", name).strip().upper()


class SecClient:
    """Client for the SEC EDGAR submissions and XBRL company facts APIs.

    The SEC requires a User-Agent carrying contact details and limits callers to ten
    requests per second. Both constraints are applied here rather than at the call site.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        cache = ResponseCache(
            root=self._settings.cache_dir / "sec",
            ttl=timedelta(hours=self._settings.cache_ttl_hours),
        )
        self._client = JsonApiClient(
            headers={
                "User-Agent": self._settings.sec_user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            },
            rate_limiter=RateLimiter(self._settings.sec_requests_per_second),
            cache=cache,
            timeout=self._settings.request_timeout_seconds,
            max_retries=self._settings.max_retries,
        )

    def company_tickers(self) -> list[dict[str, Any]]:
        """Return the full CIK to ticker mapping published by the SEC."""
        payload = self._client.get_json(COMPANY_TICKERS_URL)
        return [
            {
                "cik": int(row["cik_str"]),
                "ticker": row["ticker"],
                "title": row["title"],
            }
            for row in payload.values()
        ]

    def companies_by_sic(self, sic: str) -> list[int]:
        """Return the CIK of every EDGAR entity carrying an SIC code.

        Reads the company browser rather than a bulk file because no bulk file publishes
        SIC. The Atom rendering is used for its stable markup, but its company-name field
        is unusable — EDGAR emits a serialised Perl reference such as ``ARRAY(0x55d3...)``
        rather than the name — so only the CIK is taken and names are resolved from the
        submissions endpoint.
        """
        ciks: list[int] = []
        seen: set[int] = set()

        for page in range(BROWSE_MAX_PAGES):
            payload = self._client.get_text(
                BROWSE_URL,
                params={
                    "action": "getcompany",
                    "SIC": sic,
                    "dateb": "",
                    "owner": "include",
                    "count": str(BROWSE_PAGE_SIZE),
                    "start": str(page * BROWSE_PAGE_SIZE),
                    "output": "atom",
                },
            )
            found = [int(match) for match in _CIK_PATTERN.findall(payload)]
            if not found:
                return ciks
            for cik in found:
                if cik not in seen:
                    seen.add(cik)
                    ciks.append(cik)

        raise RuntimeError(f"SIC {sic} exceeded {BROWSE_MAX_PAGES} pages of company results")

    def frame_payload(
        self, tag: str, frame: str, *, taxonomy: str = "us-gaap", unit: str = "USD"
    ) -> dict[str, Any]:
        """Return the raw frame payload, including the entity name on each observation.

        The frames endpoint answers cross-filer questions in a single request that would
        otherwise cost one company facts download per filer. It reports only filers whose
        period aligns to the frame, so a filer with a non-calendar fiscal year is absent
        from the calendar frame rather than reported at zero.
        """
        url = FRAME_URL.format(taxonomy=taxonomy, tag=tag, unit=unit, frame=frame)
        payload: dict[str, Any] = self._client.get_json(url)
        return payload

    def frame(
        self, tag: str, frame: str, *, taxonomy: str = "us-gaap", unit: str = "USD"
    ) -> dict[int, float]:
        """Return one concept's value for every filer reporting it in a period."""
        payload = self.frame_payload(tag, frame, taxonomy=taxonomy, unit=unit)
        return {int(row["cik"]): float(row["val"]) for row in payload.get("data", [])}

    def frame_or_empty(
        self, tag: str, frame: str, *, taxonomy: str = "us-gaap", unit: str = "USD"
    ) -> dict[int, float]:
        """Return a frame, treating 404 as nobody having reported the concept in the period.

        The frames endpoint publishes a document per concept and period and returns 404
        where none exists. That is an ordinary answer when sweeping a candidate concept
        list across years, not a fault, so it is distinguished here from the other error
        statuses, which still raise.
        """
        try:
            return self.frame(tag, frame, taxonomy=taxonomy, unit=unit)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return {}
            raise

    def company_facts(self, cik: int | str) -> dict[str, Any]:
        """Return every XBRL fact the SEC holds for a filer."""
        url = COMPANY_FACTS_URL.format(cik=format_cik(cik))
        payload: dict[str, Any] = self._client.get_json(url)
        return payload

    def submissions(self, cik: int | str) -> dict[str, Any]:
        """Return filer metadata and recent filing history."""
        url = SUBMISSIONS_URL.format(cik=format_cik(cik))
        payload: dict[str, Any] = self._client.get_json(url)
        return payload

    def has_company_facts(self, cik: int | str) -> bool:
        """Report whether the SEC holds any XBRL facts for a filer.

        A registrant that has never filed a financial statement in XBRL returns 404 from
        the company facts endpoint. That is the signature of an institution reachable in
        EDGAR only through ownership forms, which is not the same as absence from EDGAR
        and is distinguished from it in universe construction.
        """
        try:
            self.company_facts(cik)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return False
            raise
        return True

    def entity_name(self, cik: int | str) -> str:
        """Return the registrant name for a CIK, normalised.

        Taken from the submissions endpoint rather than the entityName field on company
        facts. That field can carry a co-filing subsidiary instead of the registrant:
        CIK 70858 is Bank of America Corporation, but its company facts payload reports
        BofA Finance LLC, a financing subsidiary that files under the same CIK.
        """
        return normalise_entity_name(str(self.submissions(cik).get("name", "")))

    def filing_history(self, cik: int | str) -> list[dict[str, Any]]:
        """Return the complete filing history, following the SEC's older-filing pages.

        The submissions endpoint holds only the most recent filings inline; anything
        beyond that is split across supplementary files listed under ``filings.files``.
        Large filers exceed the inline window well within the period this project covers,
        so the supplementary pages must be followed rather than assumed empty.
        """
        payload = self.submissions(cik)
        filings = payload.get("filings", {})

        rows = _expand_filing_table(filings.get("recent", {}))

        for page in filings.get("files", []):
            page_payload = self._client.get_json(SUBMISSIONS_PAGE_URL.format(filename=page["name"]))
            rows.extend(_expand_filing_table(page_payload))

        return rows

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SecClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _expand_filing_table(table: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Convert the SEC's column-oriented filing table into rows."""
    if not table:
        return []

    columns = list(table)
    lengths = {len(table[column]) for column in columns}
    if len(lengths) > 1:
        raise ValueError(f"Ragged filing table: column lengths {sorted(lengths)}")

    return [dict(zip(columns, values, strict=True)) for values in zip(*table.values(), strict=True)]
