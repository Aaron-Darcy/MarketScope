from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow

from marketscope.facts import Fact
from marketscope.ingestion.fred import Observation
from marketscope.universe import SeedRow

DATABASE_PATH = Path("data/marketscope.duckdb")

RAW_SCHEMA = "raw"

# Rows buffered before a bulk insert. Large enough that the two million facts the universe
# produces go in a handful of scans, small enough that a batch is not held in memory long.
DEFAULT_BATCH_SIZE = 200_000

# Raw tables mirror what each endpoint returns, converted to types and nothing else. Every
# harmonisation decision belongs in the transformation layer where dbt can test it, so a
# defect there is fixed by rerunning models rather than by refetching the SEC.
DDL: tuple[str, ...] = (
    f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}",
    f"""CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.universe (
        cik BIGINT NOT NULL,
        registrant_name VARCHAR NOT NULL,
        rank INTEGER,
        pinned BOOLEAN NOT NULL,
        pinned_reason VARCHAR NOT NULL
    )""",
    f"""CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.sec_facts (
        cik BIGINT NOT NULL,
        taxonomy VARCHAR NOT NULL,
        tag VARCHAR NOT NULL,
        unit VARCHAR NOT NULL,
        value DOUBLE NOT NULL,
        period_start DATE,
        period_end DATE NOT NULL,
        filed DATE NOT NULL,
        accession VARCHAR,
        form VARCHAR,
        fiscal_year INTEGER,
        fiscal_period VARCHAR,
        frame VARCHAR
    )""",
    f"""CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.sec_filings (
        cik BIGINT NOT NULL,
        accession_number VARCHAR,
        form VARCHAR,
        filing_date DATE,
        report_date DATE,
        acceptance_datetime VARCHAR,
        primary_document VARCHAR,
        is_xbrl BOOLEAN,
        size BIGINT
    )""",
    f"""CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.sec_registrants (
        cik BIGINT NOT NULL,
        registrant_name VARCHAR NOT NULL,
        sic VARCHAR,
        sic_description VARCHAR,
        entity_type VARCHAR,
        state_of_incorporation VARCHAR,
        fiscal_year_end VARCHAR,
        tickers VARCHAR,
        exchanges VARCHAR
    )""",
    f"""CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.fred_observations (
        series_id VARCHAR NOT NULL,
        observation_date DATE NOT NULL,
        value DOUBLE
    )""",
    f"""CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.ingest_log (
        source VARCHAR NOT NULL,
        loaded_at TIMESTAMPTZ NOT NULL,
        rows BIGINT NOT NULL
    )""",
)


def connect(path: Path = DATABASE_PATH, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse, creating the raw schema if it is not there yet."""
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        for statement in DDL:
            connection.execute(statement)
    return connection


class Appender:
    """Buffers rows and flushes them to DuckDB in bulk.

    Row-at-a-time inserts do not scale to the two million facts the universe produces.
    Rows are staged through an Arrow table instead, which DuckDB reads columnar and
    inserts in one scan.
    """

    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        table: str,
        columns: Sequence[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._connection = connection
        self._table = table
        self._columns = tuple(columns)
        self._batch_size = batch_size
        self._buffer: list[tuple[Any, ...]] = []
        self.rows = 0

    def append(self, rows: Sequence[tuple[Any, ...]]) -> None:
        self._buffer.extend(rows)
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return

        batch = pyarrow.table(
            {
                column: [row[index] for row in self._buffer]
                for index, column in enumerate(self._columns)
            }
        )
        self._connection.register("_append_batch", batch)
        try:
            self._connection.execute(
                f"INSERT INTO {self._table} ({', '.join(self._columns)}) "
                f"SELECT * FROM _append_batch"
            )
        finally:
            self._connection.unregister("_append_batch")

        self.rows += len(self._buffer)
        self._buffer.clear()


@contextmanager
def replacing_many(
    connection: duckdb.DuckDBPyConnection,
    tables: Mapping[str, Sequence[str]],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Iterator[dict[str, Appender]]:
    """Replace several raw tables together, streaming rows in rather than holding them all.

    A full replace rather than an upsert, because the company facts endpoint restates
    history in place: a filer that revises a 2019 figure republishes the whole series, and
    merging on a key would leave the superseded value behind as though it were current.
    Restatement across runs is captured by snapshotting these tables, not by accumulating
    into them.

    One transaction spans every table, because facts, filings and registrants are loaded
    from the same responses and a run that half-succeeded would leave them describing
    different sets of filers. DuckDB has no nested transactions, so the tables must be
    opened together rather than one context inside another.
    """
    appenders = {
        table: Appender(connection, f"{RAW_SCHEMA}.{table}", columns, batch_size)
        for table, columns in tables.items()
    }

    connection.execute("BEGIN TRANSACTION")
    try:
        for table in tables:
            connection.execute(f"DELETE FROM {RAW_SCHEMA}.{table}")

        yield appenders

        for table, appender in appenders.items():
            appender.flush()
            connection.execute(f"DELETE FROM {RAW_SCHEMA}.ingest_log WHERE source = ?", [table])
            connection.execute(
                f"INSERT INTO {RAW_SCHEMA}.ingest_log (source, loaded_at, rows) VALUES (?, ?, ?)",
                [table, datetime.now(UTC), appender.rows],
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


@contextmanager
def replacing(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    columns: Sequence[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Iterator[Appender]:
    """Replace one raw table's contents."""
    with replacing_many(connection, {table: columns}, batch_size) as appenders:
        yield appenders[table]


def replace(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    columns: Sequence[str],
    rows: Sequence[tuple[Any, ...]],
) -> int:
    """Replace a raw table with a set of rows already in memory."""
    with replacing(connection, table, columns) as appender:
        appender.append(rows)
    return len(rows)


UNIVERSE_COLUMNS = ("cik", "registrant_name", "rank", "pinned", "pinned_reason")
FACT_COLUMNS = (
    "cik",
    "taxonomy",
    "tag",
    "unit",
    "value",
    "period_start",
    "period_end",
    "filed",
    "accession",
    "form",
    "fiscal_year",
    "fiscal_period",
    "frame",
)
FILING_COLUMNS = (
    "cik",
    "accession_number",
    "form",
    "filing_date",
    "report_date",
    "acceptance_datetime",
    "primary_document",
    "is_xbrl",
    "size",
)
REGISTRANT_COLUMNS = (
    "cik",
    "registrant_name",
    "sic",
    "sic_description",
    "entity_type",
    "state_of_incorporation",
    "fiscal_year_end",
    "tickers",
    "exchanges",
)
FRED_COLUMNS = ("series_id", "observation_date", "value")


def universe_rows(seed: Iterable[SeedRow]) -> list[tuple[Any, ...]]:
    return [(row.cik, row.registrant_name, row.rank, row.pinned, row.pinned_reason) for row in seed]


def fact_rows(cik: int, facts: Iterable[Fact]) -> list[tuple[Any, ...]]:
    return [
        (
            cik,
            fact.taxonomy,
            fact.tag,
            fact.unit,
            fact.value,
            fact.period_start,
            fact.period_end,
            fact.filed,
            fact.accession,
            fact.form,
            fact.fiscal_year,
            fact.fiscal_period,
            fact.frame,
        )
        for fact in facts
    ]


def _as_date(value: Any) -> str | None:
    """Keep an empty date string out of a DATE column rather than letting it become 1970."""
    text = str(value or "").strip()
    return text or None


def filing_rows(cik: int, filings: Iterable[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            cik,
            filing.get("accessionNumber"),
            filing.get("form"),
            _as_date(filing.get("filingDate")),
            _as_date(filing.get("reportDate")),
            filing.get("acceptanceDateTime"),
            filing.get("primaryDocument"),
            bool(filing.get("isXBRL")),
            filing.get("size"),
        )
        for filing in filings
    ]


def registrant_row(cik: int, submissions: dict[str, Any]) -> tuple[Any, ...]:
    return (
        cik,
        str(submissions.get("name", "")),
        str(submissions.get("sic", "")) or None,
        str(submissions.get("sicDescription", "")) or None,
        str(submissions.get("entityType", "")) or None,
        str(submissions.get("stateOfIncorporation", "")) or None,
        str(submissions.get("fiscalYearEnd", "")) or None,
        "|".join(submissions.get("tickers", [])),
        "|".join(submissions.get("exchanges", [])),
    )


def fred_rows(series_id: str, observations: Iterable[Observation]) -> list[tuple[Any, ...]]:
    return [
        (series_id, observation.observation_date, observation.value) for observation in observations
    ]


def table_counts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Row count per raw table, for the change detection the specification asks for."""
    tables = connection.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = ? ORDER BY table_name",
        [RAW_SCHEMA],
    ).fetchall()

    counts: dict[str, int] = {}
    for (name,) in tables:
        result = connection.execute(f"SELECT count(*) FROM {RAW_SCHEMA}.{name}").fetchone()
        counts[str(name)] = int(result[0]) if result else 0
    return counts


def read_facts(
    connection: duckdb.DuckDBPyConnection,
    cik: int,
    tags: Iterable[str] | None = None,
) -> list[Fact]:
    """Rebuild a filer's facts from the warehouse.

    Returns the same shape the SEC client produces, so panel construction and the metric
    are indifferent to whether a fact arrived from the API or from a previous load.
    """
    query = f"""
        select taxonomy, tag, unit, value, period_start, period_end, filed,
               accession, form, fiscal_year, fiscal_period, frame
        from {RAW_SCHEMA}.sec_facts
        where cik = ?
    """
    parameters: list[Any] = [cik]

    wanted = None if tags is None else sorted(set(tags))
    if wanted is not None:
        query += f" and tag in ({', '.join('?' for _ in wanted)})"
        parameters.extend(wanted)

    return [
        Fact(
            taxonomy=row[0],
            tag=row[1],
            unit=row[2],
            value=row[3],
            period_start=row[4],
            period_end=row[5],
            filed=row[6],
            accession=row[7],
            form=row[8],
            fiscal_year=row[9],
            fiscal_period=row[10],
            frame=row[11],
        )
        for row in connection.execute(query, parameters).fetchall()
    ]


def read_universe(connection: duckdb.DuckDBPyConnection) -> list[SeedRow]:
    """Read the loaded universe back, ranked members first and pins after."""
    rows = connection.execute(
        f"select cik, registrant_name, rank, pinned, pinned_reason "
        f"from {RAW_SCHEMA}.universe order by rank nulls last, cik"
    ).fetchall()

    return [
        SeedRow(
            cik=int(row[0]),
            registrant_name=str(row[1]),
            rank=None if row[2] is None else int(row[2]),
            pinned=bool(row[3]),
            pinned_reason=str(row[4]),
        )
        for row in rows
    ]
