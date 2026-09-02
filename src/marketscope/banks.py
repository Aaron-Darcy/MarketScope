from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class FundingProfile(StrEnum):
    LARGE_DIVERSIFIED = "large_diversified"
    SUPER_REGIONAL = "super_regional"
    REGIONAL = "regional"
    DIRECT = "direct"


@dataclass(frozen=True)
class Bank:
    cik: int
    name: str
    ticker: str | None
    profile: FundingProfile
    name_fragment: str
    rationale: str
    last_filed_period: date | None = None
    entity_events: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_terminal_filer(self) -> bool:
        return self.last_filed_period is not None


FEASIBILITY_SAMPLE: tuple[Bank, ...] = (
    Bank(
        cik=19617,
        name="JPMorgan Chase & Co.",
        ticker="JPM",
        profile=FundingProfile.LARGE_DIVERSIFIED,
        name_fragment="JPMORGAN",
        rationale="Largest US filer; most complex deposit disclosure",
        entity_events=("Acquired First Republic Bank, May 2023",),
    ),
    Bank(
        cik=70858,
        name="Bank of America Corporation",
        ticker="BAC",
        profile=FundingProfile.LARGE_DIVERSIFIED,
        name_fragment="BANK OF AMERICA",
        rationale="Large branch-funded deposit base; expected low beta",
    ),
    Bank(
        cik=72971,
        name="Wells Fargo & Company",
        ticker="WFC",
        profile=FundingProfile.LARGE_DIVERSIFIED,
        name_fragment="WELLS FARGO",
        rationale="Large branch-funded deposit base; expected low beta",
    ),
    Bank(
        cik=831001,
        name="Citigroup Inc.",
        ticker="C",
        profile=FundingProfile.LARGE_DIVERSIFIED,
        name_fragment="CITIGROUP",
        rationale="Material foreign deposit base; tests domestic/foreign tag split",
    ),
    Bank(
        cik=713676,
        name="The PNC Financial Services Group, Inc.",
        ticker="PNC",
        profile=FundingProfile.SUPER_REGIONAL,
        name_fragment="PNC",
        rationale="Super-regional; mid-cycle acquisition tests entity continuity",
        entity_events=("Acquired BBVA USA, June 2021",),
    ),
    Bank(
        cik=36104,
        name="U.S. Bancorp",
        ticker="USB",
        profile=FundingProfile.SUPER_REGIONAL,
        name_fragment="US BANCORP",
        rationale="Super-regional; mid-cycle acquisition tests entity continuity",
        entity_events=("Acquired MUFG Union Bank, December 2022",),
    ),
    Bank(
        cik=92230,
        name="Truist Financial Corporation",
        ticker="TFC",
        profile=FundingProfile.SUPER_REGIONAL,
        name_fragment="TRUIST",
        rationale="Merger of equals straddles the calibration window",
        entity_events=("BB&T and SunTrust merged to form Truist, December 2019",),
    ),
    Bank(
        cik=36270,
        name="M&T Bank Corporation",
        ticker="MTB",
        profile=FundingProfile.REGIONAL,
        name_fragment="M&T BANK",
        rationale="Regional; mid-cycle acquisition tests entity continuity",
        entity_events=("Acquired People's United Financial, April 2022",),
    ),
    Bank(
        cik=40729,
        name="Ally Financial Inc.",
        ticker="ALLY",
        profile=FundingProfile.DIRECT,
        name_fragment="ALLY FINANCIAL",
        rationale=(
            "Direct bank with no branch network; expected high beta. Provides the upper "
            "end of the repricing contrast the study depends on"
        ),
    ),
    Bank(
        cik=109380,
        name="Zions Bancorporation, National Association",
        ticker="ZION",
        profile=FundingProfile.REGIONAL,
        name_fragment="ZIONS",
        rationale=(
            "Branch-funded regional; expected low beta. Provides the lower end of the "
            "repricing contrast the study depends on"
        ),
    ),
    Bank(
        cik=719739,
        name="SVB Financial Group",
        ticker=None,
        profile=FundingProfile.REGIONAL,
        name_fragment="SVB FINANCIAL",
        rationale="Terminal filer; concentrated uninsured commercial deposit base",
        last_filed_period=date(2022, 12, 31),
        entity_events=("Silicon Valley Bank closed by regulators, March 2023",),
    ),
    Bank(
        cik=1132979,
        name="First Republic Bank",
        ticker=None,
        profile=FundingProfile.REGIONAL,
        name_fragment="FIRST REPUBLIC",
        rationale="Terminal filer; relationship deposit base",
        last_filed_period=date(2022, 12, 31),
        entity_events=("Closed by regulators and acquired by JPMorgan Chase, May 2023",),
    ),
)


DEPOSIT_INTEREST_EXPENSE_TAGS: tuple[str, ...] = (
    "InterestExpenseDeposits",
    "InterestExpenseDomesticDeposits",
    "InterestExpenseForeignDeposits",
    "InterestExpenseDemandDeposits",
    "InterestExpenseSavingsDeposits",
    "InterestExpenseMoneyMarketDeposits",
    "InterestExpenseNegotiableOrderOfWithdrawalNOW",
    "InterestExpenseTimeDeposits",
    "InterestExpenseDepositsAndShortTermBorrowings",
)

DEPOSIT_BALANCE_TAGS: tuple[str, ...] = (
    "Deposits",
    "InterestBearingDepositLiabilities",
    "NoninterestBearingDepositLiabilities",
    "InterestBearingDomesticDepositMoneyMarket",
    "InterestBearingDomesticDepositsSavings",
    "InterestBearingDomesticDepositsTimeDeposits",
    "DepositsDomestic",
    "DepositsForeign",
    "TimeDeposits",
)

CONTEXT_TAGS: tuple[str, ...] = (
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "InterestExpense",
    "InterestIncomeExpenseNet",
    "InterestAndDividendIncomeOperating",
    "NetIncomeLoss",
)


def sample_by_cik() -> dict[int, Bank]:
    return {bank.cik: bank for bank in FEASIBILITY_SAMPLE}


def terminal_filers() -> tuple[Bank, ...]:
    return tuple(bank for bank in FEASIBILITY_SAMPLE if bank.is_terminal_filer)
