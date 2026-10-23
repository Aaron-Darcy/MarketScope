"""Milestone 3: do foreign-office deposits explain the custody banks' move between cycles?

Methodology 6.1 offers a hypothesis, formed after the persistence result was seen, for State
Street's move from the first quartile of calibration-cycle betas to the third, and Northern
Trust's from the second to the third. A custody bank holds much of its deposit base in
other currencies. Through 2015 to 2019 euro and yen policy rates stayed at or below zero
while the dollar rate rose, which would hold down a beta measured against the federal funds
rate; in 2022 and 2023 the euro rate rose too.

The Call Report splits both interest-bearing deposits and their expense between domestic and
foreign offices, so a beta can be read for each. If the hypothesis holds, a custody bank's
foreign offices should reprice far less than its domestic offices in the calibration cycle
and close much of that gap in the test cycle, and measuring every filer on its domestic
offices alone should remove most of the move between quartiles.

This is a post-hoc test of a post-hoc hypothesis, designed after State Street's office split
had been looked at. It is evidence about a mechanism, not a confirmatory result, and it does
not touch the headline. A foreign office is a branch or subsidiary outside the US, not a
currency: dollar deposits booked offshore count as foreign here.

Usage:
    python analysis/milestone3/foreign_deposits.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from marketscope import store
from marketscope.cycles import RateCycle, read_study_cycles
from marketscope.metrics import cost_of_deposits, cumulative_beta
from marketscope.panel import previous_quarter_end
from marketscope.persistence import CALIBRATION, HEADLINE, TEST, eligible, read_filers
from marketscope.ranking import average_ranks, quartiles, spearman
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

# A filer is reported by office where foreign offices hold at least a tenth of its
# interest-bearing deposits across the calibration cycle. Below that the foreign beta rests
# on a balance too small to move the total.
FOREIGN_SHARE_FLOOR = 0.10

# The same rule as the persistence script's material deviators.
DEVIATION = 2

OFFICES = ("total", "domestic", "foreign")


@dataclass(frozen=True)
class Office:
    interest_bearing: float | None
    expense: float | None


@dataclass(frozen=True)
class Group:
    cik: int
    name: str
    quarters: dict[date, dict[str, Office]]

    def cost(self, quarter: date, office: str) -> float | None:
        current = self.quarters.get(quarter, {}).get(office)
        if current is None or current.interest_bearing is None or current.expense is None:
            return None
        opening = self.quarters.get(previous_quarter_end(quarter), {}).get(office)
        return cost_of_deposits(
            current.expense,
            opening.interest_bearing if opening is not None else None,
            current.interest_bearing,
        )

    def beta(self, cycle: RateCycle, office: str) -> float | None:
        start, end = self.cost(cycle.start, office), self.cost(cycle.end, office)
        if start is None or end is None:
            return None
        return cumulative_beta(start, end, cycle.start_rate, cycle.end_rate)

    def foreign_share(self, cycle: RateCycle) -> float:
        shares = [
            (offices["foreign"].interest_bearing or 0.0) / total
            for quarter, offices in self.quarters.items()
            if cycle.covers(quarter)
            and (total := offices["total"].interest_bearing) is not None
            and total > 0
        ]
        if not shares:
            raise ValueError(f"{self.name} has no interest-bearing deposits in {cycle.name}")
        return sum(shares) / len(shares)


def read_groups(connection: duckdb.DuckDBPyConnection, ciks: list[int]) -> list[Group]:
    """Each filer's insured institutions summed per quarter, by office.

    A sum of foreign figures is null only where every institution in the group leaves it
    out, which is a group with no foreign offices.
    """
    rows = connection.execute(
        f"""
        select
            financials.cik,
            members.registrant_name,
            financials.quarter_end,
            sum(financials.interest_bearing_deposits),
            sum(financials.deposit_expense),
            sum(financials.domestic_interest_bearing_deposits),
            sum(financials.domestic_deposit_expense),
            sum(financials.foreign_interest_bearing_deposits),
            sum(financials.foreign_deposit_expense)
        from main_staging.stg_fdic__financials as financials
        join dim_bank as members using (cik)
        where financials.cik in ({", ".join(str(cik) for cik in ciks)})
        group by all
        """
    ).fetchall()

    names: dict[int, str] = {}
    quarters: dict[int, dict[date, dict[str, Office]]] = {}
    for cik, name, quarter, *figures in rows:
        names[cik] = name
        quarters.setdefault(cik, {})[quarter] = {
            office: Office(figures[2 * index], figures[2 * index + 1])
            for index, office in enumerate(OFFICES)
        }
    return [Group(cik, names[cik], quarters[cik]) for cik in sorted(quarters)]


def by_office(groups: list[Group], cycles: dict[str, RateCycle]) -> list[str]:
    calibration = cycles[CALIBRATION]
    lines = [
        f"Filers with at least {FOREIGN_SHARE_FLOOR:.0%} of interest-bearing deposits in "
        "foreign offices across the calibration cycle,",
        "Call Report betas by office:",
        f"  {'':<28}{'foreign share':>14}{'':>3}{'domestic':>9}{'foreign':>9}{'total':>8}",
    ]
    for group in sorted(groups, key=lambda group: -group.foreign_share(calibration)):
        if group.foreign_share(calibration) < FOREIGN_SHARE_FLOOR:
            continue
        for name, cycle in cycles.items():
            betas = [group.beta(cycle, office) for office in ("domestic", "foreign", "total")]
            lines.append(
                f"  {(group.name[:26] if name == CALIBRATION else ''):<28}"
                f"{group.foreign_share(cycle):>14.0%}{name[:3]:>3}"
                + "".join(f"{beta:>9.3f}" if beta is not None else f"{'-':>9}" for beta in betas)
            )
    return lines


def quartile_moves(groups: list[Group], cycles: dict[str, RateCycle]) -> list[str]:
    """Each filer's quartile in both cycles on total betas and on domestic-office betas.

    Filers with no foreign offices have the same beta both ways, so any change in the
    deviators comes from the filers that do.
    """
    calibration, test = cycles[CALIBRATION], cycles[TEST]
    complete = [
        group
        for group in groups
        if all(
            group.beta(cycle, office) is not None
            for cycle in (calibration, test)
            for office in ("total", "domestic")
        )
    ]
    lines = [f"Quartiles across the {len(complete)} headline filers with Call Report betas:"]
    for office in ("total", "domestic"):
        first = [group.beta(calibration, office) or 0.0 for group in complete]
        second = [group.beta(test, office) or 0.0 for group in complete]
        lines.append(
            f"  {office} betas, filers above the foreign share floor: "
            + "; ".join(
                f"{group.name[:16]} {before} to {after}"
                for group, before, after in zip(
                    complete, quartiles(first), quartiles(second), strict=True
                )
                if group.foreign_share(calibration) >= FOREIGN_SHARE_FLOOR
            )
        )
        moves = [
            f"{group.name[:24]} {before} to {after}"
            for group, before, after in zip(
                complete, quartiles(first), quartiles(second), strict=True
            )
            if abs(after - before) >= DEVIATION
        ]
        lines += [
            f"  {office} betas: cross-cycle Spearman {spearman(first, second):+.3f}; "
            f"two or more quartiles apart: {len(moves)}",
            *(f"    {move}" for move in moves),
        ]

    shares = [group.foreign_share(calibration) for group in complete]
    first = [group.beta(calibration, "total") or 0.0 for group in complete]
    second = [group.beta(test, "total") or 0.0 for group in complete]
    rises = [
        after - before
        for before, after in zip(average_ranks(first), average_ranks(second), strict=True)
    ]
    lines += [
        "",
        "Across the same filers, Spearman of the calibration-cycle foreign share against the "
        f"rise in rank\nfrom calibration to test on total betas: {spearman(shares, rises):+.3f}",
    ]
    for group, share, rise in sorted(
        zip(complete, shares, rises, strict=True), key=lambda row: -row[1]
    )[:4]:
        lines.append(f"  {group.name[:28]:<28} share {share:>4.0%}, rank {rise:+.1f}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    connection = store.connect(args.database, read_only=True)
    try:
        cycles = read_study_cycles(connection)
        sample = [filer for filer in read_filers(connection) if eligible(filer, HEADLINE)]
        groups = read_groups(connection, [filer.cik for filer in sample])
    finally:
        connection.close()

    report = "\n".join(
        [
            f"Headline filers: {len(sample)}; with Call Reports: {len(groups)}",
            "",
            *by_office(groups, cycles),
            "",
            *quartile_moves(groups, cycles),
        ]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "foreign_deposits.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
