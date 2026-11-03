from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from marketscope.site_data import SITE_TABLES, ExportError, export

TABLES: dict[str, tuple[str, ...]] = {
    "bank": ("cik",),
    "bank_quarter": ("cik", "quarter_end"),
}

MODELS = Path(__file__).resolve().parents[1] / "transform" / "dbt" / "models"


@pytest.fixture
def warehouse() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("create table bank (cik bigint, rank integer, sic varchar, pinned boolean)")
    connection.execute("insert into bank values (2, 7, '6021', false), (1, null, '6022', true)")
    connection.execute(
        "create table bank_quarter (cik bigint, quarter_end date, cost double, tier varchar)"
    )
    connection.execute(
        "insert into bank_quarter values "
        "(1, '2016-03-31', 0.004, '1'), (1, '2015-12-31', null, 'X'), (2, '2015-12-31', 0.003, '2')"
    )
    return connection


def test_each_table_is_written_with_its_columns_types_and_rows(
    warehouse: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    counts = export(warehouse, tmp_path, TABLES)

    assert counts == {"bank": 2, "bank_quarter": 3}
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "bank.parquet",
        "bank_quarter.parquet",
    ]
    written = warehouse.execute(
        "describe select * from read_parquet(?)", [str(tmp_path / "bank.parquet")]
    ).fetchall()
    assert [column[:2] for column in written] == [
        ("cik", "BIGINT"),
        ("rank", "INTEGER"),
        ("sic", "VARCHAR"),
        ("pinned", "BOOLEAN"),
    ]


def test_rows_are_written_in_key_order(
    warehouse: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    export(warehouse, tmp_path, TABLES)

    rows = warehouse.execute(
        "select cik, quarter_end from read_parquet(?)", [str(tmp_path / "bank_quarter.parquet")]
    ).fetchall()
    assert rows == [(1, date(2015, 12, 31)), (1, date(2016, 3, 31)), (2, date(2015, 12, 31))]


def test_an_unchanged_warehouse_reproduces_the_same_files(
    warehouse: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    export(warehouse, tmp_path, TABLES)
    first = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    export(warehouse, tmp_path, TABLES)

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == first


def test_an_empty_table_stops_the_export_and_keeps_the_previous_files(
    warehouse: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    export(warehouse, tmp_path, TABLES)
    previous = (tmp_path / "bank.parquet").read_bytes()
    warehouse.execute("delete from bank_quarter")
    warehouse.execute("update bank set rank = 1")

    with pytest.raises(ExportError, match="bank_quarter is empty"):
        export(warehouse, tmp_path, TABLES)

    assert (tmp_path / "bank.parquet").read_bytes() == previous
    assert (tmp_path / "bank_quarter.parquet").exists()


def test_a_repeated_key_stops_the_export(
    warehouse: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """Rows sharing a key have no fixed order, so the files would change between runs."""
    warehouse.execute("insert into bank_quarter values (2, '2015-12-31', 0.005, '1')")

    with pytest.raises(ExportError, match="1 rows that repeat a key"):
        export(warehouse, tmp_path, TABLES)


def test_a_table_no_longer_exported_is_removed(
    warehouse: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    (tmp_path / "retired_mart.parquet").write_bytes(b"stale")

    export(warehouse, tmp_path, TABLES)

    assert not (tmp_path / "retired_mart.parquet").exists()


def test_every_exported_table_is_a_dbt_model() -> None:
    models = {path.stem for path in MODELS.rglob("*") if path.suffix in {".sql", ".py"}}

    assert set(SITE_TABLES) <= models
