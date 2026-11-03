from __future__ import annotations

from dataclasses import replace
from datetime import date

import duckdb
import pytest

from marketscope import persistence
from marketscope.cycles import RateCycle
from marketscope.persistence import (
    CALIBRATION,
    COMPARISON_COLUMNS,
    HEADLINE,
    RECOVERED,
    RESULT_COLUMNS,
    TEST,
    VARIANTS,
    CycleBeta,
    Filer,
    RecoveredBeta,
    comparison_frame,
    eligible,
    read_recovered,
    recovered_beta,
    recovered_frame,
    result_frame,
)
from marketscope.ranking import spearman
from marketscope.regulatory import REFERENCE_MAP


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


def _ranked(
    cik: int, calibration: float, test: float, *, rank: int | None = 10, acquired: bool = False
) -> Filer:
    filer = _filer(
        rank=rank,
        calibration=_cycle(beta=calibration, material_event=acquired),
        test=_cycle(beta=test),
    )
    return replace(filer, cik=cik, registrant_name=f"Bank {cik}")


def test_the_comparison_places_headline_filers_by_rank_and_quartile() -> None:
    filers = [_ranked(cik, 0.1 * cik, 0.1 * cik) for cik in range(1, 5)]
    filers[0] = _ranked(1, 0.1, 0.9)

    frame = comparison_frame(filers).set_index("cik")

    assert frame["calibration_rank"].tolist() == [1.0, 2.0, 3.0, 4.0]
    assert frame["test_rank"].tolist() == [4.0, 1.0, 2.0, 3.0]
    assert frame["quartile_shift"].tolist() == [3, -1, -1, -1]
    assert frame["material_deviator"].tolist() == [True, False, False, False]


def test_a_filer_outside_the_headline_has_no_place_in_it() -> None:
    outside = _ranked(9, 0.5, 0.5, rank=None)
    frame = comparison_frame([_ranked(1, 0.2, 0.3), _ranked(2, 0.4, 0.6), outside])

    row = frame[frame["cik"] == 9].iloc[0]
    assert not row["in_headline"]
    assert frame[frame["cik"] == 9][["calibration_rank", "test_quartile"]].isna().all(axis=None)
    assert row["calibration_beta"] == 0.5


def test_each_variant_column_follows_the_variant_it_is_named_for() -> None:
    acquirer = _ranked(3, 0.3, 0.3, acquired=True)
    frame = comparison_frame([_ranked(1, 0.2, 0.3), _ranked(2, 0.4, 0.6), acquirer])

    variant_columns = [column for column in COMPARISON_COLUMNS if column.startswith("in_r")]
    assert variant_columns == [f"in_{key.lower()}" for key in VARIANTS]
    row = frame[frame["cik"] == 3].iloc[0]
    assert not row["in_headline"]
    assert [bool(row[column]) for column in variant_columns] == [
        eligible(acquirer, rules) for _, rules in VARIANTS.values()
    ]


@pytest.fixture
def quick_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(persistence, "PERMUTATIONS", 99)
    monkeypatch.setattr(persistence, "RESAMPLES", 99)


@pytest.mark.usefixtures("quick_statistics")
def test_the_result_frame_reports_every_sample_in_reporting_order() -> None:
    headline = [_ranked(cik, 0.1 * cik, 0.1 * cik + 0.05) for cik in range(1, 5)]
    acquirer = _ranked(5, 0.6, 0.2, acquired=True)
    recovered = {
        "Failed Bank": RecoveredBeta(calibration=0.7, test=0.8, test_end=date(2023, 3, 31))
    }

    frame = result_frame([*headline, acquirer], recovered).set_index("sample")

    assert list(frame.columns) == list(RESULT_COLUMNS[1:])
    assert list(frame.index) == ["headline", "R1", "R2", "R3", "R4", "R4+recovered"]
    assert frame["filers"].tolist() == [4, 4, 5, 4, 4, 5]
    assert frame.loc["headline", "spearman"] == pytest.approx(1.0)
    assert frame.loc["R2", "spearman"] == pytest.approx(
        spearman([0.1, 0.2, 0.3, 0.4, 0.6], [0.15, 0.25, 0.35, 0.45, 0.2])
    )
    assert frame.loc["R4+recovered", "description"] == (
        "R4 with Failed Bank recovered from Call Reports"
    )
    assert frame["supported"].dtype == bool


def test_the_result_frame_refuses_a_recovered_sample_without_its_banks() -> None:
    with pytest.raises(ValueError, match="recovered sample"):
        result_frame([_ranked(cik, 0.1 * cik, 0.1 * cik) for cik in range(1, 4)], {})


def _regulatory_warehouse(costs: dict[str, dict[date, float]]) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute(
        "create table dim_rate_cycle (cycle_name varchar, start_quarter date, "
        "end_quarter date, start_rate_fraction double, end_rate_fraction double)"
    )
    for cycle in CYCLES.values():
        connection.execute(
            "insert into dim_rate_cycle values (?, ?, ?, ?, ?)",
            [cycle.name, cycle.start, cycle.end, cycle.start_rate, cycle.end_rate],
        )
    connection.execute("create table int_rate_cycles (quarter_end date, rate_fraction double)")
    connection.executemany("insert into int_rate_cycles values (?, ?)", list(POLICY.items()))
    connection.execute(
        "create table int_regulatory_deposit_cost "
        "(group_key varchar, quarter_end date, cost_of_deposits double)"
    )
    for key, series in costs.items():
        connection.executemany(
            "insert into int_regulatory_deposit_cost values (?, ?, ?)",
            [(key, quarter, cost) for quarter, cost in series.items()],
        )
    return connection


QUALIFYING = _costs(
    (date(2015, 12, 31), 0.005),
    (date(2016, 3, 31), 0.006),
    (date(2016, 6, 30), 0.007),
    (date(2022, 3, 31), 0.002),
    (date(2022, 6, 30), 0.006),
    (date(2022, 9, 30), 0.017),
)


def test_each_recovered_bank_is_read_under_its_name() -> None:
    connection = _regulatory_warehouse(dict.fromkeys(RECOVERED, QUALIFYING))

    recovered = read_recovered(connection)

    assert list(recovered) == [REFERENCE_MAP[key].name for key in RECOVERED]
    assert all(beta.test_end == date(2022, 9, 30) for beta in recovered.values())


def test_a_recovered_bank_that_does_not_qualify_stops_the_read() -> None:
    """A bank missing from the recovered sample would report a different sample by name."""
    first, second = RECOVERED
    shortened = {quarter: cost for quarter, cost in QUALIFYING.items() if quarter.year > 2015}
    connection = _regulatory_warehouse({first: QUALIFYING, second: shortened})

    with pytest.raises(ValueError, match=REFERENCE_MAP[second].name):
        read_recovered(connection)


def test_each_recovered_bank_has_a_row_with_its_measured_test_end() -> None:
    frame = recovered_frame(
        {"Failed Bank": RecoveredBeta(calibration=0.3, test=0.5, test_end=date(2022, 12, 31))}
    )

    assert frame.to_dict("records") == [
        {
            "bank": "Failed Bank",
            "calibration_beta": 0.3,
            "test_beta": 0.5,
            "test_end": date(2022, 12, 31),
        }
    ]


def test_the_recovered_frame_refuses_to_be_empty() -> None:
    with pytest.raises(ValueError, match="recovered sample"):
        recovered_frame({})
