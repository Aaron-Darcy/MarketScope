from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from marketscope import store
from marketscope.facts import Fact
from marketscope.ingestion.fred import Observation
from marketscope.universe import SeedRow


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    with store.connect(tmp_path / "test.duckdb") as handle:
        yield handle


def _fact(tag: str = "Deposits", value: float = 1.0) -> Fact:
    return Fact(
        taxonomy="us-gaap",
        tag=tag,
        unit="USD",
        value=value,
        period_start=None,
        period_end=date(2022, 12, 31),
        filed=date(2023, 2, 21),
        accession="0000019617-23-000001",
        form="10-K",
        fiscal_year=2022,
        fiscal_period="FY",
    )


def test_connect_creates_the_raw_tables(connection: duckdb.DuckDBPyConnection) -> None:
    assert set(store.table_counts(connection)) == {
        "universe",
        "sec_facts",
        "sec_filings",
        "sec_registrants",
        "fred_observations",
        "ingest_log",
    }


def test_replace_loads_rows(connection: duckdb.DuckDBPyConnection) -> None:
    rows = store.fact_rows(19617, [_fact(), _fact("Assets", 2.0)])

    assert store.replace(connection, "sec_facts", store.FACT_COLUMNS, rows) == 2
    assert store.table_counts(connection)["sec_facts"] == 2


def test_replace_is_idempotent(connection: duckdb.DuckDBPyConnection) -> None:
    """A rerun must leave the same rows, not twice as many. The company facts endpoint
    restates history in place, so the raw table is replaced rather than accumulated into."""
    rows = store.fact_rows(19617, [_fact()])

    store.replace(connection, "sec_facts", store.FACT_COLUMNS, rows)
    store.replace(connection, "sec_facts", store.FACT_COLUMNS, rows)

    assert store.table_counts(connection)["sec_facts"] == 1


def test_replace_records_one_log_entry_per_source(connection: duckdb.DuckDBPyConnection) -> None:
    store.replace(connection, "sec_facts", store.FACT_COLUMNS, store.fact_rows(1, [_fact()]))
    store.replace(connection, "sec_facts", store.FACT_COLUMNS, store.fact_rows(1, []))

    logged = connection.execute(
        "SELECT source, rows FROM raw.ingest_log ORDER BY source"
    ).fetchall()

    assert logged == [("sec_facts", 0)]


def test_replace_leaves_the_table_untouched_when_a_row_is_bad(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """A load that fails halfway must not leave a partially replaced table behind, which
    would read as a coverage collapse rather than as a failed run."""
    store.replace(connection, "sec_facts", store.FACT_COLUMNS, store.fact_rows(1, [_fact()]))

    bad = [(1, "us-gaap", "Deposits", "USD", None, None, None, None, None, None, None, None, None)]
    with pytest.raises(duckdb.Error):
        store.replace(connection, "sec_facts", store.FACT_COLUMNS, bad)

    assert store.table_counts(connection)["sec_facts"] == 1


def test_filing_rows_keeps_an_empty_report_date_null() -> None:
    """An empty string in a DATE column becomes an epoch date, which reads as a filing
    lodged in 1970 rather than as one with no period."""
    rows = store.filing_rows(19617, [{"form": "8-K", "filingDate": "2023-03-10", "reportDate": ""}])

    assert rows[0][4] is None
    assert rows[0][3] == "2023-03-10"


def test_registrant_row_flattens_tickers_and_exchanges() -> None:
    row = store.registrant_row(
        19617,
        {
            "name": "JPMORGAN CHASE & CO",
            "sic": "6021",
            "tickers": ["JPM", "JPM-PC"],
            "exchanges": ["NYSE"],
        },
    )

    assert row[1] == "JPMORGAN CHASE & CO"
    assert row[7] == "JPM|JPM-PC"
    assert row[8] == "NYSE"


def test_registrant_row_leaves_an_absent_sic_null() -> None:
    """First Republic's EDGAR record carries no SIC at all."""
    assert store.registrant_row(1132979, {"name": "FIRST REPUBLIC BANK"})[2] is None


def test_fred_rows_preserve_a_missing_observation() -> None:
    rows = store.fred_rows(
        "DGS10",
        [
            Observation(observation_date=date(2023, 1, 2), value=None),
            Observation(observation_date=date(2023, 1, 3), value=3.79),
        ],
    )

    assert rows == [("DGS10", date(2023, 1, 2), None), ("DGS10", date(2023, 1, 3), 3.79)]


def test_universe_rows_carry_an_unranked_pin(connection: duckdb.DuckDBPyConnection) -> None:
    seed = [
        SeedRow(cik=19617, registrant_name="JPMORGAN", rank=1, pinned=False, pinned_reason=""),
        SeedRow(
            cik=1102112, registrant_name="PACWEST", rank=None, pinned=True, pinned_reason="terminal"
        ),
    ]

    store.replace(connection, "universe", store.UNIVERSE_COLUMNS, store.universe_rows(seed))

    assert connection.execute(
        "SELECT cik, rank, pinned FROM raw.universe ORDER BY cik"
    ).fetchall() == [(19617, 1, False), (1102112, None, True)]


def test_replacing_many_rolls_every_table_back_together(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """Facts, filings and registrants come from the same responses, so a half-succeeded run
    must not leave them describing different sets of filers."""
    store.replace(connection, "sec_facts", store.FACT_COLUMNS, store.fact_rows(1, [_fact()]))
    store.replace(
        connection, "sec_registrants", store.REGISTRANT_COLUMNS, [store.registrant_row(1, {})]
    )

    tables = {"sec_facts": store.FACT_COLUMNS, "sec_registrants": store.REGISTRANT_COLUMNS}
    with (
        pytest.raises(RuntimeError, match="fetch failed"),
        store.replacing_many(connection, tables) as appenders,
    ):
        appenders["sec_facts"].append(store.fact_rows(2, [_fact(), _fact()]))
        raise RuntimeError("fetch failed")

    counts = store.table_counts(connection)
    assert counts["sec_facts"] == 1
    assert counts["sec_registrants"] == 1


def test_appender_counts_rows_across_several_batches(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    """The final partial batch is only flushed when the context exits, so a count read
    inside it would fall short of what was loaded."""
    rows = store.fact_rows(1, [_fact() for _ in range(3)])

    with store.replacing(connection, "sec_facts", store.FACT_COLUMNS, batch_size=2) as appender:
        appender.append(rows[:2])
        assert appender.rows == 2
        appender.append(rows[2:])
        assert appender.rows == 2

    assert appender.rows == 3
    assert store.table_counts(connection)["sec_facts"] == 3
