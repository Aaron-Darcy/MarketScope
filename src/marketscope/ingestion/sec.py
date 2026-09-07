from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from marketscope.config import Settings, get_settings
from marketscope.ingestion.http import JsonApiClient, RateLimiter, ResponseCache

DATA_HOST = "https://data.sec.gov"
WWW_HOST = "https://www.sec.gov"

COMPANY_TICKERS_URL = f"{WWW_HOST}/files/company_tickers.json"
COMPANY_FACTS_URL = f"{DATA_HOST}/api/xbrl/companyfacts/{{cik}}.json"
SUBMISSIONS_URL = f"{DATA_HOST}/submissions/{{cik}}.json"
SUBMISSIONS_PAGE_URL = f"{DATA_HOST}/submissions/{{filename}}"


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


def _expand_filing_table(table: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Convert the SEC's column-oriented filing table into rows."""
    if not table:
        return []

    columns = list(table)
    lengths = {len(table[column]) for column in columns}
    if len(lengths) > 1:
        raise ValueError(f"Ragged filing table: column lengths {sorted(lengths)}")

    return [dict(zip(columns, values, strict=True)) for values in zip(*table.values(), strict=True)]
