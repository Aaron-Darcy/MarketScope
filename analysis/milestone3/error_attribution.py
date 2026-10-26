"""Milestone 3: is the persistence result a property of banks or of their XBRL tagging?

Specification 6 asks how much of the cross-bank dispersion in betas is plausibly reporting
difference rather than behaviour. Every beta is recomputed from the Call Report cost of
deposits of the same group, over the same window and against the same policy move, so the
only thing that changes is the source of the figures.

Two comparisons follow. Within each cycle, the XBRL and regulatory betas are compared by rank
correlation: if they order banks the same way, the ordering is not an artefact of tagging.
Across cycles, the pre-registered headline correlation is computed again on regulatory betas
for the same 22 filers, with the same test and seed. That is a check on the source, not a
second headline: the headline is fixed in specification 6.1 and is not replaced by this.

Usage:
    python analysis/milestone3/error_attribution.py
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.cycles import STUDY_CYCLES
from marketscope.metrics import cumulative_beta
from marketscope.persistence import (
    CALIBRATION,
    HEADLINE,
    PERMUTATIONS,
    RESAMPLES,
    SEED,
    TEST,
    eligible,
    read_filers,
)
from marketscope.ranking import bootstrap_interval, permutation_p_value, spearman
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def read_betas(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Each member's XBRL beta beside the beta its regulatory group's figures give."""
    frame = connection.execute(
        """
        select
            betas.cik,
            betas.registrant_name,
            betas.cycle_name,
            betas.deposit_beta as xbrl_beta,
            betas.start_rate_fraction,
            betas.end_rate_fraction,
            opening.cost_of_deposits as regulatory_start_cost,
            closing.cost_of_deposits as regulatory_end_cost
        from fct_deposit_beta as betas
        left join int_regulatory_deposit_cost as opening
          on opening.cik = betas.cik
         and opening.quarter_end = betas.start_quarter
        left join int_regulatory_deposit_cost as closing
          on closing.cik = betas.cik
         and closing.quarter_end = betas.measured_end_quarter
        order by betas.cik, betas.cycle_name
        """
    ).df()
    frame["regulatory_beta"] = [
        None
        if pd.isna(start) or pd.isna(end)
        else cumulative_beta(start, end, start_rate, end_rate)
        for start, end, start_rate, end_rate in zip(
            frame["regulatory_start_cost"],
            frame["regulatory_end_cost"],
            frame["start_rate_fraction"],
            frame["end_rate_fraction"],
            strict=True,
        )
    ]
    return frame


def summarise(frame: pd.DataFrame, headline: set[int]) -> str:
    lines = [
        "Deposit betas on XBRL figures against betas on Call Report figures",
        "",
        "Within each cycle, filers with both betas:",
        f"{'':<22}{'filers':>7}{'Spearman':>10}{'median gap':>12}",
    ]
    for cycle in STUDY_CYCLES:
        for label, rows in (
            ("all", frame[frame["cycle_name"] == cycle]),
            ("headline", frame[(frame["cycle_name"] == cycle) & frame["cik"].isin(headline)]),
        ):
            both = rows.dropna(subset=["xbrl_beta", "regulatory_beta"])
            gap = (both["xbrl_beta"] - both["regulatory_beta"]).abs()
            lines.append(
                f"{cycle + ', ' + label:<22}{len(both):>7}"
                f"{spearman(list(both['xbrl_beta']), list(both['regulatory_beta'])):>+10.3f}"
                f"{statistics.median(gap):>12.3f}"
            )

    pivot = frame[frame["cik"].isin(headline)].pivot(
        index="cik", columns="cycle_name", values="regulatory_beta"
    )
    complete = pivot.dropna()
    calibration, test = list(complete[CALIBRATION]), list(complete[TEST])
    interval = bootstrap_interval(calibration, test, resamples=RESAMPLES, seed=SEED)
    lines += [
        "",
        "Cross-cycle correlation on Call Report betas, headline sample, same test and seed:",
        f"  filers with both regulatory betas: {len(complete)} of {len(headline)}",
        f"  Spearman {spearman(calibration, test):+.3f}, one-sided p "
        f"{permutation_p_value(calibration, test, permutations=PERMUTATIONS, seed=SEED):.4f}, "
        f"95% interval {interval.low:+.3f} to {interval.high:+.3f}",
        "  A check on the source of the figures, not a second headline.",
    ]

    gaps = frame.dropna(subset=["xbrl_beta", "regulatory_beta"]).assign(
        gap=lambda rows: (rows["xbrl_beta"] - rows["regulatory_beta"]).abs()
    )
    lines += ["", "Largest gaps between the two betas:"]
    for _, row in gaps.sort_values("gap", ascending=False).head(6).iterrows():
        lines.append(
            f"  {str(row['registrant_name'])[:38]:<38} {row['cycle_name']:<12} "
            f"XBRL {row['xbrl_beta']:.3f}, Call Report {row['regulatory_beta']:.3f}"
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
        frame = read_betas(connection)
        headline = {filer.cik for filer in read_filers(connection) if eligible(filer, HEADLINE)}
    finally:
        connection.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output_dir / "error_attribution.csv", index=False)
    report = summarise(frame, headline)
    print(report)
    (args.output_dir / "error_attribution.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
