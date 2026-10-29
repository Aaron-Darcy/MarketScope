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
from marketscope.averaging import cost_on_reported_average
from marketscope.cycles import RateCycle, read_study_cycles
from marketscope.metrics import cumulative_beta
from marketscope.persistence import CALIBRATION, HEADLINE, TEST, assess_pairs, eligible, read_filers
from marketscope.ranking import average_ranks, spearman
from marketscope.regulatory import REFERENCE_MAP, mapped_registrants
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


def regulatory_betas(measured: pd.DataFrame, cycles: dict[str, RateCycle]) -> pd.DataFrame:
    """Each reconciling group's cycle betas from its Call Reports, on both averages.

    Only complete cycles with an error measured at both ends, so the two betas differ by
    the averaging alone.
    """
    indexed = measured.set_index(["group_key", "quarter_end"])
    rows: list[dict[str, object]] = []
    for group_key in sorted(measured["group_key"].unique()):
        for name, cycle in cycles.items():
            ends = [(group_key, cycle.start), (group_key, cycle.end)]
            if not all(end in indexed.index for end in ends):
                continue
            start, end = (indexed.loc[key] for key in ends)
            endpoint = cumulative_beta(
                start["endpoint_cost"], end["endpoint_cost"], cycle.start_rate, cycle.end_rate
            )
            reported = cumulative_beta(
                cost_on_reported_average(start["endpoint_cost"], start["averaging_error"]),
                cost_on_reported_average(end["endpoint_cost"], end["averaging_error"]),
                cycle.start_rate,
                cycle.end_rate,
            )
            if endpoint is None or reported is None:
                continue
            rows.append(
                {
                    "group_key": group_key,
                    "group_name": start["group_name"],
                    "cycle": name,
                    "endpoint_beta": endpoint,
                    "reported_beta": reported,
                    "stepped_endpoint": bool(start["stepped"] or end["stepped"]),
                }
            )
    betas = pd.DataFrame(rows)
    betas["difference"] = betas["reported_beta"] - betas["endpoint_beta"]
    return betas


def beta_effect(betas: pd.DataFrame) -> list[str]:
    lines = [
        "Call Report cycle betas on the endpoint average and on the reported average",
        f"{'':<14}{'groups':>7} {'median |diff|':>14} {'p90 |diff|':>11} {'max |diff|':>11} "
        f"{'Spearman':>9}",
    ]
    for cycle, rows in betas.groupby("cycle", sort=False):
        difference = rows["difference"].abs()
        lines.append(
            f"{cycle!s:<14}{len(rows):>7} {difference.median():>14.3f} "
            f"{difference.quantile(0.9):>11.3f} {difference.max():>11.3f} "
            f"{spearman(list(rows['endpoint_beta']), list(rows['reported_beta'])):>+9.3f}"
        )
    lines += ["", "Betas moving by 0.02 or more, the scale 0032 treats as material:"]
    moved = betas[betas["difference"].abs() >= 0.02].sort_values("difference", key=abs)
    for _, row in moved.iloc[::-1].iterrows():
        lines.append(
            f"  {row['group_name'][:36]:<36} {row['cycle']:<12} {row['endpoint_beta']:.3f} "
            f"to {row['reported_beta']:.3f}"
            + ("  (an endpoint stepped by a tenth)" if row["stepped_endpoint"] else "")
        )
    if moved.empty:
        lines.append("  none")
    return lines


def read_headline(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The headline sample's beta endpoints, with the group each filer maps to."""
    sample = {filer.cik for filer in read_filers(connection) if eligible(filer, HEADLINE)}
    groups = {cik: key for key, cik in mapped_registrants().items()}
    frame = connection.execute(
        """
        select cik, registrant_name, cycle_name, start_quarter, measured_end_quarter,
            start_cost_of_deposits, end_cost_of_deposits, start_rate_fraction,
            end_rate_fraction, deposit_beta
        from fct_deposit_beta
        order by cik, cycle_name
        """
    ).df()
    frame = frame[frame["cik"].isin(sample)].copy()
    for column in ("start_quarter", "measured_end_quarter"):
        frame[column] = frame[column].dt.date
    frame["group_key"] = frame["cik"].map(groups)
    return frame


def restated_cost(
    measured: pd.DataFrame, group_key: object, quarter: date, cost: float
) -> tuple[float, str]:
    """An XBRL endpoint cost restated by its group's averaging error, and why if it is not.

    The error is measured on the group's Call Reports and applied to the holding company's
    filing, which assumes the two bases moved alike within the quarter. Quarters where the
    group's base stepped by a tenth are left as measured, since the step need not be one
    the filing shares.
    """
    if not isinstance(group_key, str):
        return cost, "no regulatory group"
    rows = measured[(measured["group_key"] == group_key) & (measured["quarter_end"] == quarter)]
    if rows.empty:
        return cost, "group not measured"
    row = rows.iloc[0]
    if row["stepped"]:
        return cost, "base stepped by a tenth"
    return cost_on_reported_average(cost, row["averaging_error"]), "restated"


def headline(measured: pd.DataFrame, endpoints: pd.DataFrame) -> list[str]:
    """The pre-registered headline with every restatable endpoint restated. A diagnostic,
    not a variant: specification 6.1 fixes the headline on the metric as built."""
    outcomes: dict[str, int] = {}
    restated: dict[tuple[int, str], float] = {}
    for _, row in endpoints.iterrows():
        start, start_outcome = restated_cost(
            measured, row["group_key"], row["start_quarter"], row["start_cost_of_deposits"]
        )
        end, end_outcome = restated_cost(
            measured, row["group_key"], row["measured_end_quarter"], row["end_cost_of_deposits"]
        )
        for outcome in (start_outcome, end_outcome):
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        beta = cumulative_beta(start, end, row["start_rate_fraction"], row["end_rate_fraction"])
        if beta is None:
            raise ValueError(f"{row['registrant_name']} has no restated {row['cycle_name']} beta")
        restated[(row["cik"], row["cycle_name"])] = beta

    names = dict(zip(endpoints["cik"], endpoints["registrant_name"], strict=False))
    measured_betas = {
        (row["cik"], row["cycle_name"]): row["deposit_beta"] for _, row in endpoints.iterrows()
    }
    ciks = sorted(names)
    pairs = {
        label: (
            [betas[(cik, CALIBRATION)] for cik in ciks],
            [betas[(cik, TEST)] for cik in ciks],
        )
        for label, betas in (("as measured", measured_betas), ("restated", restated))
    }

    lines = [
        "The headline on reported averages, as a diagnostic (specification 6.1 is unchanged)",
        f"  {len(ciks)} filers, {sum(outcomes.values())} beta endpoints: "
        + ", ".join(f"{count} {outcome}" for outcome, count in sorted(outcomes.items())),
    ]
    for label, (calibration, test) in pairs.items():
        result = assess_pairs(calibration, test)
        lines.append(
            f"  {label:<12} Spearman {result.spearman:+.3f}, p {result.p_value:.4f}, "
            f"95% interval {result.interval.low:+.3f} to {result.interval.high:+.3f}"
        )

    lines += [
        "",
        "  Headline betas moving by 0.02 or more, with rank of the sample before and after:",
    ]
    for cycle, position in ((CALIBRATION, 0), (TEST, 1)):
        before = average_ranks(pairs["as measured"][position])
        after = average_ranks(pairs["restated"][position])
        for index, cik in enumerate(ciks):
            difference = restated[(cik, cycle)] - measured_betas[(cik, cycle)]
            if abs(difference) >= 0.02:
                lines.append(
                    f"  {names[cik][:32]:<32} {cycle:<12} {measured_betas[(cik, cycle)]:.3f} to "
                    f"{restated[(cik, cycle)]:.3f}, rank {before[index]:g} to {after[index]:g}"
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
        endpoints = read_headline(connection)
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

    betas = regulatory_betas(measured, cycles)

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
        beta_effect(betas),
        headline(measured, endpoints),
    ]
    report = "\n\n".join("\n".join(section) for section in sections)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["group_name"]).to_csv(args.output_dir / "averaging_error.csv", index=False)
    betas.drop(columns=["group_name"]).to_csv(
        args.output_dir / "averaging_error_betas.csv", index=False
    )
    (args.output_dir / "averaging_error.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
