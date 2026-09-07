from __future__ import annotations

from marketscope.banks import (
    EXCLUDED_FROM_EDGAR,
    FEASIBILITY_SAMPLE,
    FundingProfile,
    sample_by_cik,
    terminal_filers,
)


def test_sample_has_unique_ciks() -> None:
    ciks = [bank.cik for bank in FEASIBILITY_SAMPLE]

    assert len(ciks) == len(set(ciks))


def test_sample_index_covers_every_bank() -> None:
    assert len(sample_by_cik()) == len(FEASIBILITY_SAMPLE)


def test_sample_retains_terminal_filers() -> None:
    names = {bank.name for bank in terminal_filers()}

    assert "SVB Financial Group" in names
    assert "PacWest Bancorp" in names


def test_banks_without_edgar_coverage_are_recorded_with_a_reason() -> None:
    names = {name for name, _ in EXCLUDED_FROM_EDGAR}

    assert "First Republic Bank" in names
    assert all(reason.strip() for _, reason in EXCLUDED_FROM_EDGAR)


def test_excluded_banks_are_absent_from_the_sample() -> None:
    sampled = {bank.name for bank in FEASIBILITY_SAMPLE}

    assert sampled.isdisjoint({name for name, _ in EXCLUDED_FROM_EDGAR})


def test_terminal_filers_carry_a_last_filed_period_and_exit_reason() -> None:
    for bank in terminal_filers():
        assert bank.last_filed_period is not None
        assert bank.entity_events


def test_sample_spans_the_repricing_contrast() -> None:
    profiles = {bank.profile for bank in FEASIBILITY_SAMPLE}

    assert FundingProfile.DIRECT in profiles
    assert FundingProfile.REGIONAL in profiles


def test_delisted_banks_have_no_ticker() -> None:
    for bank in terminal_filers():
        assert bank.ticker is None
