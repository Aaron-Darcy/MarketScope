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
        cik=1102112,
        name="PacWest Bancorp",
        ticker=None,
        profile=FundingProfile.REGIONAL,
        name_fragment="PACWEST",
        rationale=(
            "Terminal filer covering both cycles. Sustained acute deposit outflow through "
            "2023 and exited by merger rather than closure, which exercises the terminal "
            "filer and entity event paths together"
        ),
        last_filed_period=date(2023, 9, 30),
        entity_events=("Merged into Banc of California, November 2023",),
    ),
)

EXCLUDED_FROM_EDGAR: tuple[tuple[str, str], ...] = (
    (
        "First Republic Bank",
        "State-chartered bank with no holding company. Filed periodic reports with the "
        "FDIC rather than the SEC, so EDGAR holds no 10-K and no XBRL facts. CIK 1132979 "
        "exists under the name but carries only 40-6B/A and SC 13G filings. Recoverable "
        "only from regulatory data.",
    ),
    (
        "Signature Bank",
        "Same pattern as First Republic. No 10-K filer in EDGAR.",
    ),
    (
        "Silvergate Capital Corporation",
        "Files with the SEC and has XBRL, but its first 10-K covers fiscal 2019, so it has "
        "no calibration-window history. Usable for the test cycle and the survivorship "
        "comparison, not for cross-cycle persistence.",
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
