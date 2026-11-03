"""Export the tables the site reads from the warehouse to Parquet files committed beside it.

The warehouse is not committed and cannot be rebuilt unattended, since the FFIEC archives
are downloaded by hand, so the site is built from this export rather than from the warehouse
(decision 0044).

Usage:
    python -m marketscope.site_data
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import duckdb

from marketscope import store
from marketscope.store import DATABASE_PATH

SITE_DATA_DIR = Path("data/site")

# Each table with the columns that identify a row. Rows are written in key order, so an
# export of an unchanged warehouse reproduces the same files and a commit of the export
# changes only where a figure did.
SITE_TABLES: dict[str, tuple[str, ...]] = {
    "dim_bank": ("cik",),
    "dim_rate_cycle": ("cycle_key",),
    "bank_entity_events": ("cik", "event_date", "event_type", "counterparty"),
    "fct_bank_quarter": ("cik", "quarter_end"),
    "fct_deposit_beta": ("cik", "cycle_name"),
    "mart_bank_overview": ("cik",),
    "mart_cross_bank_comparison": ("cik",),
    "mart_persistence_result": ("sample",),
    "mart_recovered_beta": ("bank",),
}


class ExportError(Exception):
    """A table cannot be published as the site would read it."""


def _check_table(connection: duckdb.DuckDBPyConnection, table: str, keys: tuple[str, ...]) -> int:
    [(rows, distinct)] = connection.execute(
        f"select count(*), count(distinct ({', '.join(keys)})) from {table}"
    ).fetchall()
    if rows == 0:
        raise ExportError(f"{table} is empty; a page built on it would show nothing")
    if distinct != rows:
        raise ExportError(f"{table} has {rows - distinct} rows that repeat a key {keys}")
    return int(rows)


def _check_file(connection: duckdb.DuckDBPyConnection, table: str, path: Path, rows: int) -> None:
    source = connection.execute(f"describe {table}").fetchall()
    written = connection.execute("describe select * from read_parquet(?)", [str(path)]).fetchall()
    if [column[:2] for column in written] != [column[:2] for column in source]:
        raise ExportError(f"{path.name} does not carry the columns and types of {table}")
    [(counted,)] = connection.execute(
        "select count(*) from read_parquet(?)", [str(path)]
    ).fetchall()
    if counted != rows:
        raise ExportError(f"{path.name} holds a different number of rows from {table}")


def export(
    connection: duckdb.DuckDBPyConnection,
    directory: Path = SITE_DATA_DIR,
    tables: dict[str, tuple[str, ...]] = SITE_TABLES,
) -> dict[str, int]:
    """Write each table to `<table>.parquet` and return the rows written.

    Every file is written and checked before any replaces the published set, so a failure
    leaves the previous export whole rather than half of each. Files for tables no longer
    exported are removed, since the site would otherwise go on reading them.
    """
    directory.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory(dir=directory.parent) as staging:
        for table, keys in tables.items():
            rows = _check_table(connection, table, keys)
            path = Path(staging) / f"{table}.parquet"
            connection.sql(f"select * from {table} order by {', '.join(keys)}").write_parquet(
                str(path)
            )
            _check_file(connection, table, path, rows)
            counts[table] = rows

        for stale in directory.glob("*.parquet"):
            stale.unlink()
        for table in tables:
            shutil.move(Path(staging) / f"{table}.parquet", directory / f"{table}.parquet")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=SITE_DATA_DIR)
    args = parser.parse_args(argv)

    connection = store.connect(args.database, read_only=True)
    try:
        counts = export(connection, args.output_dir)
    finally:
        connection.close()

    print(f"Exported to {args.output_dir}")
    for table, rows in counts.items():
        print(f"  {table:<28} {rows:>8,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
