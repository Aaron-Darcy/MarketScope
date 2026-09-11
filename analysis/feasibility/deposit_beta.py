"""Milestone 0, gate criterion G4: does the metric measure repricing behaviour?

Computes an annualised cost of deposits per bank-quarter and a cumulative deposit beta per
cycle, then applies two checks.

  G4  A direct bank with no branch network should reprice faster than a branch-funded
      regional. Ally Financial must exceed Zions Bancorporation by a material margin over
      the test cycle. If it does not, the construction is measuring reporting differences
      rather than deposit behaviour.

  Benchmark  Federal Reserve work on FR Y-9C filings puts the industry cumulative
      interest-bearing deposit beta near 0.4 in both the 2015-2019 and 2022-2023 cycles.
      An aggregate computed here that lands far from that indicates a units, averaging or
      tag mapping error rather than a finding.

Usage:
    python analysis/feasibility/deposit_beta.py
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from marketscope.banks import FEASIBILITY_SAMPLE, Bank
from marketscope.facts import extract_facts
from marketscope.ingestion.fred import FredClient
from marketscope.ingestion.sec import SecClient
from marketscope.metrics import (
    MetricTier,
    cumulative_beta,
    resolve_deposit_cost,
    resolve_deposit_interest_expense,
    resolve_interest_bearing_deposits,
)
from marketscope.panel import previous_quarter_end, quarter_end, quarterly_panel

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
POLICY_SERIES = "FEDFUNDS"

CYCLES: dict[str, tuple[date, date]] = {
    "calibration": (date(2015, 12, 31), date(2019, 6, 30)),
    "test": (date(2022, 3, 31), date(2023, 9, 30)),
}

BENCHMARK_BETA = 0.40
BENCHMARK_TOLERANCE = 0.15
G4_MINIMUM_MARGIN = 0.10


def quarterly_policy_rate(client: FredClient) -> dict[date, float]:
    """Return the effective federal funds rate as a quarter-end keyed decimal fraction.

    FRED publishes the series monthly in percentage points. Deposit costs here are decimal
    fractions, so the policy rate is converted to match; a beta computed across mismatched
    units is out by two orders of magnitude and looks plausible enough to miss.
    """
    observations = client.observations(POLICY_SERIES, start=date(2014, 1, 1))
    by_quarter: dict[date, list[float]] = defaultdict(list)

    for observation in observations:
        if observation.value is None:
            continue
        quarter = quarter_end(observation.observation_date)
        by_quarter[quarter].append(observation.value / 100.0)

    return {quarter: statistics.fmean(values) for quarter, values in by_quarter.items()}


def bank_cost_series(payload: dict[str, Any]) -> list[dict[str, Any]]:
    panel = quarterly_panel(extract_facts(payload, taxonomy=None))
    rows: list[dict[str, Any]] = []

    for quarter in sorted(panel):
        cost = resolve_deposit_cost(panel[quarter], panel.get(previous_quarter_end(quarter)))
        if cost is None:
            continue
        rows.append(
            {
                "quarter": quarter,
                "cost_of_deposits": cost.rate,
                "tier": cost.tier.value,
                "expense_provenance": cost.expense_provenance.value,
                "balance_provenance": cost.balance_provenance.value,
                "avg_method": cost.avg_method,
                "component_coverage": cost.component_coverage,
            }
        )

    return rows


def aggregate_series(payloads: dict[int, dict[str, Any]]) -> dict[date, float]:
    """Industry cost of deposits: summed expense over summed interest-bearing balances.

    Aggregating the inputs before dividing, rather than averaging bank-level rates,
    reproduces how the Federal Reserve computes the industry figure and makes the
    benchmark comparison meaningful.
    """
    expense: dict[date, float] = defaultdict(float)
    balance: dict[date, float] = defaultdict(float)

    for payload in payloads.values():
        panel = quarterly_panel(extract_facts(payload, taxonomy=None))
        for quarter, values in panel.items():
            resolved = resolve_deposit_cost(values, panel.get(previous_quarter_end(quarter)))
            if resolved is None or resolved.tier is MetricTier.EXCLUDED:
                continue
            resolved_expense = resolve_deposit_interest_expense(values)
            resolved_balance = resolve_interest_bearing_deposits(values)
            if resolved_expense is None or resolved_balance is None:
                continue
            expense[quarter] += resolved_expense.value
            balance[quarter] += resolved_balance.value

    return {
        quarter: expense[quarter] * 4 / balance[quarter]
        for quarter in sorted(expense)
        if balance.get(quarter, 0) > 0
    }


def beta_over_cycle(
    series: dict[date, float], policy: dict[date, float], cycle: tuple[date, date]
) -> float | None:
    start, end = cycle
    if start not in series or end not in series:
        return None
    if start not in policy or end not in policy:
        return None
    return cumulative_beta(series[start], series[end], policy[start], policy[end])


def run(output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    sec = SecClient()
    fred = FredClient()

    try:
        policy = quarterly_policy_rate(fred)
        payloads: dict[int, dict[str, Any]] = {}
        rows: list[dict[str, Any]] = []

        for bank in FEASIBILITY_SAMPLE:
            logger.info("Computing deposit cost for %s", bank.name)
            payload = sec.company_facts(bank.cik)
            payloads[bank.cik] = payload
            for row in bank_cost_series(payload):
                rows.append({"cik": bank.cik, "bank": bank.name, **row})
    finally:
        sec.close()
        fred.close()

    costs = pd.DataFrame(rows)
    betas = _bank_betas(costs, policy)
    aggregate = aggregate_series(payloads)
    report = _report(costs, betas, aggregate, policy)

    output_dir.mkdir(parents=True, exist_ok=True)
    costs.to_csv(output_dir / "deposit_cost.csv", index=False)
    betas.to_csv(output_dir / "deposit_beta.csv", index=False)
    Path(output_dir / "g4_report.txt").write_text(report, encoding="utf-8")

    return costs, betas, report


def _bank_betas(costs: pd.DataFrame, policy: dict[date, float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    usable = costs[costs["tier"] != MetricTier.EXCLUDED.value]

    for (cik, bank), group in usable.groupby(["cik", "bank"]):
        series = dict(zip(group["quarter"], group["cost_of_deposits"], strict=True))
        tiers = set(group["tier"])
        for name, cycle in CYCLES.items():
            beta = beta_over_cycle(series, policy, cycle)
            rows.append(
                {
                    "cik": cik,
                    "bank": bank,
                    "cycle": name,
                    "beta": beta,
                    "cost_start": series.get(cycle[0]),
                    "cost_end": series.get(cycle[1]),
                    "tiers": ",".join(sorted(tiers)),
                }
            )

    return pd.DataFrame(rows)


def _report(
    costs: pd.DataFrame,
    betas: pd.DataFrame,
    aggregate: dict[date, float],
    policy: dict[date, float],
) -> str:
    lines: list[str] = ["Gate criterion G4 and benchmark check", ""]

    excluded = costs[costs["tier"] == MetricTier.EXCLUDED.value]

    lines.append("Tier coverage across bank-quarters")
    for tier, count in costs["tier"].value_counts().sort_index().items():
        lines.append(f"  tier {tier}: {count} bank-quarters")
    banks_at_tier1 = costs[costs["tier"] == MetricTier.TIER_1.value]["bank"].nunique()
    lines.append(f"  banks reaching tier 1: {banks_at_tier1} of {costs['bank'].nunique()}")
    if not excluded.empty:
        lines.append("  excluded for incomplete reconstructed numerator:")
        for bank, group in excluded.groupby("bank"):
            worst = group["component_coverage"].min()
            lines.append(f"    {bank} ({len(group)} quarters, coverage as low as {worst:.0%})")
    lines.append("")

    test = betas[betas["cycle"] == "test"].set_index("bank")
    lines.append("G4: direct bank against branch-funded regional, test cycle")
    ally = test["beta"].get("Ally Financial Inc.")
    zions = test["beta"].get("Zions Bancorporation, National Association")
    for label, value in (("Ally Financial", ally), ("Zions Bancorporation", zions)):
        lines.append(f"  {label:24} beta {value:.3f}" if pd.notna(value) else f"  {label:24} n/a")
    if pd.notna(ally) and pd.notna(zions):
        margin = float(ally) - float(zions)
        verdict = "PASS" if margin >= G4_MINIMUM_MARGIN else "FAIL"
        lines.append(f"  margin {margin:+.3f}  ({verdict}, threshold {G4_MINIMUM_MARGIN:.2f})")
    lines.append("")

    lines.append("Benchmark: industry cumulative interest-bearing deposit beta")
    for name, cycle in CYCLES.items():
        beta = beta_over_cycle(aggregate, policy, cycle)
        if beta is None:
            lines.append(f"  {name:12} n/a")
            continue
        deviation = abs(beta - BENCHMARK_BETA)
        verdict = "within tolerance" if deviation <= BENCHMARK_TOLERANCE else "OUT OF RANGE"
        lines.append(f"  {name:12} {beta:.3f}  (published near {BENCHMARK_BETA:.2f}, {verdict})")
    lines.append("")

    lines.append("Cross-bank test-cycle betas")
    ranked = test["beta"].dropna().sort_values(ascending=False)
    for ranked_bank, beta in ranked.items():
        lines.append(f"  {beta:>6.3f}  {ranked_bank}")

    return "\n".join(lines)


def bank_names() -> dict[int, Bank]:
    return {bank.cik: bank for bank in FEASIBILITY_SAMPLE}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    _, _, report = run(args.output_dir)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
