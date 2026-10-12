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
    tier_1_quarters: int
    tier_1_or_2_quarters: int
    cycle_quarters: int
    measured_quarters: int
    material_event: bool

    def coverage(self, tiers: frozenset[str]) -> float:
        """Share of the quarters measured that resolve at the given tiers.

        For a partial cycle the quarters measured run to the filer's last resolved quarter,
        so coverage is judged over the quarters it filed.
        """
        covered = self.tier_1_or_2_quarters if "2" in tiers else self.tier_1_quarters
        quarters = self.measured_quarters if self.partial else self.cycle_quarters
        return covered / quarters


@dataclass(frozen=True)
class Filer:
    cik: int
    registrant_name: str
    rank: int | None
    terminal: bool
    material_between_cycles: bool
    cycles: dict[str, CycleBeta]

    def beta(self, cycle: str) -> float:
        value = self.cycles[cycle].beta
        if value is None:
            raise ValueError(f"{self.registrant_name} has no {cycle} beta")
        return value


def read_filers(connection: duckdb.DuckDBPyConnection) -> list[Filer]:
    rows = connection.execute(
        """
        with between_cycles as (

            select distinct events.cik
            from bank_entity_events as events
            where events.material
              and events.event_quarter > (
                  select end_quarter from dim_rate_cycle where cycle_name = 'calibration')
              and events.event_quarter < (
                  select start_quarter from dim_rate_cycle where cycle_name = 'test')

        )

        select
            betas.cik,
            members.registrant_name,
            members.rank,
            members.is_terminal,
            betas.cik in (select cik from between_cycles),
            betas.cycle_name,
            betas.deposit_beta,
            betas.metric_tier,
            betas.partial_cycle,
            betas.tier_1_quarters,
            betas.tier_1_or_2_quarters,
            betas.cycle_quarters,
            date_diff('quarter', betas.start_quarter, betas.measured_end_quarter) + 1,
            betas.material_event_in_cycle
        from fct_deposit_beta as betas
        join dim_bank as members using (cik)
        order by betas.cik
        """
    ).fetchall()

    by_cik: dict[int, dict[str, CycleBeta]] = {}
    members: dict[int, tuple[str, int | None, bool, bool]] = {}
    for cik, name, rank, terminal, between, cycle, *measured in rows:
        by_cik.setdefault(cik, {})[cycle] = CycleBeta(*measured)
        members[cik] = (name, rank, terminal, between)

    return [
        Filer(
            cik=cik,
            registrant_name=members[cik][0],
            rank=members[cik][1],
            terminal=members[cik][2],
            material_between_cycles=members[cik][3],
            cycles=cycles,
        )
        for cik, cycles in by_cik.items()
    ]


@dataclass(frozen=True)
class Rules:
    """The sample rules of specification 6.1, with the switches its variants turn."""

    tiers: frozenset[str] = frozenset({"1"})
    exclude_material_in_cycle: bool = True
    exclude_material_between_cycles: bool = False
    admit_terminal_partial_test: bool = False


HEADLINE = Rules()

VARIANTS: dict[str, tuple[str, Rules]] = {
    "R1": ("tiers 1 and 2", Rules(tiers=frozenset({"1", "2"}))),
    "R2": (
        "material acquisitions inside a cycle included",
        Rules(exclude_material_in_cycle=False),
    ),
    "R3": (
        "material acquisitions between the cycles also excluded",
        Rules(exclude_material_between_cycles=True),
    ),
    "R4": (
        "terminal filers with a test cycle cut short added",
        Rules(admit_terminal_partial_test=True),
    ),
}


def eligible(filer: Filer, rules: Rules) -> bool:
    if filer.rank is None:
        return False
    if rules.exclude_material_between_cycles and filer.material_between_cycles:
        return False
    for cycle in STUDY_CYCLES:
        measured = filer.cycles[cycle]
        if measured.beta is None or measured.tier not in rules.tiers:
            return False
        if measured.partial and not (
            rules.admit_terminal_partial_test and filer.terminal and cycle == TEST
        ):
            return False
        if measured.coverage(rules.tiers) < COVERAGE_FLOOR:
            return False
        if rules.exclude_material_in_cycle and measured.material_event:
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

    sample = [filer for filer in filers if eligible(filer, HEADLINE)]
    result = assess(sample)
    table = filer_table(sample)

    variants = {
        name: [filer for filer in filers if eligible(filer, rules)]
        for name, (_, rules) in VARIANTS.items()
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_dir / "persistence.csv", index=False)
    report = summarise(result, table) + "\n\n" + summarise_variants(sample, variants)
    print(report)
    (args.output_dir / "persistence.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
