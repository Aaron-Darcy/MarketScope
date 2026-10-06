"""Milestone 2: how far do betas depend on which filing's value is believed?

Specification 4 resolves a period reported with different values by taking the most
recently filed one. The revision audit shows what that rule accepts: corrections and
recasts, but also another bank's history after a reverse merger and a figure dated to the
wrong quarter. If betas move materially when the original figures are used instead, the
precedence rule is carrying part of the result and has to be argued for; if they barely
move, the rule is a convention.

Every bank-quarter is resolved twice, once on the most recently filed value of each
period and once on the value as first published, and the headline-tier betas are compared
by rank correlation within each cycle. As with the cycle sensitivity, the cross-cycle
persistence result is not computed under either rule.

Usage:
    python analysis/milestone2/precedence_sensitivity.py
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
from marketscope.cycles import RateCycle, read_study_cycles
from marketscope.facts import DEFAULT_TAXONOMY, Fact, earliest_filed
from marketscope.metrics import MetricTier, cumulative_beta, resolve_deposit_cost
from marketscope.panel import PANEL_TAGS, Panel, build_panel, previous_quarter_end
from marketscope.ranking import spearman
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

HEADLINE_TIERS = frozenset({MetricTier.TIER_1, MetricTier.TIER_2})

PLAUSIBLE_BETA = (0.0, 1.0)

# A difference in annualised cost of deposits below one basis point is rounding.
MATERIAL_COST_DIFFERENCE = 0.0001

RULES: tuple[str, ...] = ("latest", "original")


@dataclass(frozen=True)
class Filer:
    cik: int
    registrant_name: str
    costs: dict[str, dict[date, float]]


def headline_costs(panel: Panel) -> dict[date, float]:
    costs: dict[date, float] = {}
    for quarter, values in panel.values.items():
        resolved = resolve_deposit_cost(values, panel.values.get(previous_quarter_end(quarter)))
        if resolved is not None and resolved.tier in HEADLINE_TIERS:
            costs[quarter] = resolved.rate
    return costs


def resolve_both(facts: list[Fact]) -> dict[str, dict[date, float]]:
    """Headline-tier costs under each precedence rule.

    The original figures go through the same panel, whose own precedence step then sees
    one value per period and keeps it.
    """
    standard = [fact for fact in facts if fact.taxonomy == DEFAULT_TAXONOMY]
    return {
        "latest": headline_costs(build_panel(standard)),
        "original": headline_costs(build_panel(earliest_filed(standard))),
    }


def read_filers(connection: object) -> list[Filer]:
    filers: list[Filer] = []
    for member in store.read_universe(connection):  # type: ignore[arg-type]
        facts = store.read_facts(connection, member.cik, tags=PANEL_TAGS)  # type: ignore[arg-type]
        filers.append(Filer(member.cik, member.registrant_name, resolve_both(facts)))
    return filers


def cycle_betas(filers: list[Filer], cycle: RateCycle, rule: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for filer in filers:
        costs = filer.costs[rule]
        if cycle.start not in costs or cycle.end not in costs:
            continue
        beta = cumulative_beta(
            costs[cycle.start], costs[cycle.end], cycle.start_rate, cycle.end_rate
        )
        if beta is not None:
            result[filer.registrant_name] = beta
    return result


def is_plausible(beta: float) -> bool:
    low, high = PLAUSIBLE_BETA
    return low <= beta <= high


def cost_differences(filers: list[Filer]) -> pd.DataFrame:
    rows = []
    for filer in filers:
        latest, original = filer.costs["latest"], filer.costs["original"]
        for quarter in sorted(set(latest) | set(original)):
            rows.append(
                {
                    "registrant_name": filer.registrant_name,
                    "quarter_end": quarter,
                    "latest": latest.get(quarter),
                    "original": original.get(quarter),
                }
            )
    frame = pd.DataFrame(rows)
    frame["difference"] = (frame["latest"] - frame["original"]).abs()
    return frame


def summarise(filers: list[Filer], cycles: dict[str, RateCycle], betas: pd.DataFrame) -> str:
    costs = cost_differences(filers)
    both = costs.dropna(subset=["latest", "original"])
    material = both[both["difference"] > MATERIAL_COST_DIFFERENCE]
    one_sided = costs[costs["latest"].isna() != costs["original"].isna()]

    lines = [
        "Precedence sensitivity: most recently filed against first published values",
        "",
        f"Headline-tier bank-quarters under either rule: {len(costs):,}",
        f"  resolved under both:                         {len(both):,}",
        f"  differing by more than one basis point:      {len(material):,}",
        f"  resolved under one rule only:                {len(one_sided):,}",
        "",
        "Bank-quarters differing by more than one basis point, by filer:",
    ]
    for name, count in material["registrant_name"].value_counts().head(12).items():
        lines.append(f"  {str(name)[:40]:<40} {count:>4}")

    for name, cycle in cycles.items():
        rows = betas[betas["cycle"] == name].dropna(subset=["latest", "original"])
        plausible = rows[rows["latest"].map(is_plausible) & rows["original"].map(is_plausible)]
        rows = rows.assign(shift=(rows["latest"] - rows["original"]).abs())
        lines += [
            "",
            f"{name.capitalize()} cycle, {cycle.start} to {cycle.end}",
            f"  filers with a headline-tier beta under both rules: {len(rows)}",
            f"  median beta, latest {statistics.median(rows['latest']):.3f}, "
            f"original {statistics.median(rows['original']):.3f}",
            f"  Spearman, all filers:            {spearman(list(rows['latest']), list(rows['original'])):+.3f}",
            f"  Spearman, plausible under both:  "
            f"{spearman(list(plausible['latest']), list(plausible['original'])):+.3f} "
            f"({len(plausible)} filers)",
            f"  filers whose beta moves by more than 0.01: {int((rows['shift'] > 0.01).sum())}",
            "  largest movers, latest against original:",
        ]
        for _, row in rows.sort_values("shift", ascending=False).head(5).iterrows():
            lines.append(
                f"    {str(row['registrant_name'])[:38]:<38} {row['latest']:>7.3f} "
                f"{row['original']:>7.3f}"
            )

    return "\n".join(lines)


def run(database: Path, output_dir: Path) -> str:
    connection = store.connect(database, read_only=True)
    try:
        cycles = read_study_cycles(connection)
        filers = read_filers(connection)
    finally:
        connection.close()

    rows = []
    for name, cycle in cycles.items():
        by_rule = {rule: cycle_betas(filers, cycle, rule) for rule in RULES}
        for filer in filers:
            rows.append(
                {
                    "cycle": name,
                    "registrant_name": filer.registrant_name,
                    **{rule: by_rule[rule].get(filer.registrant_name) for rule in RULES},
                }
            )
    betas = pd.DataFrame(rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    betas.to_csv(output_dir / "precedence_sensitivity.csv", index=False)
    return summarise(filers, cycles, betas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    report = run(args.database, args.output_dir)
    print(report)
    (args.output_dir / "precedence_sensitivity.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
