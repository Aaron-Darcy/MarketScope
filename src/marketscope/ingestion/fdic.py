from __future__ import annotations

from datetime import timedelta
from types import TracebackType
from typing import Any

from marketscope.config import Settings, get_settings
from marketscope.ingestion.http import JsonApiClient, RateLimiter, ResponseCache

FDIC_HOST = "https://api.fdic.gov/banks"
PAGE_SIZE = 10_000

# Call Report balances and flows are published in thousands of dollars.
THOUSANDS = 1_000.0

# Deposit concepts per insured institution and quarter. The quarterly expense fields are the
# FDIC's own differencing of the year-to-date Call Report figures, so no fourth quarter has
# to be derived on this side. DEPI is interest-bearing deposits in domestic and foreign
# offices together, the base the XBRL metric divides by. DEPIDOM and DEPIFOR split it by
# office, matching the split of the expense, so a cost can be read for each office alone.
DEPOSIT_FIELDS: tuple[str, ...] = (
    "CERT",
    "REPDTE",
    "RSSDHCR",
    "DEP",
    "DEPI",
    "DEPNI",
    "DEPIDOM",
    "DEPIFOR",
    "EDEPDOMQ",
    "EDEPFORQ",
)


class FdicClient:
    """Client for the FDIC BankFind Suite API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = JsonApiClient(
            # The FDIC asks for no key; the SEC contact string identifies the caller.
            headers={"User-Agent": self._settings.sec_user_agent, "Accept": "application/json"},
            rate_limiter=RateLimiter(self._settings.fred_requests_per_second),
            cache=ResponseCache(
                root=self._settings.cache_dir / "fdic",
                ttl=timedelta(hours=self._settings.cache_ttl_hours),
            ),
            timeout=self._settings.request_timeout_seconds,
            max_retries=self._settings.max_retries,
        )

    def fetch_all(self, path: str, fields: str, filters: str = "") -> list[dict[str, Any]]:
        """Page through a collection until a page comes back short or empty."""
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            params: dict[str, Any] = {
                "fields": fields,
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
                "format": "json",
            }
            if filters:
                params["filters"] = filters
            payload = self._client.get_json(f"{FDIC_HOST}/{path}", params=params)
            batch = [row["data"] for row in payload.get("data", [])]
            rows.extend(batch)
            offset += len(batch)
            if len(batch) < PAGE_SIZE:
                return rows

    def financials(
        self, filters: str, fields: tuple[str, ...] = DEPOSIT_FIELDS
    ) -> list[dict[str, Any]]:
        return self.fetch_all("financials", ",".join(fields), filters)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FdicClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
