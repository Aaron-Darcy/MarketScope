from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

QUARTERS_PER_YEAR = 4

TOTAL_DEPOSITS_TAG = "Deposits"
IB_REPORTED_TAG = "InterestBearingDepositLiabilities"
NIB_REPORTED_TAG = "NoninterestBearingDepositLiabilities"

IB_COMPONENT_TAGS: tuple[str, ...] = (
    "InterestBearingDepositLiabilitiesDomestic",
    "InterestBearingDepositLiabilitiesForeign",
)
NIB_COMPONENT_TAGS: tuple[str, ...] = (
    "NoninterestBearingDepositLiabilitiesDomestic",
    "NoninterestBearingDepositLiabilitiesForeign",
)

EXPENSE_REPORTED_TAG = "InterestExpenseDeposits"
TOTAL_INTEREST_EXPENSE_TAG = "InterestExpense"

# Non-deposit funding lines, subtracted from total interest expense to imply what deposits
# must have cost. Used only to test whether a reconstructed numerator is complete. The list
# was first drawn from a twelve-bank sample and missed the funding sources regional banks
# rely on most, notably Federal Home Loan Bank advances and repurchase agreements, which
# inflated the implied figure and made complete reconstructions look short.
NON_DEPOSIT_FUNDING_TAGS: tuple[str, ...] = (
    "InterestExpenseLongTermDebt",
    "InterestExpenseOtherLongTermDebt",
    "InterestExpenseShortTermBorrowings",
    "InterestExpenseOtherShortTermBorrowings",
    "InterestExpenseShortTermBorrowingsExcludingFederalFundsAndSecuritiesSoldUnderAgreementsToRepurchase",
    "InterestExpenseBorrowings",
    "InterestExpenseOtherBorrowings",
    "InterestExpenseDebt",
    "InterestExpenseSubordinatedNotesAndDebentures",
    "InterestExpenseJuniorSubordinatedDebentures",
    "InterestExpenseFederalFundsPurchasedAndSecuritiesSoldUnderAgreementsToRepurchase",
    "InterestExpenseFederalFundsPurchased",
    "InterestExpenseSecuritiesSoldUnderAgreementsToRepurchase",
    "InterestExpenseFederalHomeLoanBankAndFederalReserveBankAdvancesLongTerm",
    "InterestExpenseFederalHomeLoanBankAndFederalReserveBankAdvancesShortTerm",
    "InterestExpenseTradingLiabilities",
    "InterestExpenseCommercialPaper",
    "InterestExpenseBeneficialInterestsIssuedByConsolidatedVariableInterestEntities",
    "InterestExpenseRelatedParty",
    "InterestExpenseLesseeAssetsUnderCapitalLease",
)

COMPONENT_COVERAGE_FLOOR = 0.80

# Deposit expense categories, each contributing to the numerator at most once. A category
# is taken from its total where the filer publishes one, and otherwise from whichever leaf
# concepts are present. Totals and leaves are never added together: several filers tag both
# a combined concept and its parts, and summing everything present would double count them,
# which is the opposite of the understatement the completeness check guards against.
#
# The categories do not overlap, so the reconstruction is their sum.
EXPENSE_COMPONENT_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    # Time deposits, as a total or split at the old FDIC insurance limit.
    (
        ("InterestExpenseTimeDeposits",),
        (
            "InterestExpenseTimeDeposits100000OrMore",
            "InterestExpenseTimeDepositsLessThan100000",
        ),
    ),
    # Savings, money market and NOW. Several filers publish one combined concept covering
    # all three rather than tagging them separately.
    (
        ("InterestExpenseNOWAccountsMoneyMarketAccountsAndSavingsDeposits",),
        (
            "InterestExpenseSavingsDeposits",
            "InterestExpenseMoneyMarketDeposits",
            "InterestExpenseNegotiableOrderOfWithdrawalNOWDeposits",
            "InterestExpenseNegotiableOrderOfWithdrawalNOW",
        ),
    ),
    # Interest-bearing demand and checking balances tagged apart from the above.
    (
        (),
        (
            "InterestExpenseDemandDeposits",
            "InterestExpenseDemandDepositAccounts",
            "InterestExpenseDomesticDepositLiabilitiesChecking",
        ),
    ),
    # Domestic deposits a filer places in none of the categories above.
    (
        (),
        (
            "InterestExpenseOtherDomesticDeposits",
            "InterestExpenseDomesticDepositLiabilitiesWithdrawalPenalties",
        ),
    ),
    # Foreign deposits.
    ((), ("InterestExpenseForeignDeposits",)),
)

EXPENSE_COMPONENT_TAGS: tuple[str, ...] = tuple(
    dict.fromkeys(tag for totals, leaves in EXPENSE_COMPONENT_GROUPS for tag in (*totals, *leaves))
)


class Provenance(StrEnum):
    REPORTED = "reported"
    SUMMED_COMPONENTS = "summed_components"
    DERIVED_RESIDUAL = "derived_residual"


class MetricTier(StrEnum):
    TIER_1 = "1"
    TIER_2 = "2"
    TIER_3 = "3"
    EXCLUDED = "X"


@dataclass(frozen=True)
class Resolved:
    value: float
    provenance: Provenance


@dataclass(frozen=True)
class DepositCost:
    """An annualised cost of deposits for one bank-quarter, with its provenance."""

    rate: float
    tier: MetricTier
    expense_provenance: Provenance
    balance_provenance: Provenance
    avg_method: str
    component_coverage: float | None = None


def _sum_if_complete(values: Mapping[str, float], tags: tuple[str, ...]) -> float | None:
    present = [values[tag] for tag in tags if tag in values]
    if len(present) != len(tags):
        return None
    return sum(present)


def resolve_noninterest_bearing_deposits(values: Mapping[str, float]) -> Resolved | None:
    reported = values.get(NIB_REPORTED_TAG)
    if reported is not None:
        return Resolved(reported, Provenance.REPORTED)

    summed = _sum_if_complete(values, NIB_COMPONENT_TAGS)
    if summed is not None:
        return Resolved(summed, Provenance.SUMMED_COMPONENTS)

    return None


def resolve_interest_bearing_deposits(values: Mapping[str, float]) -> Resolved | None:
    """Resolve interest-bearing deposits by the most direct route the filer supports.

    Non-interest-bearing deposits have a deposit beta of zero by construction, so
    including them in the denominator scales a bank's measured beta by its
    interest-bearing share. That share varies widely by business model and moved sharply
    during 2022 and 2023, which makes total deposits unusable for cross-bank comparison.

    The residual route requires a complete non-interest-bearing figure. A partial one, such
    as a domestic component with no foreign counterpart, would understate what is subtracted
    and silently overstate the interest-bearing base, so it is refused rather than
    approximated.
    """
    reported = values.get(IB_REPORTED_TAG)
    if reported is not None:
        return Resolved(reported, Provenance.REPORTED)

    summed = _sum_if_complete(values, IB_COMPONENT_TAGS)
    if summed is not None:
        return Resolved(summed, Provenance.SUMMED_COMPONENTS)

    total = values.get(TOTAL_DEPOSITS_TAG)
    noninterest_bearing = resolve_noninterest_bearing_deposits(values)
    if total is not None and noninterest_bearing is not None:
        residual = total - noninterest_bearing.value
        if residual <= 0:
            return None
        return Resolved(residual, Provenance.DERIVED_RESIDUAL)

    return None


def resolve_deposit_interest_expense(values: Mapping[str, float]) -> Resolved | None:
    reported = values.get(EXPENSE_REPORTED_TAG)
    if reported is not None:
        return Resolved(reported, Provenance.REPORTED)

    components = sum_component_groups(values)
    if components is not None:
        return Resolved(components, Provenance.SUMMED_COMPONENTS)

    return None


def sum_component_groups(values: Mapping[str, float]) -> float | None:
    """Sum deposit expense across categories, taking each category at most once.

    A filer may tag a category total alongside the parts that make it up. Summing every
    concept present would then count those parts twice and overstate the numerator, which
    is the opposite of the understatement the completeness check guards against.
    """
    total = 0.0
    matched = False

    for totals, leaves in EXPENSE_COMPONENT_GROUPS:
        reported_total = next((values[tag] for tag in totals if tag in values), None)
        if reported_total is not None:
            total += reported_total
            matched = True
            continue

        present = [values[tag] for tag in leaves if tag in values]
        if present:
            total += sum(present)
            matched = True

    return total if matched else None


def implied_deposit_expense(values: Mapping[str, float]) -> float | None:
    """Deposit interest expense implied by total interest expense less non-deposit funding."""
    total = values.get(TOTAL_INTEREST_EXPENSE_TAG)
    if total is None:
        return None

    non_deposit = sum(values[tag] for tag in NON_DEPOSIT_FUNDING_TAGS if tag in values)
    implied = total - non_deposit
    return implied if implied > 0 else None


def component_coverage(values: Mapping[str, float], summed_expense: float) -> float | None:
    """Share of implied deposit expense that a reconstructed numerator accounts for.

    A filer may declare component concepts in its taxonomy yet tag only some of them in a
    given quarter. Summing whatever is present then understates the numerator silently and
    depresses the resulting beta, which is indistinguishable from a genuinely low-beta bank
    unless the sum is checked against an independent total.
    """
    implied = implied_deposit_expense(values)
    if implied is None:
        return None
    return summed_expense / implied


def average_balance(opening: float | None, closing: float) -> tuple[float, str]:
    """Average a deposit balance over a quarter from period-end observations.

    No filer in the sample tags an average deposit balance in any taxonomy, so the average
    is approximated from the two period ends. Where no opening balance is available the
    closing balance stands alone, which is marked so it can be excluded from results that
    require a true average.
    """
    if opening is None:
        return closing, "closing_only"
    return (opening + closing) / 2, "endpoint"


def cost_of_deposits(
    quarterly_expense: float,
    opening_balance: float | None,
    closing_balance: float,
) -> float | None:
    """Annualised rate paid on a deposit base for one quarter.

    Follows the convention used on regulatory filings: quarterly interest expense scaled by
    the average balance for the quarter, annualised by simple multiplication rather than
    compounding.
    """
    balance, _ = average_balance(opening_balance, closing_balance)
    if balance <= 0:
        return None
    return quarterly_expense * QUARTERS_PER_YEAR / balance


def resolve_deposit_cost(
    values: Mapping[str, float],
    previous_values: Mapping[str, float] | None = None,
) -> DepositCost | None:
    """Compute a bank-quarter cost of deposits at the most precise tier available.

    Tier 1 divides deposit interest expense by average interest-bearing deposits, which is
    the measure used in Federal Reserve deposit beta work. Tier 2 falls back to total
    deposits and is not comparable across banks with different non-interest-bearing shares.
    Tier 3 additionally reconstructs the numerator from component categories.
    """
    expense = resolve_deposit_interest_expense(values)
    if expense is None:
        return None

    balance = resolve_interest_bearing_deposits(values)
    tier_base = MetricTier.TIER_1
    if balance is None:
        total = values.get(TOTAL_DEPOSITS_TAG)
        if total is None:
            return None
        balance = Resolved(total, Provenance.REPORTED)
        tier_base = MetricTier.TIER_2

    coverage: float | None = None
    if expense.provenance is Provenance.SUMMED_COMPONENTS:
        tier_base = MetricTier.TIER_3
        coverage = component_coverage(values, expense.value)
        if coverage is not None and coverage < COMPONENT_COVERAGE_FLOOR:
            tier_base = MetricTier.EXCLUDED

    opening = _opening_balance(previous_values, tier_base)
    rate = cost_of_deposits(expense.value, opening, balance.value)
    if rate is None:
        return None

    _, avg_method = average_balance(opening, balance.value)

    return DepositCost(
        rate=rate,
        tier=tier_base,
        expense_provenance=expense.provenance,
        balance_provenance=balance.provenance,
        avg_method=avg_method,
        component_coverage=coverage,
    )


def _opening_balance(previous_values: Mapping[str, float] | None, tier: MetricTier) -> float | None:
    """Take the opening balance from the same deposit base as the closing balance.

    Averaging an interest-bearing closing balance against a total-deposit opening balance
    would produce a denominator that is neither, so the base must match the tier.
    """
    if previous_values is None:
        return None
    if tier in (MetricTier.TIER_2, MetricTier.EXCLUDED):
        return previous_values.get(TOTAL_DEPOSITS_TAG)

    resolved = resolve_interest_bearing_deposits(previous_values)
    return resolved.value if resolved is not None else None


def cumulative_beta(
    cost_start: float,
    cost_end: float,
    policy_rate_start: float,
    policy_rate_end: float,
) -> float | None:
    """Share of a policy rate move passed through to depositors over a full cycle.

    Cumulative over the cycle rather than differenced quarter on quarter, which is the
    market convention and far more stable than differencing noisy quarterly series.
    """
    policy_move = policy_rate_end - policy_rate_start
    if policy_move == 0:
        return None
    return (cost_end - cost_start) / policy_move
