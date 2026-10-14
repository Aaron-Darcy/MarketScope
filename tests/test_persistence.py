from __future__ import annotations

from dataclasses import replace

from marketscope.persistence import (
    CALIBRATION,
    HEADLINE,
    TEST,
    VARIANTS,
    CycleBeta,
    Filer,
    eligible,
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
