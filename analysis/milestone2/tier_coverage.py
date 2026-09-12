"""Milestone 2: does the tier logic built on twelve banks hold across the full universe?

The comparability tiers, the interest-bearing resolution routes and the completeness check
on reconstructed numerators were all designed against a twelve-bank sample chosen for its
variety. The universe is fifty-one filers, most of them smaller and more thinly disclosed,
so the question is whether tier 1 coverage survives at that width or collapses into tier 3
reconstruction and tier X exclusion.

Reads the warehouse rather than the SEC, so it measures exactly what the pipeline loaded.

Usage:
    python analysis/milestone2/tier_coverage.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from marketscope import store
from marketscope.metrics import MetricTier, resolve_deposit_cost
from marketscope.panel import PANEL_TAGS, previous_quarter_end, quarterly_panel
from marketscope.store import DATABASE_PATH
from marketscope.universe import SeedRow

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

QUARTER_LAST_DAY = {3: 31, 6: 30, 9: 30, 12: 31}

# The specification's cycle windows. Coverage is measured against these rather than against
# whatever a filer happens to report, so a bank that stops filing mid-cycle is visible as a
# coverage gap rather than as a complete short series.
CYCLES: dict[str, tuple[date, date]] = {
    "calibration": (date(2015, 12, 31), date(2019, 6, 30)),
    "test": (date(2022, 3, 31), date(2023, 12, 31)),
}

# Specification 7.2: a bank needs this share of quarters to carry a headline result.
COVERAGE_FLOOR = 0.80

# Headline results run on tier 1, then repeat including tier 2 as a robustness check.
# Tier 3 reconstructs the numerator and tier X failed its completeness test, so neither
# counts toward the coverage a headline result requires.
HEADLINE_TIERS = frozenset({MetricTier.TIER_1, MetricTier.TIER_2})

TIER_ORDER: tuple[MetricTier, ...] = (
    MetricTier.TIER_1,
    MetricTier.TIER_2,
    MetricTier.TIER_3,
    MetricTier.EXCLUDED,
)


def cycle_quarters(cycle: tuple[date, date]) -> list[date]:
    """Every quarter end inside a cycle window, inclusive of both bounds."""
    start, end = cycle
    quarters: list[date] = []
    current = start

    while current <= end:
        quarters.append(current)
        month = current.month + 3
        year = current.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        current = date(year, month, QUARTER_LAST_DAY[month])

    return quarters


@dataclass(frozen=True)
class BankQuarter:
    cik: int
    registrant_name: str
    quarter: date
    tier: MetricTier
    rate: float
    expense_provenance: str
    balance_provenance: str
    avg_method: str
    component_coverage: float | None


@dataclass(frozen=True)
class CycleCoverage:
    quarters: int
    covered: int

    @property
    def share(self) -> float:
        return self.covered / self.quarters if self.quarters else 0.0

    @property
    def is_eligible(self) -> bool:
        return self.share >= COVERAGE_FLOOR


@dataclass(frozen=True)
class BankSummary:
    member: SeedRow
    tiers: Counter[MetricTier]
    coverage: dict[str, CycleCoverage] = field(default_factory=dict)

    @property
    def best_tier(self) -> MetricTier | None:
        """The most precise tier the filer reaches anywhere in its history."""
        for tier in TIER_ORDER:
            if self.tiers.get(tier):
                return tier
        return None


def bank_quarters(member: SeedRow, panel: dict[date, dict[str, float]]) -> list[BankQuarter]:
    rows: list[BankQuarter] = []

    for quarter in sorted(panel):
        cost = resolve_deposit_cost(panel[quarter], panel.get(previous_quarter_end(quarter)))
        if cost is None:
            continue
        rows.append(
            BankQuarter(
                cik=member.cik,
                registrant_name=member.registrant_name,
                quarter=quarter,
                tier=cost.tier,
                rate=cost.rate,
                expense_provenance=cost.expense_provenance.value,
                balance_provenance=cost.balance_provenance.value,
                avg_method=cost.avg_method,
                component_coverage=cost.component_coverage,
            )
        )

    return rows


def summarise_bank(member: SeedRow, rows: list[BankQuarter]) -> BankSummary:
    by_quarter = {row.quarter: row for row in rows}

    coverage = {}
    for name, cycle in CYCLES.items():
        quarters = cycle_quarters(cycle)
        covered = sum(
            1
            for quarter in quarters
            if quarter in by_quarter and by_quarter[quarter].tier in HEADLINE_TIERS
        )
        coverage[name] = CycleCoverage(quarters=len(quarters), covered=covered)

    return BankSummary(
        member=member,
        tiers=Counter(row.tier for row in rows),
        coverage=coverage,
    )


def run(database: Path, output_dir: Path) -> tuple[list[BankQuarter], list[BankSummary]]:
    connection = store.connect(database, read_only=True)
    try:
        members = store.read_universe(connection)
        logger.info("Resolving deposit cost for %d members", len(members))

        rows: list[BankQuarter] = []
        summaries: list[BankSummary] = []

        for member in members:
            facts = store.read_facts(connection, member.cik, tags=PANEL_TAGS)
            member_rows = bank_quarters(member, quarterly_panel(facts))
            rows.extend(member_rows)
            summaries.append(summarise_bank(member, member_rows))
    finally:
        connection.close()

    write(rows, summaries, output_dir)
    return rows, summaries


def write(rows: list[BankQuarter], summaries: list[BankSummary], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "cik": row.cik,
                "registrant_name": row.registrant_name,
                "quarter": row.quarter,
                "tier": row.tier.value,
                "cost_of_deposits": row.rate,
                "expense_provenance": row.expense_provenance,
                "balance_provenance": row.balance_provenance,
                "avg_method": row.avg_method,
                "component_coverage": row.component_coverage,
            }
            for row in rows
        ]
    ).to_csv(output_dir / "bank_quarters.csv", index=False)

    summary_rows: list[dict[str, Any]] = []
    for summary in summaries:
        record: dict[str, Any] = {
            "cik": summary.member.cik,
            "registrant_name": summary.member.registrant_name,
            "rank": summary.member.rank,
            "pinned": summary.member.pinned,
            "bank_quarters": sum(summary.tiers.values()),
            "best_tier": summary.best_tier.value if summary.best_tier else "",
        }
        for tier in TIER_ORDER:
            record[f"tier_{tier.value.lower()}"] = summary.tiers.get(tier, 0)
        for name, cycle_coverage in summary.coverage.items():
            record[f"{name}_covered"] = cycle_coverage.covered
            record[f"{name}_quarters"] = cycle_coverage.quarters
            record[f"{name}_share"] = cycle_coverage.share
            record[f"{name}_eligible"] = cycle_coverage.is_eligible
        summary_rows.append(record)

    pd.DataFrame(summary_rows).to_csv(output_dir / "tier_summary.csv", index=False)


def summarise(rows: list[BankQuarter], summaries: list[BankSummary]) -> str:
    total = len(rows)
    lines = [
        "Tier coverage across the full universe",
        "",
        f"Bank-quarters resolved: {total:,} across {len(summaries)} filers",
        "",
    ]

    tiers = Counter(row.tier for row in rows)
    for tier in TIER_ORDER:
        count = tiers.get(tier, 0)
        lines.append(f"  tier {tier.value}: {count:>6,}  {count / total if total else 0:>6.1%}")

    lines += ["", "Filers by the most precise tier they reach:"]
    best = Counter(summary.best_tier for summary in summaries)
    for tier in TIER_ORDER:
        lines.append(f"  tier {tier.value:<12} {best.get(tier, 0):>3}")
    lines.append(f"  {'no series':<17} {best.get(None, 0):>3}")

    for label, attribute in (
        ("interest-bearing base", "balance_provenance"),
        ("deposit expense numerator", "expense_provenance"),
    ):
        lines += ["", f"Provenance of the {label}:"]
        counts = Counter(getattr(row, attribute) for row in rows)
        for provenance, count in counts.most_common():
            lines.append(f"  {provenance:<20} {count:>6,}")

    lines += ["", "Averaging method:"]
    for method, count in Counter(row.avg_method for row in rows).most_common():
        lines.append(f"  {method:<20} {count:>6,}")

    for name in CYCLES:
        eligible = [s for s in summaries if s.coverage[name].is_eligible]
        lines += [
            "",
            f"{name.title()} cycle, filers at or above the {COVERAGE_FLOOR:.0%} floor: "
            f"{len(eligible)} of {len(summaries)}",
        ]
        short = sorted(
            (s for s in summaries if not s.coverage[name].is_eligible),
            key=lambda s: -s.coverage[name].share,
        )
        for summary in short:
            cycle_coverage = summary.coverage[name]
            pin = "  (pinned)" if summary.member.pinned else ""
            lines.append(
                f"    {summary.member.registrant_name[:40]:<40} "
                f"{cycle_coverage.covered:>2}/{cycle_coverage.quarters} "
                f"{cycle_coverage.share:>6.1%}{pin}"
            )

    excluded = sorted(
        (s for s in summaries if s.tiers.get(MetricTier.EXCLUDED)),
        key=lambda s: -s.tiers[MetricTier.EXCLUDED],
    )
    lines += ["", f"Filers with tier X bank-quarters: {len(excluded)}"]
    for summary in excluded:
        lines.append(
            f"  {summary.member.registrant_name[:40]:<40} "
            f"{summary.tiers[MetricTier.EXCLUDED]:>3} quarters"
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows, summaries = run(args.database, args.output_dir)
    if not rows:
        print("No bank-quarters resolved.")
        return 1

    report = summarise(rows, summaries)
    print(report)
    (args.output_dir / "tier_coverage.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
