from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from marketscope.config import Settings, get_settings
from marketscope.ingestion.http import JsonApiClient, RateLimiter, ResponseCache

OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES_URL = "https://api.stlouisfed.org/fred/series"

MISSING_VALUE = "."


class Observation(BaseModel):
    observation_date: date
    value: float | None


class FredClient:
    """Client for the Federal Reserve Economic Data API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.fred_api_key:
            raise ValueError("MARKETSCOPE_FRED_API_KEY is not set")

        cache = ResponseCache(
            root=self._settings.cache_dir / "fred",
            ttl=timedelta(hours=self._settings.cache_ttl_hours),
        )
        self._client = JsonApiClient(
            headers={"Accept": "application/json"},
            rate_limiter=RateLimiter(self._settings.fred_requests_per_second),
            cache=cache,
            timeout=self._settings.request_timeout_seconds,
            max_retries=self._settings.max_retries,
        )
        self._api_key = self._settings.fred_api_key

    def series_metadata(self, series_id: str) -> dict[str, Any]:
        payload = self._client.get_json(
            SERIES_URL,
            params={"series_id": series_id, "api_key": self._api_key, "file_type": "json"},
        )
        seriess: list[dict[str, Any]] = payload["seriess"]
        if not seriess:
            raise KeyError(f"FRED returned no metadata for series {series_id}")
        return seriess[0]

    def observations(
        self,
        series_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[Observation]:
        """Return a series as observations, with FRED's missing-value marker resolved to None.

        FRED encodes a missing observation as a single full stop rather than null, which
        silently becomes a string if the payload is loaded without conversion.
        """
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
        }
        if start is not None:
            params["observation_start"] = start.isoformat()
        if end is not None:
            params["observation_end"] = end.isoformat()

        payload = self._client.get_json(OBSERVATIONS_URL, params=params)

        return [
            Observation(
                observation_date=date.fromisoformat(row["date"]),
                value=None if row["value"] == MISSING_VALUE else float(row["value"]),
            )
            for row in payload["observations"]
        ]

    def close(self) -> None:
        self._client.close()
