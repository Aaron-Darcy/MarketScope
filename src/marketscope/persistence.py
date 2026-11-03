"""The persistence analysis as pre-registered in specification 6.1 and decision 0034.

Every constant and rule here was fixed before the cross-cycle result was computed. The
analysis scripts read them from this module so that the headline, its variants and any check
run against another source use one definition of the sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd

from marketscope.cycles import STUDY_CYCLES, RateCycle, read_policy_rate, read_study_cycles
from marketscope.metrics import cumulative_beta
from marketscope.ranking import (
    Interval,
    average_ranks,
    bootstrap_interval,
    permutation_p_value,
    quartiles,
    spearman,
)
from marketscope.regulatory import REFERENCE_MAP

SEED = 20261010
PERMUTATIONS = 100_000
RESAMPLES = 10_000
SIGNIFICANCE = 0.05
COVERAGE_FLOOR = 0.80

# Specification 6 reports material deviators: filers two or more quartiles apart between the
# cycles.
DEVIATION = 2

CALIBRATION, TEST = STUDY_CYCLES

# Decision 0034 adds these two to R4 once recovered from regulatory data. Neither filed with
# the SEC, so their betas come from Call Reports, which methodology 7.5 shows order banks as
# the XBRL figures do.
RECOVERED: tuple[str, ...] = ("BANK:59017", "BANK:57053")


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


COMPARISON_COLUMNS: tuple[str, ...] = (
    "cik",
    "registrant_name",
    "rank",
    "calibration_beta",
    "test_beta",
    "calibration_tier",
    "test_tier",
    "in_headline",
    "in_r1",
    "in_r2",
    "in_r3",
    "in_r4",
    "calibration_rank",
    "test_rank",
    "calibration_quartile",
    "test_quartile",
    "quartile_shift",
    "material_deviator",
)


def comparison_frame(filers: list[Filer]) -> pd.DataFrame:
    """One row per member: its cycle betas, the pre-registered samples it enters, and its
    rank and quartile within the headline sample, rank 1 the slowest repricer.

    Ranks and quartiles are those the persistence analysis reports and are null outside
    the headline, since a place in a sample the filer is not in has no meaning.
    """
    sample = [filer for filer in filers if eligible(filer, HEADLINE)]
    calibration = [filer.beta(CALIBRATION) for filer in sample]
    test = [filer.beta(TEST) for filer in sample]
    places = {
        filer.cik: place
        for filer, *place in zip(
            sample,
            average_ranks(calibration),
            average_ranks(test),
            quartiles(calibration),
            quartiles(test),
            strict=True,
        )
    }

    rows: list[tuple[object, ...]] = []
    for filer in sorted(filers, key=lambda member: member.cik):
        place = places.get(filer.cik)
        shift = int(place[3] - place[2]) if place else None
        rows.append(
            (
                filer.cik,
                filer.registrant_name,
                filer.rank,
                filer.cycles[CALIBRATION].beta,
                filer.cycles[TEST].beta,
                filer.cycles[CALIBRATION].tier,
                filer.cycles[TEST].tier,
                place is not None,
                *(eligible(filer, rules) for _, rules in VARIANTS.values()),
                *(place if place else (None, None, None, None)),
                shift,
                None if shift is None else abs(shift) >= DEVIATION,
            )
        )
    frame = pd.DataFrame(rows, columns=list(COMPARISON_COLUMNS))
    return frame.astype(
        {
            "rank": "Int64",
            "calibration_quartile": "Int64",
            "test_quartile": "Int64",
            "quartile_shift": "Int64",
            "material_deviator": "boolean",
        }
    )


@dataclass(frozen=True)
class Result:
    filers: int
    spearman: float
    p_value: float
    interval: Interval


def assess_pairs(calibration: list[float], test: list[float]) -> Result:
    """The pre-registered statistic, test and interval for paired cycle betas."""
    return Result(
        filers=len(calibration),
        spearman=spearman(calibration, test),
        p_value=permutation_p_value(calibration, test, permutations=PERMUTATIONS, seed=SEED),
        interval=bootstrap_interval(calibration, test, resamples=RESAMPLES, seed=SEED),
    )


def assess(sample: list[Filer]) -> Result:
    return assess_pairs(
        [filer.beta(CALIBRATION) for filer in sample], [filer.beta(TEST) for filer in sample]
    )


@dataclass(frozen=True)
class RecoveredBeta:
    calibration: float
    test: float
    test_end: date


def recovered_beta(
    costs: dict[date, float], policy: dict[date, float], cycles: dict[str, RateCycle]
) -> RecoveredBeta | None:
    """Cycle betas for a bank EDGAR does not hold, from its regulatory cost of deposits.

    The sample rules applied over the quarters the bank reported, as R4 applies them to a
    terminal filer: the calibration cycle complete, the test cycle measured to its last
    reported quarter where the bank failed inside it, and each covering at least 80 percent
    of the quarters measured. None where the bank does not qualify.
    """
    betas: dict[str, float] = {}
    test_end: date | None = None
    for name, cycle in cycles.items():
        reported = [quarter for quarter in cycle.quarters() if quarter in costs]
        if cycle.start not in costs or not reported:
            return None
        end = cycle.end if cycle.end in costs else max(reported)
        if end != cycle.end and name != TEST:
            return None
        measured = [quarter for quarter in cycle.quarters() if quarter <= end]
        if len([q for q in reported if q <= end]) / len(measured) < COVERAGE_FLOOR:
            return None
        beta = cumulative_beta(costs[cycle.start], costs[end], policy[cycle.start], policy[end])
        if beta is None:
            return None
        betas[name] = beta
        if name == TEST:
            test_end = end
    if test_end is None:
        return None
    return RecoveredBeta(calibration=betas[CALIBRATION], test=betas[TEST], test_end=test_end)


def read_recovered(connection: duckdb.DuckDBPyConnection) -> dict[str, RecoveredBeta]:
    """Cycle betas of the banks decision 0034 recovers into R4, keyed by name.

    Raises where a bank does not qualify, since the recovered sample is pre-registered with
    both and leaving one out would report a different sample under the same name.
    """
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


def supported(result: Result) -> bool:
    """The pre-registered reading: a positive correlation with p below the significance level."""
    return result.spearman > 0 and result.p_value < SIGNIFICANCE


HEADLINE_SAMPLE = "headline"
RECOVERED_SAMPLE = "R4+recovered"

RESULT_COLUMNS: tuple[str, ...] = (
    "sample",
    "description",
    "filers",
    "spearman",
    "p_value",
    "interval_low",
    "interval_high",
    "undefined_resamples",
    "supported",
)


def result_frame(filers: list[Filer], recovered: dict[str, RecoveredBeta]) -> pd.DataFrame:
    """The pre-registered statistic, test and interval for each sample, in reporting order:
    the headline, the four variants, and R4 with the banks recovered from Call Reports.
    """
    if not recovered:
        raise ValueError("The recovered sample needs the banks decision 0034 names")

    samples: list[tuple[str, str, Result]] = [
        (
            HEADLINE_SAMPLE,
            "headline sample",
            assess([filer for filer in filers if eligible(filer, HEADLINE)]),
        )
    ]
    for name, (description, rules) in VARIANTS.items():
        samples.append(
            (name, description, assess([filer for filer in filers if eligible(filer, rules)]))
        )

    survivors = [filer for filer in filers if eligible(filer, VARIANTS["R4"][1])]
    samples.append(
        (
            RECOVERED_SAMPLE,
            f"R4 with {' and '.join(recovered)} recovered from Call Reports",
            assess_pairs(
                [filer.beta(CALIBRATION) for filer in survivors]
                + [beta.calibration for beta in recovered.values()],
                [filer.beta(TEST) for filer in survivors]
                + [beta.test for beta in recovered.values()],
            ),
        )
    )

    rows = [
        (
            name,
            description,
            result.filers,
            result.spearman,
            result.p_value,
            result.interval.low,
            result.interval.high,
            result.interval.undefined,
            supported(result),
        )
        for name, description, result in samples
    ]
    return pd.DataFrame(rows, columns=list(RESULT_COLUMNS))


RECOVERED_COLUMNS: tuple[str, ...] = ("bank", "calibration_beta", "test_beta", "test_end")


def recovered_frame(recovered: dict[str, RecoveredBeta]) -> pd.DataFrame:
    """One row per bank recovered from Call Reports, with each cycle's beta and the quarter
    its test beta is measured to."""
    if not recovered:
        raise ValueError("The recovered sample needs the banks decision 0034 names")
    return pd.DataFrame(
        [(name, beta.calibration, beta.test, beta.test_end) for name, beta in recovered.items()],
        columns=list(RECOVERED_COLUMNS),
    )
