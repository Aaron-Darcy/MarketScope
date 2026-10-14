from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from marketscope.cycles import RateCycle
from marketscope.persistence import (
    CALIBRATION,
    HEADLINE,
    TEST,
    VARIANTS,
    CycleBeta,
    Filer,
    eligible,
    recovered_beta,
)


def _cycle(**changes: object) -> CycleBeta:
    measured = CycleBeta(
        beta=0.5,
        tier="1",
        partial=False,
        tier_1_quarters=14,
        tier_1_or_2_quarters=14,
        cycle_quarters=14,
        measured_quarters=14,
        material_event=False,
    )
    return replace(measured, **changes)  # type: ignore[arg-type]


def _filer(
    *,
    rank: int | None = 10,
    terminal: bool = False,
    between: bool = False,
    calibration: CycleBeta | None = None,
    test: CycleBeta | None = None,
) -> Filer:
    return Filer(
        cik=1,
        registrant_name="Example Bancorp",
        rank=rank,
        terminal=terminal,
        material_between_cycles=between,
        cycles={CALIBRATION: calibration or _cycle(), TEST: test or _cycle()},
    )


def test_a_filer_meeting_every_rule_enters_the_headline() -> None:
    assert eligible(_filer(), HEADLINE)


def test_a_pinned_filer_outside_the_ranked_fifty_is_left_out() -> None:
    assert not eligible(_filer(rank=None), HEADLINE)


def test_a_tier_2_beta_is_left_out_of_the_headline_and_admitted_by_r1() -> None:
    filer = _filer(test=_cycle(tier="2", tier_1_quarters=0))

    assert not eligible(filer, HEADLINE)
    assert eligible(filer, VARIANTS["R1"][1])


def test_coverage_below_the_floor_is_left_out() -> None:
    """Specification 7.2: 80 percent of a cycle's quarters at the headline tier."""
    assert not eligible(_filer(calibration=_cycle(tier_1_quarters=11)), HEADLINE)
    assert eligible(_filer(calibration=_cycle(tier_1_quarters=12)), HEADLINE)


def test_a_material_acquisition_inside_a_cycle_is_left_out_except_in_r2() -> None:
    filer = _filer(calibration=_cycle(material_event=True))

    assert not eligible(filer, HEADLINE)
    assert eligible(filer, VARIANTS["R2"][1])


def test_r3_also_leaves_out_an_acquisition_between_the_cycles() -> None:
    filer = _filer(between=True)

    assert eligible(filer, HEADLINE)
    assert not eligible(filer, VARIANTS["R3"][1])


def test_a_partial_test_cycle_enters_only_r4_and_only_for_a_terminal_filer() -> None:
    """SVB's test cycle ends at its last filing; coverage is judged over the quarters it
    filed."""
    shortened = _cycle(partial=True, tier_1_quarters=4, measured_quarters=4, cycle_quarters=8)

    assert not eligible(_filer(terminal=True, test=shortened), HEADLINE)
    assert eligible(_filer(terminal=True, test=shortened), VARIANTS["R4"][1])
    assert not eligible(_filer(terminal=False, test=shortened), VARIANTS["R4"][1])


def test_a_partial_calibration_cycle_is_never_admitted() -> None:
    shortened = _cycle(partial=True, tier_1_quarters=6, measured_quarters=6)

    assert not eligible(_filer(terminal=True, calibration=shortened), VARIANTS["R4"][1])


def test_a_missing_beta_is_left_out() -> None:
    assert not eligible(_filer(test=_cycle(beta=None)), HEADLINE)


CYCLES = {
    CALIBRATION: RateCycle(CALIBRATION, date(2015, 12, 31), date(2016, 6, 30), 0.001, 0.011),
    TEST: RateCycle(TEST, date(2022, 3, 31), date(2022, 12, 31), 0.002, 0.042),
}
POLICY = {
    date(2015, 12, 31): 0.001,
    date(2016, 6, 30): 0.011,
    date(2022, 3, 31): 0.002,
    date(2022, 9, 30): 0.032,
    date(2022, 12, 31): 0.042,
}


def _costs(*quarters: tuple[date, float]) -> dict[date, float]:
    return dict(quarters)


def test_a_recovered_bank_is_measured_to_its_last_reported_test_quarter() -> None:
    """Signature filed its last Call Report for 2022Q3 in this example, inside the cycle."""
    costs = _costs(
        (date(2015, 12, 31), 0.005),
        (date(2016, 3, 31), 0.006),
        (date(2016, 6, 30), 0.007),
        (date(2022, 3, 31), 0.002),
        (date(2022, 6, 30), 0.006),
        (date(2022, 9, 30), 0.017),
    )

    beta = recovered_beta(costs, POLICY, CYCLES)

    assert beta is not None
    assert beta.calibration == pytest.approx(0.2)
    assert beta.test == pytest.approx(0.5)
    assert beta.test_end == date(2022, 9, 30)


def test_a_recovered_bank_needs_a_complete_calibration_cycle() -> None:
    costs = _costs(
        (date(2015, 12, 31), 0.005),
        (date(2016, 3, 31), 0.006),
        (date(2022, 3, 31), 0.002),
        (date(2022, 12, 31), 0.022),
    )

    assert recovered_beta(costs, POLICY, CYCLES) is None


def test_a_recovered_bank_below_the_coverage_floor_is_refused() -> None:
    costs = _costs(
        (date(2015, 12, 31), 0.005),
        (date(2016, 6, 30), 0.007),
        (date(2022, 3, 31), 0.002),
        (date(2022, 12, 31), 0.022),
    )

    assert recovered_beta(costs, POLICY, CYCLES) is None
