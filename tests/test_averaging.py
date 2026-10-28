from __future__ import annotations

from datetime import date

import pytest

from marketscope.averaging import (
    RECONCILIATION_TOLERANCE,
    Basis,
    GroupQuarter,
    averaging_frame,
    cost_on_reported_average,
    measurements,
    reconcile,
)

IB, NT = Basis.INTEREST_BEARING, Basis.NONTRANSACTION
QUARTERS = (date(2022, 12, 31), date(2023, 3, 31), date(2023, 6, 30), date(2023, 9, 30))


def _quarter(
    day: date,
    average: tuple[float, float],
    closing: tuple[float, float],
    *,
    group_key: str = "HC:1",
    institutions: int = 1,
    averaged: int = 1,
) -> GroupQuarter:
    return GroupQuarter(
        group_key=group_key,
        cik=1,
        quarter_end=day,
        institutions=institutions,
        averaged_institutions=averaged,
        average={IB: average[0], NT: average[1]},
        closing={IB: closing[0], NT: closing[1]},
    )


def _series(
    closings: list[tuple[float, float]], averages: list[tuple[float, float]], group_key: str
) -> list[GroupQuarter]:
    return [
        _quarter(day, average, closing, group_key=group_key)
        for day, average, closing in zip(QUARTERS, averages, closings, strict=True)
    ]


def test_the_endpoint_average_is_the_mean_of_the_two_quarter_ends() -> None:
    measured = measurements(
        [
            _quarter(QUARTERS[0], (90.0, 70.0), (100.0, 80.0)),
            _quarter(QUARTERS[1], (110.0, 85.0), (120.0, 90.0)),
        ]
    )

    [only] = measured["HC:1"]
    assert only.endpoint == {IB: 110.0, NT: 85.0}
    assert only.gap(IB) == pytest.approx(0.0)
    assert only.quarter.quarter_end == QUARTERS[1]


@pytest.mark.parametrize(
    ("current", "previous"),
    [((2, 1), (1, 1)), ((1, 1), (2, 1))],
)
def test_a_quarter_with_an_institution_missing_from_the_archives_is_not_measured(
    current: tuple[int, int], previous: tuple[int, int]
) -> None:
    quarters = [
        _quarter(
            QUARTERS[0], (1.0, 1.0), (1.0, 1.0), institutions=previous[0], averaged=previous[1]
        ),
        _quarter(QUARTERS[1], (1.0, 1.0), (1.0, 1.0), institutions=current[0], averaged=current[1]),
    ]

    assert measurements(quarters) == {}


def test_a_quarter_without_the_previous_quarter_end_is_not_measured() -> None:
    quarters = [
        _quarter(QUARTERS[0], (1.0, 1.0), (1.0, 1.0)),
        _quarter(QUARTERS[2], (1.0, 1.0), (1.0, 1.0)),
    ]

    assert measurements(quarters) == {}


def test_a_reported_average_that_is_not_positive_is_not_divided_by() -> None:
    quarters = [
        _quarter(QUARTERS[0], (1.0, 1.0), (1.0, 1.0)),
        _quarter(QUARTERS[1], (1.0, 0.0), (1.0, 1.0)),
    ]

    assert measurements(quarters) == {}


def test_the_interest_bearing_basis_is_preferred_where_both_reconcile() -> None:
    flat = [(100.0, 80.0)] * 4
    measured = measurements(_series(flat, flat, "HC:1"))["HC:1"]

    assert reconcile(measured).basis is IB


def test_a_group_whose_averages_exclude_reclassified_savings_reconciles_on_interest_bearing() -> (
    None
):
    """Its quarter-end nontransaction accounts hold balances its RC-K leaves out."""
    closings = [(100.0, 160.0)] * 4
    averages = [(100.0, 80.0)] * 4
    reconciliation = reconcile(measurements(_series(closings, averages, "HC:1"))["HC:1"])

    assert reconciliation.basis is IB
    assert reconciliation.gaps[NT] == pytest.approx(1.0)


def test_a_group_whose_averages_include_them_reconciles_on_nontransaction() -> None:
    closings = [(100.0, 160.0)] * 4
    averages = [(150.0, 160.0)] * 4
    reconciliation = reconcile(measurements(_series(closings, averages, "HC:1"))["HC:1"])

    assert reconciliation.basis is NT
    assert reconciliation.gaps[IB] == pytest.approx(100 / 150 - 1)


def test_one_quarter_of_sharp_movement_does_not_move_the_basis() -> None:
    """Averaging error in a single quarter is what is being measured, not a definition."""
    closings = [(100.0, 100.0), (100.0, 100.0), (60.0, 60.0), (60.0, 60.0)]
    averages = [(100.0, 100.0), (100.0, 100.0), (90.0, 90.0), (60.0, 60.0)]
    measured = measurements(_series(closings, averages, "HC:1"))["HC:1"]

    assert reconcile(measured).basis is IB
    assert measured[1].gap(IB) == pytest.approx(80 / 90 - 1)


@pytest.mark.parametrize(
    ("offset", "reconciles"),
    [(RECONCILIATION_TOLERANCE * 0.99, True), (RECONCILIATION_TOLERANCE * 1.01, False)],
)
def test_the_median_gap_is_held_to_the_tolerance(offset: float, reconciles: bool) -> None:
    closings = [(100.0 * (1 + offset), 100.0 * (1 + 3 * offset))] * 4
    averages = [(100.0, 100.0)] * 4
    reconciliation = reconcile(measurements(_series(closings, averages, "HC:1"))["HC:1"])

    assert (reconciliation.basis is IB) is reconciles
    assert reconciliation.basis is not NT


def test_the_frame_measures_each_group_on_its_own_basis_and_none_where_neither_holds() -> None:
    reconciled = _series([(100.0, 160.0)] * 4, [(100.0, 80.0)] * 4, "HC:1")
    unreconciled = _series([(100.0, 100.0)] * 4, [(120.0, 125.0)] * 4, "HC:2")

    frame = averaging_frame(reconciled + unreconciled)
    first = frame[frame["group_key"] == "HC:1"]
    second = frame[frame["group_key"] == "HC:2"]

    assert first["basis"].tolist() == ["interest_bearing"] * 3
    assert first["averaging_error"].tolist() == pytest.approx([0.0] * 3)
    assert second["basis"].isna().all()
    assert second["averaging_error"].isna().all()
    assert second["nontransaction_gap"].tolist() == pytest.approx([-0.2] * 3)


def test_the_closing_balance_alone_is_measured_against_the_same_average() -> None:
    quarters = [
        _quarter(QUARTERS[0], (100.0, 100.0), (100.0, 100.0)),
        _quarter(QUARTERS[1], (90.0, 90.0), (80.0, 80.0)),
    ]

    row = averaging_frame(quarters).iloc[0]

    assert row["averaging_error"] == pytest.approx(90 / 90 - 1)
    assert row["closing_only_error"] == pytest.approx(80 / 90 - 1)


def test_a_cost_is_restated_by_the_ratio_of_the_two_averages() -> None:
    """An endpoint average 5 percent above the reported one understates the cost by as much."""
    assert cost_on_reported_average(0.02, 0.05) == pytest.approx(0.021)
