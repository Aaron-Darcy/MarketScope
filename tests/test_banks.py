from __future__ import annotations

from marketscope.banks import FEASIBILITY_SAMPLE, FundingProfile, sample_by_cik, terminal_filers


def test_sample_has_unique_ciks() -> None:
    ciks = [bank.cik for bank in FEASIBILITY_SAMPLE]

    assert len(ciks) == len(set(ciks))


def test_sample_index_covers_every_bank() -> None:
    assert len(sample_by_cik()) == len(FEASIBILITY_SAMPLE)


def test_sample_retains_terminal_filers() -> None:
    names = {bank.name for bank in terminal_filers()}

    assert "SVB Financial Group" in names
    assert "First Republic Bank" in names


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
