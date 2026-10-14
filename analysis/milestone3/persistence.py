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
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.cycles import read_policy_rate, read_study_cycles
from marketscope.persistence import (
    CALIBRATION,
    HEADLINE,
    PERMUTATIONS,
    RESAMPLES,
    SEED,
    SIGNIFICANCE,
    TEST,
    VARIANTS,
    Filer,
    RecoveredBeta,
    Result,
    assess,
    assess_pairs,
    eligible,
    read_filers,
    recovered_beta,
)
from marketscope.ranking import (
    average_ranks,
    ols,
    pearson,
    quartiles,
    transition_matrix,
)
from marketscope.regulatory import REFERENCE_MAP
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

# Filers two or more quartiles apart between the cycles are material deviators.
DEVIATION = 2

# Decision 0034 adds these two to R4 once recovered from regulatory data. Neither filed with
# the SEC, so their betas come from Call Reports, which section 7.5 of the methodology shows
# order banks as the XBRL figures do.
RECOVERED: tuple[str, ...] = ("BANK:59017", "BANK:57053")


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


def summarise_variants(headline: list[Filer], variants: dict[str, list[Filer]]) -> str:
    """Each pre-registered variant beside the headline, with the filers it adds or drops."""
    base = {filer.cik for filer in headline}
    lines = [
        "Robustness variants, pre-registered beside the headline and not replacing it",
        "",
        f"{'':<4}{'variant':<56}{'filers':>7}{'Spearman':>10}{'p':>8}   95% interval",
    ]
    details: list[str] = []
    for name, sample in variants.items():
        result = assess(sample)
        lines.append(
            f"{name:<4}{VARIANTS[name][0]:<56}{result.filers:>7}{result.spearman:>+10.3f}"
            f"{result.p_value:>8.4f}   {result.interval.low:+.3f} to {result.interval.high:+.3f}"
        )
        cohort = {filer.cik: filer for filer in sample}
        added = sorted(cohort[cik].registrant_name for cik in cohort.keys() - base)
        dropped = sorted(filer.registrant_name for filer in headline if filer.cik not in cohort)
        details.append(f"{name}: adds {', '.join(added) or 'none'}")
        details.append(f"    drops {', '.join(dropped) or 'none'}")

    lines += ["", *details]

    survivors = variants["R4"]
    calibration = average_ranks([filer.beta(CALIBRATION) for filer in survivors])
    test = average_ranks([filer.beta(TEST) for filer in survivors])
    lines += [
        "",
        f"Terminal filers in R4, ranked among its {len(survivors)} filers, 1 the slowest:",
    ]
    for filer, calibration_rank, test_rank in zip(survivors, calibration, test, strict=True):
        if filer.terminal and filer.cycles[TEST].partial:
            lines.append(
                f"  {filer.registrant_name[:38]:<38} calibration {filer.beta(CALIBRATION):.3f} "
                f"(rank {calibration_rank:g}), test to its last quarter "
                f"{filer.beta(TEST):.3f} (rank {test_rank:g})"
            )
    return "\n".join(lines)


def summarise_recovered(survivors: list[Filer], recovered: dict[str, RecoveredBeta]) -> str:
    """R4 with the banks EDGAR does not hold, as decision 0034 provides once recovered."""
    names = [filer.registrant_name for filer in survivors] + list(recovered)
    calibration = [filer.beta(CALIBRATION) for filer in survivors] + [
        beta.calibration for beta in recovered.values()
    ]
    test = [filer.beta(TEST) for filer in survivors] + [beta.test for beta in recovered.values()]
    result = assess_pairs(calibration, test)
    calibration_ranks, test_ranks = average_ranks(calibration), average_ranks(test)

    lines = [
        "R4 with First Republic and Signature, recovered from Call Reports",
        f"  filers {result.filers}, Spearman {result.spearman:+.3f}, one-sided p "
        f"{result.p_value:.4f}, 95% interval {result.interval.low:+.3f} to "
        f"{result.interval.high:+.3f}",
        f"  ranked among {result.filers}, 1 the slowest:",
    ]
    for name, beta in recovered.items():
        index = names.index(name)
        lines.append(
            f"  {name:<38} calibration {beta.calibration:.3f} (rank {calibration_ranks[index]:g}), "
            f"test to {beta.test_end} {beta.test:.3f} (rank {test_ranks[index]:g})"
        )
    return "\n".join(lines)


def read_recovered(connection: duckdb.DuckDBPyConnection) -> dict[str, RecoveredBeta]:
    cycles = read_study_cycles(connection)
    policy = read_policy_rate(connection)
    recovered: dict[str, RecoveredBeta] = {}
    for key in RECOVERED:
        rows = connection.execute(
            "select quarter_end, cost_of_deposits from int_regulatory_deposit_cost "
            "where group_key = ?",
            [key],
        ).fetchall()
        beta = recovered_beta(dict(rows), policy, cycles)
        if beta is None:
            raise ValueError(f"{REFERENCE_MAP[key].name} does not qualify for R4")
        recovered[REFERENCE_MAP[key].name] = beta
    return recovered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    connection = store.connect(args.database, read_only=True)
    try:
        filers = read_filers(connection)
        recovered = read_recovered(connection)
    finally:
        connection.close()

    sample = [filer for filer in filers if eligible(filer, HEADLINE)]
    result = assess(sample)
    table = filer_table(sample)

    variants = {
        name: [filer for filer in filers if eligible(filer, rules)]
        for name, (_, rules) in VARIANTS.items()
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_dir / "persistence.csv", index=False)
    report = "\n\n".join(
        (
            summarise(result, table),
            summarise_variants(sample, variants),
            summarise_recovered(variants["R4"], recovered),
        )
    )
    print(report)
    (args.output_dir / "persistence.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
