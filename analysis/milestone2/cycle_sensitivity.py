"""Milestone 2: does the cross-bank ordering depend on exactly where a cycle is cut?

dim_rate_cycle places each boundary where the policy rate turns, and that placement is
mechanical rather than chosen. The derived calibration cycle ends at 2019Q1, a quarter
before the window the specification pinned by hand, and the gate script measured the test
cycle to 2023Q3 where the derivation ends it at 2023Q4. If a one-quarter move at either end
reorders banks, the persistence test is measuring the cut rather than behaviour, and the
windows need an argument beyond the rate series.

Each boundary is shifted one quarter either way and the betas recomputed, and each
alternative is compared with the derived window by rank correlation across the filers
both can measure. Only within-cycle ordering is compared. The cross-cycle correlation the
windows exist to feed is deliberately not computed here, so no window can be chosen by
how the headline result comes out.

Usage:
    python analysis/milestone2/cycle_sensitivity.py
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from marketscope import store
from marketscope.cycles import RateCycle, read_policy_rate, read_study_cycles
from marketscope.metrics import MetricTier, cumulative_beta, resolve_deposit_cost
from marketscope.panel import PANEL_TAGS, previous_quarter_end, quarter_end, quarterly_panel
from marketscope.ranking import spearman
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

HEADLINE_TIERS = frozenset({MetricTier.TIER_1, MetricTier.TIER_2})

# A cumulative beta outside this range cannot be a pass-through share. Above 1.0 matches the
# ceiling the construct validity check applies; below zero means deposit cost fell across
# a tightening cycle, which marks a faulty endpoint rather than a bank.
PLAUSIBLE_BETA = (0.0, 1.0)

Series = dict[str, dict[date, float]]


@dataclass(frozen=True)
class Comparison:
    cycle: str
    label: str
    start: date
    end: date
    filers: int
    median_beta: float
    spearman_all: float | None
    spearman_plausible: float | None
    plausible_filers: int
    largest_mover: str
    largest_shift: float


def next_quarter_end(quarter: date) -> date:
    return quarter_end(quarter + timedelta(days=1))


def alternatives(cycle: RateCycle) -> dict[str, RateCycle]:
    """The derived window and every window one quarter away from it at either end."""
    return {
        "derived": cycle,
        "start one quarter earlier": replace(cycle, start=previous_quarter_end(cycle.start)),
        "start one quarter later": replace(cycle, start=next_quarter_end(cycle.start)),
        "end one quarter earlier": replace(cycle, end=previous_quarter_end(cycle.end)),
        "end one quarter later": replace(cycle, end=next_quarter_end(cycle.end)),
    }


def is_plausible(beta: float) -> bool:
    low, high = PLAUSIBLE_BETA
    return low <= beta <= high


def headline_series(connection: object) -> Series:
    """Headline-tier cost of deposits for every member, keyed by registrant then quarter."""
    series: Series = {}
    for member in store.read_universe(connection):  # type: ignore[arg-type]
        panel = quarterly_panel(store.read_facts(connection, member.cik, tags=PANEL_TAGS))  # type: ignore[arg-type]
        costs: dict[date, float] = {}
        for quarter, values in panel.items():
            resolved = resolve_deposit_cost(values, panel.get(previous_quarter_end(quarter)))
            if resolved is not None and resolved.tier in HEADLINE_TIERS:
                costs[quarter] = resolved.rate
        series[member.registrant_name] = costs
    return series


def betas(series: Series, policy: dict[date, float], window: RateCycle) -> dict[str, float]:
    if window.start not in policy or window.end not in policy:
        raise KeyError(f"No policy rate for {window.start} or {window.end}")

    result: dict[str, float] = {}
    for registrant, costs in series.items():
        if window.start not in costs or window.end not in costs:
            continue
        beta = cumulative_beta(
            costs[window.start], costs[window.end], policy[window.start], policy[window.end]
        )
        if beta is not None:
            result[registrant] = beta
    return result


def _correlation(
    derived: dict[str, float], alternative: dict[str, float], filers: list[str]
) -> float | None:
    if len(filers) < 2:
        return None
    return spearman([derived[f] for f in filers], [alternative[f] for f in filers])


def compare(cycle: RateCycle, series: Series, policy: dict[date, float]) -> list[Comparison]:
    windows = alternatives(cycle)
    derived = betas(series, policy, cycle)
    comparisons: list[Comparison] = []

    for label, window in windows.items():
        alternative = betas(series, policy, window)
        common = sorted(set(derived) & set(alternative))
        plausible = [f for f in common if is_plausible(derived[f]) and is_plausible(alternative[f])]
        mover = max(common, key=lambda f: abs(alternative[f] - derived[f]))

        comparisons.append(
            Comparison(
                cycle=cycle.name,
                label=label,
                start=window.start,
                end=window.end,
                filers=len(alternative),
                median_beta=statistics.median(alternative.values()),
                spearman_all=(
                    None if label == "derived" else _correlation(derived, alternative, common)
                ),
                spearman_plausible=(
                    None if label == "derived" else _correlation(derived, alternative, plausible)
                ),
                plausible_filers=len(plausible),
                largest_mover=mover,
                largest_shift=alternative[mover] - derived[mover],
            )
        )

    return comparisons


def implausible_endpoints(
    cycle: RateCycle, series: Series, policy: dict[date, float]
) -> list[tuple[str, float, float, float]]:
    """Filers whose derived-window beta falls outside the plausible range, with endpoints."""
    return sorted(
        (registrant, beta, series[registrant][cycle.start], series[registrant][cycle.end])
        for registrant, beta in betas(series, policy, cycle).items()
        if not is_plausible(beta)
    )


def run(database: Path, output_dir: Path) -> tuple[list[Comparison], str]:
    connection = store.connect(database, read_only=True)
    try:
        cycles = read_study_cycles(connection)
        policy = read_policy_rate(connection)
        series = headline_series(connection)
    finally:
        connection.close()

    comparisons = [c for cycle in cycles.values() for c in compare(cycle, series, policy)]
    report = summarise(cycles, comparisons, series, policy)

    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([vars(c) for c in comparisons]).to_csv(
        output_dir / "cycle_sensitivity.csv", index=False
    )
    (output_dir / "cycle_sensitivity.txt").write_text(report, encoding="utf-8")
    return comparisons, report


def _format_correlation(value: float | None) -> str:
    return f"{value:+.3f}" if value is not None else "     -"


def summarise(
    cycles: dict[str, RateCycle],
    comparisons: list[Comparison],
    series: Series,
    policy: dict[date, float],
) -> str:
    lines = [
        "Cycle boundary sensitivity: headline-tier cumulative deposit beta",
        "",
        "Each alternative is compared with the derived window by Spearman rank correlation",
        "over the filers both windows can measure. 'plausible' restricts that to filers whose",
        f"beta lies within {PLAUSIBLE_BETA[0]:.1f} to {PLAUSIBLE_BETA[1]:.1f} under both windows.",
    ]

    for name, cycle in cycles.items():
        lines += [
            "",
            f"{name.title()} cycle, derived {cycle.start} to {cycle.end}, "
            f"{len(cycle.quarters())} quarters, policy move {cycle.move * 100:.2f}pp",
            "",
            f"  {'window':<28} {'end points':<23} {'n':>3} {'median':>7} "
            f"{'rho all':>8} {'rho plaus.':>10}  largest mover",
        ]
        for c in (c for c in comparisons if c.cycle == name):
            row = (
                f"  {c.label:<28} {c.start} {c.end} {c.filers:>3} {c.median_beta:>7.3f} "
                f"{_format_correlation(c.spearman_all):>8} "
                f"{_format_correlation(c.spearman_plausible):>10}  "
                + ("" if c.label == "derived" else f"{c.largest_mover[:32]} {c.largest_shift:+.3f}")
            )
            lines.append(row.rstrip())

        implausible = implausible_endpoints(cycle, series, policy)
        if implausible:
            lines += [
                "",
                "  Implausible betas on the derived window, cost of deposits at each end:",
            ]
            for registrant, beta, start_cost, end_cost in implausible:
                lines.append(
                    f"    {registrant[:40]:<40} {beta:>7.3f}   "
                    f"{start_cost * 100:>6.2f}% -> {end_cost * 100:>6.2f}%"
                )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    _, report = run(args.database, args.output_dir)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
