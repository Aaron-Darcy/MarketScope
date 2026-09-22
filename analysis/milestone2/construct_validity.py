"""Milestone 2: does the metric measure repricing behaviour or reporting differences?

Gate criterion G4 tested this by comparing two banks, a direct bank against a branch-funded
regional. Two banks is a weak test of construct validity and it depends entirely on both
being typical of their kind, which Zions turned out not to be.

This is the same economic hypothesis tested across the whole universe on a reported
characteristic rather than a hand-assigned label. Non-interest-bearing deposits are
transaction and operating balances: they pay nothing by construction, they are stickier than
rate-seeking money, and a bank funded by more of them has less of its base to reprice. The
prediction, fixed before the measurement, is a negative rank correlation between a bank's
non-interest-bearing share and its cumulative deposit beta.

A positive or flat correlation would say the metric is picking up disclosure differences
rather than behaviour, which is what G4 existed to detect.

Usage:
    python analysis/milestone2/construct_validity.py
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from marketscope import store
from marketscope.metrics import (
    TOTAL_DEPOSITS_TAG,
    MetricTier,
    cumulative_beta,
    resolve_deposit_cost,
    resolve_noninterest_bearing_deposits,
)
from marketscope.panel import PANEL_TAGS, previous_quarter_end, quarterly_panel
from marketscope.ranking import spearman
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

POLICY_SERIES = "FEDFUNDS"
QUARTER_LAST_DAY = {3: 31, 6: 30, 9: 30, 12: 31}

CYCLE_START = date(2022, 3, 31)
CYCLE_END = date(2023, 12, 31)

# Headline tiers only. A reconstructed numerator carries its own uncertainty and would
# blur a test whose whole purpose is to detect measurement error.
HEADLINE_TIERS = frozenset({MetricTier.TIER_1, MetricTier.TIER_2})

# A cumulative beta above this cannot be a pass-through share and marks a data fault
# rather than a fast-repricing bank.
IMPLAUSIBLE_BETA = 1.0


@dataclass(frozen=True)
class Observation:
    registrant_name: str
    beta: float
    noninterest_bearing_share: float

    @property
    def is_plausible(self) -> bool:
        return self.beta <= IMPLAUSIBLE_BETA


def quarter_end(day: date) -> date:
    month = ((day.month - 1) // 3 + 1) * 3
    return date(day.year, month, QUARTER_LAST_DAY[month])


def policy_rate_by_quarter(connection: object) -> dict[date, float]:
    """Quarter-averaged federal funds rate as a decimal fraction.

    FRED publishes the series monthly in percentage points while deposit costs here are
    decimal fractions. A beta computed across mismatched units is out by two orders of
    magnitude and still looks plausible enough to miss.
    """
    rows = connection.execute(  # type: ignore[attr-defined]
        "select observation_date, value from raw.fred_observations "
        "where series_id = ? and value is not null",
        [POLICY_SERIES],
    ).fetchall()

    by_quarter: dict[date, list[float]] = {}
    for observation_date, value in rows:
        by_quarter.setdefault(quarter_end(observation_date), []).append(value / 100.0)

    return {quarter: statistics.fmean(values) for quarter, values in by_quarter.items()}


def observe(connection: object, policy: dict[date, float]) -> list[Observation]:
    observations: list[Observation] = []

    for member in store.read_universe(connection):  # type: ignore[arg-type]
        panel = quarterly_panel(store.read_facts(connection, member.cik, tags=PANEL_TAGS))  # type: ignore[arg-type]

        costs: dict[date, float] = {}
        for quarter in (CYCLE_START, CYCLE_END):
            resolved = resolve_deposit_cost(
                panel.get(quarter, {}), panel.get(previous_quarter_end(quarter))
            )
            if resolved is not None and resolved.tier in HEADLINE_TIERS:
                costs[quarter] = resolved.rate

        shares = []
        for quarter, values in panel.items():
            if not CYCLE_START <= quarter <= CYCLE_END:
                continue
            total = values.get(TOTAL_DEPOSITS_TAG)
            noninterest = resolve_noninterest_bearing_deposits(values)
            if total and noninterest and total > 0:
                shares.append(noninterest.value / total)

        if len(costs) != 2 or not shares:
            continue

        beta = cumulative_beta(
            costs[CYCLE_START], costs[CYCLE_END], policy[CYCLE_START], policy[CYCLE_END]
        )
        if beta is None:
            continue

        observations.append(
            Observation(
                registrant_name=member.registrant_name,
                beta=beta,
                noninterest_bearing_share=statistics.fmean(shares),
            )
        )

    return sorted(observations, key=lambda o: o.noninterest_bearing_share)


def run(database: Path, output_dir: Path) -> list[Observation]:
    connection = store.connect(database, read_only=True)
    try:
        observations = observe(connection, policy_rate_by_quarter(connection))
    finally:
        connection.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "registrant_name": o.registrant_name,
                "test_cycle_beta": o.beta,
                "noninterest_bearing_share": o.noninterest_bearing_share,
                "plausible": o.is_plausible,
            }
            for o in observations
        ]
    ).to_csv(output_dir / "construct_validity.csv", index=False)

    return observations


def summarise(observations: list[Observation]) -> str:
    plausible = [o for o in observations if o.is_plausible]
    excluded = [o for o in observations if not o.is_plausible]

    lines = [
        "Construct validity: funding mix against test-cycle deposit beta",
        "",
        f"Filers with a headline-tier beta and a reported deposit split: {len(observations)}",
        f"  of which carry a plausible beta at or below {IMPLAUSIBLE_BETA:.1f}: {len(plausible)}",
        "",
        f"{'bank':<44} {'beta':>7} {'NIB share':>10}",
    ]
    for observation in observations:
        flag = "" if observation.is_plausible else "   <- implausible, excluded"
        lines.append(
            f"{observation.registrant_name[:44]:<44} {observation.beta:>7.3f} "
            f"{observation.noninterest_bearing_share:>10.1%}{flag}"
        )

    correlation = spearman(
        [o.noninterest_bearing_share for o in plausible], [o.beta for o in plausible]
    )
    with_outliers = spearman(
        [o.noninterest_bearing_share for o in observations], [o.beta for o in observations]
    )

    lines += [
        "",
        "Spearman rank correlation, non-interest-bearing share against beta",
        f"  plausible betas only ({len(plausible)} filers): {correlation:+.3f}",
        f"  including implausible ({len(observations)} filers): {with_outliers:+.3f}",
        "",
        "Predicted negative: a bank funded by more non-interest-bearing balances has less",
        "of its base to reprice. A positive or flat result would indicate the metric is",
        "measuring disclosure differences rather than behaviour.",
    ]

    if excluded:
        lines += ["", "Betas above 1.0, carried as a data quality finding:"]
        for observation in excluded:
            lines.append(f"  {observation.registrant_name[:44]:<44} {observation.beta:>7.3f}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    observations = run(args.database, args.output_dir)
    if not observations:
        print("No filers carry both a headline-tier beta and a reported deposit split.")
        return 1

    report = summarise(observations)
    print(report)
    (args.output_dir / "construct_validity.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
