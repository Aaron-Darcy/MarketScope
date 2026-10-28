from __future__ import annotations

import pathlib
from collections.abc import Callable, Iterator

import duckdb
import pytest

from marketscope import store
from marketscope.pipeline import LoadReport, load_ffiec

Writer = Callable[..., pathlib.Path]


@pytest.fixture
def connection(tmp_path: pathlib.Path) -> Iterator[duckdb.DuckDBPyConnection]:
    handle = store.connect(tmp_path / "warehouse.duckdb")
    yield handle
    handle.close()


def _count(connection: duckdb.DuckDBPyConnection) -> int:
    row = connection.execute("select count(*) from raw.ffiec_call_items").fetchone()
    return int(row[0]) if row else 0


def test_every_archive_in_the_directory_is_loaded(
    tmp_path: pathlib.Path, bulk_archive: Writer, connection: duckdb.DuckDBPyConnection
) -> None:
    archives = tmp_path / "ffiec"
    archives.mkdir()
    bulk_archive(archives, "09302023")
    bulk_archive(archives, "12312023")
    report = LoadReport()

    load_ffiec(connection, report, archives)

    assert report.ok
    assert report.counts["ffiec_call_items"] == _count(connection) == 2 * 14
    assert connection.execute(
        "select count(distinct report_date) from raw.ffiec_call_items"
    ).fetchone() == (2,)


@pytest.mark.parametrize("make", [True, False])
def test_no_archives_is_a_failure_and_keeps_the_previous_load(
    tmp_path: pathlib.Path,
    bulk_archive: Writer,
    connection: duckdb.DuckDBPyConnection,
    make: bool,
) -> None:
    loaded = tmp_path / "loaded"
    loaded.mkdir()
    bulk_archive(loaded)
    load_ffiec(connection, LoadReport(), loaded)
    empty = tmp_path / "empty"
    if make:
        empty.mkdir()
    report = LoadReport()

    load_ffiec(connection, report, empty)

    assert not report.ok
    assert "no bulk Call Report archives" in report.failures[0]
    assert _count(connection) == 14


def test_a_malformed_archive_fails_and_keeps_the_previous_load(
    tmp_path: pathlib.Path, bulk_archive: Writer, connection: duckdb.DuckDBPyConnection
) -> None:
    archives = tmp_path / "ffiec"
    archives.mkdir()
    bulk_archive(archives, "09302023")
    load_ffiec(connection, LoadReport(), archives)
    bulk_archive(archives, "12312023", omit="RCE")
    report = LoadReport()

    load_ffiec(connection, report, archives)

    assert not report.ok
    assert "RCE" in report.failures[0]
    assert "ffiec_call_items" not in report.counts
    assert _count(connection) == 14
