from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from marketscope.cycles import CycleError, RateCycle, read_policy_rate, read_study_cycles

CALIBRATION = ("calibration", date(2015, 12, 31), date(2019, 3, 31), 0.0016, 0.0240)
TEST = ("test", date(2022, 3, 31), date(2023, 12, 31), 0.0012, 0.0533)
EARLIER = (None, date(2004, 6, 30), date(2007, 3, 31), 0.0101, 0.0526)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    with duckdb.connect(str(tmp_path / "test.duckdb")) as handle:
        handle.execute(
            "create table dim_rate_cycle (cycle_name varchar, start_quarter date, "
            "end_quarter date, start_rate_fraction double, end_rate_fraction double)"
        )
        yield handle


def _load(connection: duckdb.DuckDBPyConnection, *rows: tuple[object, ...]) -> None:
    connection.executemany("insert into dim_rate_cycle values (?, ?, ?, ?, ?)", list(rows))


def test_study_cycles_are_read_in_reporting_order(connection: duckdb.DuckDBPyConnection) -> None:
    _load(connection, TEST, EARLIER, CALIBRATION)

    cycles = read_study_cycles(connection)

    assert list(cycles) == ["calibration", "test"]
    assert cycles["test"].start == date(2022, 3, 31)
    assert cycles["test"].end == date(2023, 12, 31)
    assert cycles["test"].move == pytest.approx(0.0521)


def test_unnamed_earlier_cycles_are_ignored(connection: duckdb.DuckDBPyConnection) -> None:
    _load(connection, CALIBRATION, TEST, EARLIER)

    assert len(read_study_cycles(connection)) == 2


def test_a_missing_study_cycle_fails(connection: duckdb.DuckDBPyConnection) -> None:
    _load(connection, CALIBRATION, EARLIER)

    with pytest.raises(CycleError, match="no test cycle"):
        read_study_cycles(connection)


def test_a_duplicated_study_cycle_fails(connection: duckdb.DuckDBPyConnection) -> None:
    """A plateau at the peak that was not collapsed would name the test cycle twice."""
    plateau = ("test", date(2022, 3, 31), date(2024, 3, 31), 0.0012, 0.0533)
    _load(connection, CALIBRATION, TEST, plateau)

    with pytest.raises(CycleError, match="more than one test"):
        read_study_cycles(connection)


def test_an_unknown_cycle_name_fails(connection: duckdb.DuckDBPyConnection) -> None:
    _load(connection, CALIBRATION, TEST, ("easing", date(2019, 6, 30), date(2020, 6, 30), 0, 0))

    with pytest.raises(CycleError, match="unknown cycle 'easing'"):
        read_study_cycles(connection)


def test_quarters_include_both_bounds_and_cross_year_ends() -> None:
    cycle = RateCycle("test", date(2022, 9, 30), date(2023, 3, 31), 0.0219, 0.0452)

    assert cycle.quarters() == [date(2022, 9, 30), date(2022, 12, 31), date(2023, 3, 31)]


def test_the_calibration_window_spans_fourteen_quarters() -> None:
    cycle = RateCycle(*CALIBRATION)

    assert len(cycle.quarters()) == 14
    assert cycle.covers(date(2019, 3, 31))
    assert not cycle.covers(date(2019, 6, 30))


def test_policy_rate_is_keyed_by_quarter_end(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        "create table int_rate_cycles as select * from (values "
        "(date '2023-09-30', 0.0526::double), (date '2023-12-31', 0.0533::double)"
        ") as t(quarter_end, rate_fraction)"
    )

    assert read_policy_rate(connection) == {date(2023, 9, 30): 0.0526, date(2023, 12, 31): 0.0533}
