"""Milestone 3: how far does the XBRL cost of deposits agree with the regulatory one?

Specification 5 states the accuracy of the tag mapping as a measured error against
regulatory filings rather than asserting it. Every bank-quarter the XBRL metric resolves is
paired with the cost of deposits computed from the Call Reports of the same holding
company's insured institutions, by the same arithmetic (decision 0035), so the difference
is a difference in the figures.

The difference still contains consolidation scope as well as tag mapping: a holding
company's filing includes deposits at non-US banking subsidiaries that file no Call Report,
and eliminates deposits one subsidiary holds at another. Groups of a single insured
institution are reported apart, because there the two measures cover the same bank.

Agreement is judged at 10 basis points. That is the cost error which moves a test-cycle
beta by 0.02 over its 5.2-point policy move, the scale decision 0032 already treats as
material, and it is fixed by that effect rather than by the distribution below.

Usage:
    python analysis/milestone3/regulatory_validation.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

AGREEMENT_BP = 10.0
BASIS_POINTS = 10_000.0


def read_pairs(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = connection.execute(
        """
        select
            costs.cik,
            members.registrant_name,
            costs.quarter_end,
            costs.metric_tier,
            costs.cost_of_deposits as xbrl_cost,
            regulatory.cost_of_deposits as regulatory_cost,
            regulatory.institutions,
            balances.interest_bearing_deposits as xbrl_interest_bearing,
            regulatory.interest_bearing_deposits as regulatory_interest_bearing
        from int_deposit_cost as costs
        join int_regulatory_deposit_cost as regulatory
          on regulatory.cik = costs.cik
         and regulatory.quarter_end = costs.quarter_end
        join dim_bank as members
          on members.cik = costs.cik
        left join int_deposit_balances as balances
          on balances.cik = costs.cik
         and balances.quarter_end = costs.quarter_end
        order by costs.cik, costs.quarter_end
        """
    ).df()
    frame["difference_bp"] = (frame["xbrl_cost"] - frame["regulatory_cost"]) * BASIS_POINTS
    frame["absolute_bp"] = frame["difference_bp"].abs()
    frame["agrees"] = frame["absolute_bp"] <= AGREEMENT_BP
    frame["base_ratio"] = frame["xbrl_interest_bearing"] / frame["regulatory_interest_bearing"]
    return frame


def describe(rows: pd.DataFrame) -> str:
    return (
        f"{len(rows):>6,} {rows['cik'].nunique():>7} {rows['absolute_bp'].median():>9.1f} "
        f"{rows['absolute_bp'].quantile(0.75):>7.1f} {rows['absolute_bp'].quantile(0.9):>7.1f} "
        f"{rows['agrees'].mean():>10.1%}"
    )


def summarise(frame: pd.DataFrame) -> str:
    header = (
        f"{'':<34}{'pairs':>6} {'filers':>7} {'median bp':>9} {'p75 bp':>7} {'p90 bp':>7} "
        f"{'within 10bp':>10}"
    )
    lines = [
        "XBRL cost of deposits against the Call Report figure, by the same arithmetic",
        "",
        header,
    ]
    for tier in ("1", "2", "3", "X"):
        rows = frame[frame["metric_tier"] == tier]
        if not rows.empty:
            lines.append(f"{'tier ' + tier:<34}{describe(rows)}")

    tier_one = frame[frame["metric_tier"] == "1"]
    lines += [
        "",
        "Tier 1, by how many insured institutions the group holds:",
        header,
        f"{'one institution':<34}{describe(tier_one[tier_one['institutions'] == 1])}",
        f"{'more than one':<34}{describe(tier_one[tier_one['institutions'] > 1])}",
        "",
        "Tier 1, interest-bearing base against the Call Report's, median absolute gap: "
        f"{(tier_one['base_ratio'] - 1).abs().median():.1%}",
        "",
        "Tier 1 filers whose median disagreement exceeds 10 basis points:",
    ]
    by_filer = (
        tier_one.groupby("registrant_name")
        .agg(
            pairs=("absolute_bp", "size"),
            median_bp=("absolute_bp", "median"),
            institutions=("institutions", "max"),
            base_gap=("base_ratio", lambda ratio: (ratio - 1).abs().median()),
        )
        .sort_values("median_bp", ascending=False)
    )
    for name, row in by_filer[by_filer["median_bp"] > AGREEMENT_BP].iterrows():
        lines.append(
            f"  {str(name)[:38]:<38} {int(row['pairs']):>4} quarters, median {row['median_bp']:.1f}bp, "
            f"up to {int(row['institutions'])} institutions, base gap {row['base_gap']:.1%}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    connection = store.connect(args.database, read_only=True)
    try:
        frame = read_pairs(connection)
    finally:
        connection.close()

    if frame.empty:
        print("No bank-quarter has both an XBRL and a regulatory cost of deposits.")
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output_dir / "regulatory_validation.csv", index=False)
    report = summarise(frame)
    print(report)
    (args.output_dir / "regulatory_validation.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
