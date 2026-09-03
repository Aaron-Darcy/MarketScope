from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from marketscope.ingestion.http import JsonApiClient, RateLimiter, ResponseCache

ENDPOINT = "https://example.test/data.json"


class FakeClock:
    """Monotonic clock that advances only when slept against."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_rate_limiter_does_not_delay_the_first_call() -> None:
    clock = FakeClock()
    limiter = RateLimiter(max_per_second=10, clock=clock.time, sleeper=clock.sleep)

    limiter.acquire()

    assert clock.sleeps == []


def test_rate_limiter_spaces_successive_calls() -> None:
    clock = FakeClock()
    limiter = RateLimiter(max_per_second=10, clock=clock.time, sleeper=clock.sleep)

    for _ in range(3):
        limiter.acquire()

    assert clock.sleeps == [pytest.approx(0.1), pytest.approx(0.1)]


def test_rate_limiter_does_not_delay_a_caller_that_is_already_late() -> None:
    clock = FakeClock()
    limiter = RateLimiter(max_per_second=10, clock=clock.time, sleeper=clock.sleep)

    limiter.acquire()
    clock.now += 5.0
    limiter.acquire()

    assert clock.sleeps == []


def test_rate_limiter_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(max_per_second=0)


def test_cache_round_trip(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path, ttl=timedelta(hours=1))
    cache.put(ENDPOINT, {"value": 1})

    assert cache.get(ENDPOINT) == {"value": 1}


def test_cache_returns_none_for_unknown_url(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path, ttl=timedelta(hours=1))

    assert cache.get(ENDPOINT) is None


def test_cache_expires_entries_past_ttl(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path, ttl=timedelta(hours=1))
    cache.put(ENDPOINT, {"value": 1})

    stale = datetime.now(UTC) - timedelta(hours=2)
    entry_path = next(tmp_path.rglob("*.json"))
    entry = json.loads(entry_path.read_text(encoding="utf-8"))
    entry["fetched_at"] = stale.isoformat()
    entry_path.write_text(json.dumps(entry), encoding="utf-8")

    assert cache.get(ENDPOINT) is None


def test_cache_discards_corrupt_entries(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path, ttl=timedelta(hours=1))
    cache.put(ENDPOINT, {"value": 1})

    entry_path = next(tmp_path.rglob("*.json"))
    entry_path.write_text("not json", encoding="utf-8")

    assert cache.get(ENDPOINT) is None
    assert not entry_path.exists()


def _client(cache: ResponseCache | None = None, max_retries: int = 3) -> JsonApiClient:
    return JsonApiClient(
        headers={"User-Agent": "tests contact@example.test"},
        rate_limiter=RateLimiter(max_per_second=1000),
        cache=cache,
        timeout=5.0,
        max_retries=max_retries,
    )


@respx.mock
def test_get_json_returns_payload() -> None:
    respx.get(ENDPOINT).mock(return_value=httpx.Response(200, json={"value": 1}))

    with _client() as client:
        assert client.get_json(ENDPOINT) == {"value": 1}


@respx.mock
def test_get_json_retries_retryable_status_then_succeeds() -> None:
    route = respx.get(ENDPOINT).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"value": 1}),
        ]
    )

    with _client() as client:
        assert client.get_json(ENDPOINT) == {"value": 1}

    assert route.call_count == 2


@respx.mock
def test_get_json_raises_after_exhausting_retries() -> None:
    respx.get(ENDPOINT).mock(return_value=httpx.Response(429))

    with _client(max_retries=1) as client, pytest.raises(httpx.HTTPStatusError):
        client.get_json(ENDPOINT)


@respx.mock
def test_get_json_does_not_retry_client_errors() -> None:
    route = respx.get(ENDPOINT).mock(return_value=httpx.Response(404))

    with _client() as client, pytest.raises(httpx.HTTPStatusError):
        client.get_json(ENDPOINT)

    assert route.call_count == 1


@respx.mock
def test_get_json_serves_second_call_from_cache(tmp_path: Path) -> None:
    route = respx.get(ENDPOINT).mock(return_value=httpx.Response(200, json={"value": 1}))
    cache = ResponseCache(tmp_path, ttl=timedelta(hours=1))

    with _client(cache=cache) as client:
        client.get_json(ENDPOINT)
        client.get_json(ENDPOINT)

    assert route.call_count == 1


@respx.mock
def test_cache_key_includes_query_parameters(tmp_path: Path) -> None:
    route = respx.get(ENDPOINT).mock(return_value=httpx.Response(200, json={"value": 1}))
    cache = ResponseCache(tmp_path, ttl=timedelta(hours=1))

    with _client(cache=cache) as client:
        client.get_json(ENDPOINT, params={"series_id": "FEDFUNDS"})
        client.get_json(ENDPOINT, params={"series_id": "CPIAUCSL"})

    assert route.call_count == 2
