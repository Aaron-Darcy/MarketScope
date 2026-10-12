"""Milestone 3: does a bank's ordering by deposit beta in one cycle persist into the next?

Implements specification 6.1 as pre-registered in decision 0034, before any cross-cycle
result had been computed. The sample rules, the statistic, the test, the interval and the
seed are all fixed there, and this script reads them from that entry rather than from
anything it finds in the data. A departure from them has to be recorded as a new decision
before its result is reported.

Usage:
    python analysis/milestone3/persistence.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.cycles import STUDY_CYCLES
from marketscope.ranking import (
    Interval,
    average_ranks,
    bootstrap_interval,
    ols,
    pearson,
    permutation_p_value,
    quartiles,
    spearman,
    transition_matrix,
)
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

SEED = 20261010
PERMUTATIONS = 100_000
RESAMPLES = 10_000
SIGNIFICANCE = 0.05
COVERAGE_FLOOR = 0.80

# Filers two or more quartiles apart between the cycles are material deviators.
DEVIATION = 2

CALIBRATION, TEST = STUDY_CYCLES


@dataclass(frozen=True)
class CycleBeta:
    beta: float | None
    tier: str | None
    partial: bool
    tier_1_coverage: float
    material_event: bool


@dataclass(frozen=True)
class Filer:
    cik: int
    registrant_name: str
    rank: int | None
    cycles: dict[str, CycleBeta]

    def beta(self, cycle: str) -> float:
        value = self.cycles[cycle].beta
        if value is None:
            raise ValueError(f"{self.registrant_name} has no {cycle} beta")
        return value


def read_filers(connection: duckdb.DuckDBPyConnection) -> list[Filer]:
    rows = connection.execute(
        """
        select
            betas.cik,
            members.registrant_name,
            members.rank,
            betas.cycle_name,
            betas.deposit_beta,
            betas.metric_tier,
            betas.partial_cycle,
            betas.tier_1_quarters::double / betas.cycle_quarters,
            betas.material_event_in_cycle
        from fct_deposit_beta as betas
        join dim_bank as members using (cik)
        order by betas.cik
        """
    ).fetchall()

    by_cik: dict[int, dict[str, CycleBeta]] = {}
    names: dict[int, tuple[str, int | None]] = {}
    for cik, name, rank, cycle, beta, tier, partial, coverage, material in rows:
        by_cik.setdefault(cik, {})[cycle] = CycleBeta(beta, tier, partial, coverage, material)
        names[cik] = (name, rank)

    return [
        Filer(cik=cik, registrant_name=names[cik][0], rank=names[cik][1], cycles=cycles)
        for cik, cycles in by_cik.items()
    ]


def in_headline(filer: Filer) -> bool:
    """The five rules of specification 6.1."""
    if filer.rank is None:
        return False
    for cycle in STUDY_CYCLES:
        measured = filer.cycles[cycle]
        if measured.beta is None or measured.tier != "1":
            return False
        if measured.tier_1_coverage < COVERAGE_FLOOR:
            return False
        if measured.partial or measured.material_event:
            return False
    return True


@dataclass(frozen=True)
class Result:
    filers: int
    spearman: float
    p_value: float
    interval: Interval


def assess(sample: list[Filer]) -> Result:
    calibration = [filer.beta(CALIBRATION) for filer in sample]
    test = [filer.beta(TEST) for filer in sample]
    return Result(
        filers=len(sample),
        spearman=spearman(calibration, test),
        p_value=permutation_p_value(calibration, test, permutations=PERMUTATIONS, seed=SEED),
        interval=bootstrap_interval(calibration, test, resamples=RESAMPLES, seed=SEED),
    )


def filer_table(sample: list[Filer]) -> pd.DataFrame:
    calibration = [filer.beta(CALIBRATION) for filer in sample]
    test = [filer.beta(TEST) for filer in sample]
    frame = pd.DataFrame(
        {
            "registrant_name": [filer.registrant_name for filer in sample],
            "calibration_beta": calibration,
            "test_beta": test,
            "calibration_rank": average_ranks(calibration),
            "test_rank": average_ranks(test),
            "calibration_quartile": quartiles(calibration),
            "test_quartile": quartiles(test),
        }
    )
    frame["quartile_shift"] = frame["test_quartile"] - frame["calibration_quartile"]
    return frame.sort_values("calibration_beta").reset_index(drop=True)


def summarise(result: Result, table: pd.DataFrame) -> str:
    supported = result.spearman > 0 and result.p_value < SIGNIFICANCE
    matrix = transition_matrix(list(table["calibration_quartile"]), list(table["test_quartile"]))
    same = sum(matrix[i][i] for i in range(len(matrix)))
    fit = ols(list(table["calibration_beta"]), list(table["test_beta"]))
    deviators = table[table["quartile_shift"].abs() >= DEVIATION]

    lines = [
        "Cross-cycle persistence of deposit beta, as pre-registered in specification 6.1",
        "",
        f"Headline sample: {result.filers} filers",
        f"  Spearman, calibration against test:  {result.spearman:+.3f}",
        f"  one-sided permutation p ({PERMUTATIONS:,} permutations): {result.p_value:.4f}",
        f"  95% bootstrap interval ({RESAMPLES:,} resamples): "
        f"{result.interval.low:+.3f} to {result.interval.high:+.3f}"
        + (
            f", {result.interval.undefined} undefined resamples left out"
            if result.interval.undefined
            else ""
        ),
        f"  seed {SEED}",
        "",
        "Persistence "
        + (
            "supported: the correlation is positive with p below 0.05."
            if supported
            else "not shown: the correlation does not clear p below 0.05. At this sample "
            "size that is not evidence of its absence."
        ),
        "",
        "Quartile transitions, calibration quartile (rows) to test quartile (columns):",
        "        Q1  Q2  Q3  Q4",
    ]
    for index, counts in enumerate(matrix, start=1):
        lines.append(f"  Q{index}  " + "".join(f"{count:>4}" for count in counts))
    lines += [
        f"  Same quartile in both cycles: {same} of {result.filers} "
        f"({same / result.filers:.0%}, against 25% by chance)",
        "",
        "Secondary, levels not expected to transfer:",
        f"  Pearson: {pearson(list(table['calibration_beta']), list(table['test_beta'])):+.3f}",
        f"  OLS, test on calibration: slope {fit.slope:.3f}, intercept {fit.intercept:.3f}, "
        f"R squared {fit.r_squared:.3f}",
        f"  Median beta: calibration {table['calibration_beta'].median():.3f}, "
        f"test {table['test_beta'].median():.3f}",
        "",
        f"Material deviators, {DEVIATION} or more quartiles apart: {len(deviators)}",
    ]
    for _, row in deviators.iterrows():
        lines.append(
            f"  {str(row['registrant_name'])[:38]:<38} calibration {row['calibration_beta']:.3f} "
            f"(Q{row['calibration_quartile']}), test {row['test_beta']:.3f} "
            f"(Q{row['test_quartile']})"
        )

    lines += ["", f"{'filer':<40} {'calibration':>11} {'test':>7} {'Qc':>3} {'Qt':>3}"]
    for _, row in table.iterrows():
        lines.append(
            f"{str(row['registrant_name'])[:40]:<40} {row['calibration_beta']:>11.3f} "
            f"{row['test_beta']:>7.3f} {row['calibration_quartile']:>3} {row['test_quartile']:>3}"
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
        filers = read_filers(connection)
    finally:
        connection.close()

    sample = [filer for filer in filers if in_headline(filer)]
    result = assess(sample)
    table = filer_table(sample)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_dir / "persistence.csv", index=False)
    report = summarise(result, table)
    print(report)
    (args.output_dir / "persistence.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
