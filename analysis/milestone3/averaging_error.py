"""Milestone 3: how far does endpoint averaging move the cost of deposits?

Every cost of deposits divides by the mean of two quarter-end balances, because no filer
tags an average deposit balance (decision 0011). Call Reports report true quarterly averages
on Schedule RC-K, so for each regulatory group whose averages reconcile on a basis
(decision 0039) the endpoint average can be set against the reported one, and the cost of
deposits restated on it with the expense unchanged.

A quarter in which the group's filer completed a material acquisition is listed rather than
summarised: the reported average covers part of the quarter on each side of the completion
while the endpoint average spans it, which is an entity event rather than averaging. A
quarter in which the group's quarter-end base on its basis stepped by a tenth or more is
summarised and also listed, because the step is as likely to be a merger of charters or a
change in how swept balances are reported as a movement of deposits, and only the last is
averaging error.

Usage:
    python analysis/milestone3/averaging_error.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.cycles import read_study_cycles
from marketscope.regulatory import REFERENCE_MAP
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

BASIS_POINTS = 10_000.0
PERCENT = 100.0

# The cost difference regulatory_validation.py treats as agreement, fixed there by its effect
# on a test-cycle beta.
AGREEMENT_BP = 10.0

# The deposit step decision 0032 makes material for an acquisition, applied here to the
# group's own quarter-end base on its basis.
MATERIAL_STEP = 0.10

LARGEST = 10


def read_errors(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = connection.execute(
        """
        select
            averages.group_key,
            averages.cik,
            averages.quarter_end,
            averages.basis,
            averages.interest_bearing_gap,
            averages.nontransaction_gap,
            averages.averaging_error,
            averages.closing_only_error,
            averages.endpoint_average,
            averages.closing_balance,
            costs.cost_of_deposits as endpoint_cost,
            exists (
                select 1
                from bank_entity_events as events
                where events.cik = averages.cik
                  and events.material
                  and events.event_quarter = averages.quarter_end
            ) as material_event
        from int_regulatory_average_balances as averages
        left join int_regulatory_deposit_cost as costs
          on costs.group_key = averages.group_key
         and costs.quarter_end = averages.quarter_end
        order by averages.group_key, averages.quarter_end
        """
    ).df()
    frame["quarter_end"] = frame["quarter_end"].dt.date
    frame["group_name"] = frame["group_key"].map(lambda key: REFERENCE_MAP[key].name)
    # Restated on the reported average the cost scales by one plus the error, so the
    # endpoint cost misses it by the error times the cost.
    frame["cost_error_bp"] = -frame["averaging_error"] * frame["endpoint_cost"] * BASIS_POINTS
    # The endpoint average is the mean of the two quarter ends, so the opening one is
    # recovered from it and the closing one.
    opening = 2 * frame["endpoint_average"] - frame["closing_balance"]
    frame["base_step"] = frame["closing_balance"] / opening - 1
    frame["stepped"] = frame["base_step"].abs() >= MATERIAL_STEP
    return frame


def cycle_of(quarter: date, windows: dict[str, tuple[date, date]]) -> str:
    for name, (start, end) in windows.items():
        if start <= quarter <= end:
            return name
    return "outside"


def describe(rows: pd.DataFrame) -> str:
    error = rows["averaging_error"].abs() * PERCENT
    cost = rows["cost_error_bp"].abs()
    return (
        f"{len(rows):>5} {error.median():>7.2f} {error.quantile(0.9):>7.2f} "
        f"{rows['averaging_error'].mean() * PERCENT:>+7.2f} {cost.median():>7.2f} "
        f"{cost.quantile(0.9):>7.2f} {cost.max():>7.1f} {(cost > AGREEMENT_BP).sum():>6}"
    )


def bases(frame: pd.DataFrame) -> list[str]:
    groups = frame.groupby("group_key").agg(
        name=("group_name", "first"),
        basis=("basis", "first"),
        quarters=("quarter_end", "size"),
        interest_bearing=("interest_bearing_gap", "median"),
        nontransaction=("nontransaction_gap", "median"),
    )
    lines = [
        f"Groups measured: {groups['basis'].notna().sum()} of {len(groups)}",
        f"  interest-bearing basis: {(groups['basis'] == 'interest_bearing').sum()}",
        f"  nontransaction basis:   {(groups['basis'] == 'nontransaction').sum()}",
        "",
        "Groups reconciling on neither basis, median gap on each (decision 0039):",
    ]
    unreconciled = groups[groups["basis"].isna()].copy()
    unreconciled["closer"] = unreconciled[["interest_bearing", "nontransaction"]].abs().min(axis=1)
    for _, row in unreconciled.sort_values("closer").iterrows():
        lines.append(
            f"  {row['name'][:40]:<40} {row['interest_bearing'] * PERCENT:>+7.1f}% "
            f"{row['nontransaction'] * PERCENT:>+7.1f}%  over {row['quarters']} quarters"
        )
    return lines


def distribution(measured: pd.DataFrame) -> list[str]:
    header = (
        f"{'':<18}{'n':>5} {'|err|%':>7} {'p90 %':>7} {'mean %':>7} {'|bp|':>7} "
        f"{'p90 bp':>7} {'max bp':>7} {'>10bp':>6}"
    )
    lines = [
        "Endpoint against reported average, on each group's reconciling basis, in quarters",
        "without a material acquisition",
        "  err: endpoint average over reported average, less one; positive overstates the base",
        "  bp: the endpoint cost of deposits less the cost on the reported average",
        "",
        header,
        f"{'all':<18}{describe(measured)}",
        f"{'without a step':<18}{describe(measured[~measured['stepped']])}",
    ]
    for cycle in ("calibration", "test", "outside"):
        rows = measured[measured["cycle"] == cycle]
        label = f"{cycle} cycle" if cycle != "outside" else "outside cycles"
        lines.append(f"{label:<18}{describe(rows)}")
    lines.append("")
    for year, rows in measured.groupby(measured["quarter_end"].map(lambda day: day.year)):
        lines.append(f"{year!s:<18}{describe(rows)}")
    return lines


def listed(rows: pd.DataFrame, title: str, limit: int | None = None) -> list[str]:
    ordered = rows.reindex(rows["cost_error_bp"].abs().sort_values(ascending=False).index)
    lines = [title]
    for _, row in ordered.head(limit if limit is not None else len(ordered)).iterrows():
        lines.append(
            f"  {row['group_name'][:36]:<36} {row['quarter_end']} {row['basis']:<17} "
            f"step {row['base_step'] * PERCENT:>+6.1f}% err {row['averaging_error'] * PERCENT:>+6.1f}% "
            f"cost {row['cost_error_bp']:>+6.1f}bp"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    connection = store.connect(args.database, read_only=True)
    try:
        frame = read_errors(connection)
        cycles = read_study_cycles(connection)
    finally:
        connection.close()

    if frame.empty:
        print("No group-quarter has a Call Report average to measure against.")
        return 1

    windows = {name: (cycle.start, cycle.end) for name, cycle in cycles.items()}
    frame["cycle"] = frame["quarter_end"].map(lambda day: cycle_of(day, windows))
    on_basis = frame[frame["basis"].notna()]
    acquisitions = on_basis[on_basis["material_event"]]
    measured = on_basis[~on_basis["material_event"]]

    sections = [
        bases(frame),
        distribution(measured),
        listed(
            measured[~measured["stepped"]],
            "Largest cost differences in quarters without a step:",
            LARGEST,
        ),
        listed(
            measured[measured["stepped"]],
            "Quarters where the base stepped by a tenth or more, summarised above:",
        ),
        listed(acquisitions, "Quarters of a material acquisition, not summarised:"),
    ]
    report = "\n\n".join("\n".join(section) for section in sections)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["group_name"]).to_csv(args.output_dir / "averaging_error.csv", index=False)
    (args.output_dir / "averaging_error.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
