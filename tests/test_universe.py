from __future__ import annotations

from datetime import date

import pytest

from marketscope.universe import (
    Candidate,
    EdgarCoverage,
    Exclusion,
    Filer,
    build_candidates,
    classify_coverage,
    count_foreign_annual_forms,
    deposit_share,
    peak_by_cik,
    rank,
    ten_k_history,
)


def _candidate(
    cik: int = 1,
    *,
    peak_assets: float = 100.0,
    share: float = 0.8,
    pays: bool = True,
) -> Candidate:
    return Candidate(
        cik=cik,
        entity_name=f"FILER {cik}",
        peak_assets=peak_assets,
        peak_deposits=peak_assets * share,
        deposit_share=share,
        pays_deposit_interest=pays,
    )


def _filer(candidate: Candidate, **overrides: object) -> Filer:
    defaults: dict[str, object] = {
        "registrant_name": "FILER",
        "sic": "6022",
        "sic_description": "State Commercial Banks",
        "tickers": (),
        "exchanges": (),
        "first_ten_k": date(2010, 12, 31),
        "last_ten_k": date(2023, 12, 31),
        "ten_k_count": 10,
        "foreign_annual_forms": 0,
        "coverage": EdgarCoverage.COVERED,
    }
    defaults.update(overrides)
    return Filer(candidate=candidate, **defaults)  # type: ignore[arg-type]


def test_peak_by_cik_takes_the_largest_value_across_frames() -> None:
    frames = {"CY2021Q4I": {1: 10.0, 2: 5.0}, "CY2022Q4I": {1: 8.0, 2: 9.0}}

    assert peak_by_cik(frames) == {1: 10.0, 2: 9.0}


def test_deposit_share_compares_within_a_period() -> None:
    """A filer whose assets and deposits peaked in different years is not credited with a
    ratio it never reported."""
    assets = {"CY2021Q4I": {1: 100.0}, "CY2022Q4I": {1: 1000.0}}
    deposits = {"CY2021Q4I": {1: 10.0}, "CY2022Q4I": {1: 20.0}}

    # Peak deposits over peak assets would give 20/100 = 0.20; neither period reported it.
    assert deposit_share(assets, deposits, 1) == pytest.approx(0.10)


def test_deposit_share_is_zero_when_deposits_are_never_reported() -> None:
    assets = {"CY2022Q4I": {1: 100.0}}

    assert deposit_share(assets, {"CY2022Q4I": {}}, 1) == 0.0


def test_deposit_share_ignores_a_period_with_non_positive_assets() -> None:
    assets = {"CY2022Q4I": {1: 0.0}}
    deposits = {"CY2022Q4I": {1: 50.0}}

    assert deposit_share(assets, deposits, 1) == 0.0


def test_build_candidates_marks_filers_reporting_deposit_interest() -> None:
    assets = {"CY2022Q4I": {1: 100.0, 2: 200.0}}
    deposits = {"CY2022Q4I": {1: 80.0, 2: 160.0}}

    candidates = {c.cik: c for c in build_candidates(assets, deposits, [1], {1: "ONE"})}

    assert candidates[1].pays_deposit_interest is True
    assert candidates[2].pays_deposit_interest is False
    assert candidates[1].entity_name == "ONE"
    assert candidates[2].entity_name == ""


def test_candidate_with_a_thin_deposit_base_is_excluded() -> None:
    assert _candidate(share=0.01).exclusion is Exclusion.NOT_DEPOSIT_FUNDED


def test_deposit_funded_candidate_that_pays_no_deposit_interest_is_excluded() -> None:
    """An insurer tags annuity contracts under the same Deposits concept a bank uses, so
    deposit funding alone does not identify a deposit-taking institution."""
    assert _candidate(share=0.4, pays=False).exclusion is Exclusion.NO_DEPOSIT_INTEREST


def test_deposit_taking_candidate_is_not_excluded() -> None:
    assert _candidate(share=0.4, pays=True).exclusion is None


def test_rank_orders_by_peak_assets_and_drops_excluded_candidates() -> None:
    candidates = [
        _candidate(1, peak_assets=100.0),
        _candidate(2, peak_assets=300.0),
        _candidate(3, peak_assets=200.0, pays=False),
        _candidate(4, peak_assets=250.0, share=0.001),
    ]

    assert [candidate.cik for candidate in rank(candidates)] == [2, 1]


def test_rank_breaks_ties_on_cik_so_the_order_is_stable() -> None:
    candidates = [_candidate(7, peak_assets=100.0), _candidate(3, peak_assets=100.0)]

    assert [candidate.cik for candidate in rank(candidates)] == [3, 7]


def test_ten_k_history_excludes_amendments_and_sorts() -> None:
    filings = [
        {"form": "10-K", "reportDate": "2022-12-31"},
        {"form": "10-K/A", "reportDate": "2021-12-31"},
        {"form": "10-Q", "reportDate": "2022-09-30"},
        {"form": "10-K", "reportDate": "2020-12-31"},
    ]

    assert ten_k_history(filings) == [date(2020, 12, 31), date(2022, 12, 31)]


def test_ten_k_history_skips_a_filing_with_no_report_date() -> None:
    assert ten_k_history([{"form": "10-K", "reportDate": ""}]) == []


def test_count_foreign_annual_forms_counts_only_foreign_annual_reports() -> None:
    filings = [
        {"form": "20-F"},
        {"form": "40-F"},
        {"form": "10-K"},
        {"form": "6-K"},
    ]

    assert count_foreign_annual_forms(filings) == 2


def test_classify_coverage_reports_a_filer_without_xbrl() -> None:
    assert classify_coverage(False, []) is EdgarCoverage.NO_XBRL


def test_classify_coverage_reports_a_filer_whose_last_ten_k_predates_the_window() -> None:
    assert classify_coverage(True, [date(2008, 12, 31)]) is EdgarCoverage.NO_TEN_K


def test_classify_coverage_accepts_a_ten_k_inside_the_window() -> None:
    assert (
        classify_coverage(True, [date(2008, 12, 31), date(2016, 12, 31)]) is EdgarCoverage.COVERED
    )


def test_a_filer_lodging_only_foreign_annual_reports_is_a_foreign_private_issuer() -> None:
    filer = _filer(_candidate(), ten_k_count=0, foreign_annual_forms=17)

    assert filer.is_foreign_private_issuer is True
    assert filer.exclusion is Exclusion.FOREIGN_PRIVATE_ISSUER


def test_a_filer_lodging_ten_ks_is_not_a_foreign_private_issuer() -> None:
    """A US-incorporated subsidiary of a foreign bank files 10-K and stays in scope."""
    filer = _filer(_candidate(), ten_k_count=33, foreign_annual_forms=2)

    assert filer.is_foreign_private_issuer is False
    assert filer.exclusion is None


def test_a_filer_with_no_annual_reports_at_all_is_not_a_foreign_private_issuer() -> None:
    filer = _filer(_candidate(), ten_k_count=0, foreign_annual_forms=0)

    assert filer.is_foreign_private_issuer is False


def test_filer_exclusion_falls_back_to_the_candidate_screens() -> None:
    filer = _filer(_candidate(share=0.4, pays=False))

    assert filer.exclusion is Exclusion.NO_DEPOSIT_INTEREST


def test_bank_sic_membership_reads_the_registrant_code() -> None:
    assert _filer(_candidate(), sic="6021").has_bank_sic is True
    assert _filer(_candidate(), sic="6211").has_bank_sic is False
    assert _filer(_candidate(), sic=None).has_bank_sic is False
