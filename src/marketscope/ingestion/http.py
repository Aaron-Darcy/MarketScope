from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class RateLimiter:
    """Enforces a minimum interval between successive calls across threads.

    The clock and sleep function are injectable so that callers can be tested without
    depending on wall-clock timing, which is not reliable at millisecond resolution on
    every platform.
    """

    def __init__(
        self,
        max_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")
        self._min_interval = 1.0 / max_per_second
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._next_allowed: float | None = None

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            if self._next_allowed is not None and self._next_allowed > now:
                self._sleeper(self._next_allowed - now)
                now = self._clock()
            self._next_allowed = now + self._min_interval


class ResponseCache:
    """Disk cache for JSON API responses, keyed by request URL."""

    def __init__(self, root: Path, ttl: timedelta) -> None:
        self._root = root
        self._ttl = ttl

    def _path_for(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self._root / digest[:2] / f"{digest}.json"

    def get(self, url: str) -> Any | None:
        path = self._path_for(url)
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("Discarding unreadable cache entry at %s", path)
            path.unlink(missing_ok=True)
            return None

        if self._ttl and datetime.now(UTC) - fetched_at > self._ttl:
            return None
        return entry["payload"]

    def put(self, url: str, payload: Any) -> None:
        path = self._path_for(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "url": url,
            "fetched_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(entry), encoding="utf-8")
        temp.replace(path)


class JsonApiClient:
    """HTTP client for JSON endpoints with rate limiting, disk caching and bounded retries."""

    def __init__(
        self,
        *,
        headers: dict[str, str],
        rate_limiter: RateLimiter,
        cache: ResponseCache | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(headers=headers, timeout=timeout, transport=transport)
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._max_retries = max_retries

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self._get(url, params, decode=lambda response: response.json())

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Fetch a non-JSON endpoint through the same rate limiter, cache and retries.

        EDGAR publishes the company browser as Atom rather than JSON, and it is subject to
        the same rate limit as the JSON APIs, so it must not bypass this client.
        """
        payload = self._get(url, params, decode=lambda response: response.text)
        if not isinstance(payload, str):
            raise TypeError(f"Expected a text response from {url}, got {type(payload).__name__}")
        return payload

    def _get(
        self,
        url: str,
        params: dict[str, Any] | None,
        *,
        decode: Callable[[httpx.Response], Any],
    ) -> Any:
        request = self._client.build_request("GET", url, params=params)
        cache_key = str(request.url)

        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for %s", cache_key)
                return cached

        payload = self._fetch_with_retries(cache_key, decode)

        if self._cache is not None:
            self._cache.put(cache_key, payload)
        return payload

    def _fetch_with_retries(self, url: str, decode: Callable[[httpx.Response], Any]) -> Any:
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            if attempt:
                time.sleep(self._backoff_seconds(attempt))

            self._rate_limiter.acquire()

            try:
                response = self._client.get(url)
            except httpx.TransportError as error:
                last_error = error
                logger.warning("Transport error for %s (attempt %d): %s", url, attempt + 1, error)
                continue

            if response.status_code in RETRY_STATUS_CODES:
                last_error = httpx.HTTPStatusError(
                    f"{response.status_code} from {url}",
                    request=response.request,
                    response=response,
                )
                logger.warning(
                    "Retryable status %d for %s (attempt %d)",
                    response.status_code,
                    url,
                    attempt + 1,
                )
                continue

            response.raise_for_status()
            return decode(response)

        assert last_error is not None
        raise last_error

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        return min(2.0**attempt, 30.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JsonApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
