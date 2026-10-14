"""The persistence analysis as pre-registered in specification 6.1 and decision 0034.

Every constant and rule here was fixed before the cross-cycle result was computed. The
analysis scripts read them from this module so that the headline, its variants and any check
run against another source use one definition of the sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb

from marketscope.cycles import STUDY_CYCLES, RateCycle
from marketscope.metrics import cumulative_beta
from marketscope.ranking import Interval, bootstrap_interval, permutation_p_value, spearman

SEED = 20261010
PERMUTATIONS = 100_000
RESAMPLES = 10_000
SIGNIFICANCE = 0.05
COVERAGE_FLOOR = 0.80

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
