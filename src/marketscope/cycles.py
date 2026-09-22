from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import duckdb

from marketscope.panel import quarter_end

# Named by recency in dim_rate_cycle, so these follow the rate series forward. Order is the
# order the analysis reports them in.
STUDY_CYCLES: tuple[str, ...] = ("calibration", "test")


class CycleError(Exception):
    """The warehouse does not define the study cycles the analysis requires."""


@dataclass(frozen=True)
class RateCycle:
    name: str
    start: date
    end: date
    start_rate: float
    end_rate: float

    @property
    def move(self) -> float:
        return self.end_rate - self.start_rate

    def covers(self, quarter: date) -> bool:
        return self.start <= quarter <= self.end

    def quarters(self) -> list[date]:
        """Every quarter end in the cycle, inclusive of both bounds."""
        quarters: list[date] = []
        current = self.start
        while current <= self.end:
            quarters.append(current)
            current = quarter_end(current + timedelta(days=1))
        return quarters


def read_study_cycles(connection: duckdb.DuckDBPyConnection) -> dict[str, RateCycle]:
    """Read the calibration and test cycles from `dim_rate_cycle`, in reporting order.

    dbt tests the same conditions, but a script can be run against a warehouse whose tests
    were not, and a window read wrongly here moves every coverage count and beta after it.
    """
    rows = connection.execute(
        "select cycle_name, start_quarter, end_quarter, start_rate_fraction, "
        "end_rate_fraction from dim_rate_cycle where cycle_name is not null"
    ).fetchall()

    cycles: dict[str, RateCycle] = {}
    for name, start, end, start_rate, end_rate in rows:
        if name not in STUDY_CYCLES:
            raise CycleError(f"dim_rate_cycle names an unknown cycle {name!r}")
        if name in cycles:
            raise CycleError(f"dim_rate_cycle names more than one {name} cycle")
        cycles[name] = RateCycle(
            name=name, start=start, end=end, start_rate=start_rate, end_rate=end_rate
        )

    missing = [name for name in STUDY_CYCLES if name not in cycles]
    if missing:
        raise CycleError(f"dim_rate_cycle defines no {' or '.join(missing)} cycle")

    return {name: cycles[name] for name in STUDY_CYCLES}


def read_policy_rate(connection: duckdb.DuckDBPyConnection) -> dict[date, float]:
    """Quarter-averaged federal funds rate as a decimal fraction, keyed by quarter end.

    Read from the view the cycles are derived from, so a beta's policy move and the window
    it is measured over cannot come from two different treatments of the same series.
    """
    rows = connection.execute("select quarter_end, rate_fraction from int_rate_cycles").fetchall()
    return dict(rows)
