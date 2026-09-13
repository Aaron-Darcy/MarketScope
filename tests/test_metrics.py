from __future__ import annotations

import pytest

from marketscope.metrics import (
    MetricTier,
    Provenance,
    average_balance,
    component_coverage,
    cost_of_deposits,
    cumulative_beta,
    implied_deposit_expense,
    resolve_deposit_cost,
    resolve_deposit_interest_expense,
    resolve_interest_bearing_deposits,
    resolve_noninterest_bearing_deposits,
)


def test_interest_bearing_prefers_the_reported_concept() -> None:
    resolved = resolve_interest_bearing_deposits(
        {
            "InterestBearingDepositLiabilities": 800.0,
            "Deposits": 1000.0,
            "NoninterestBearingDepositLiabilities": 150.0,
        }
    )

    assert resolved is not None
    assert resolved.value == 800.0
    assert resolved.provenance is Provenance.REPORTED


def test_interest_bearing_sums_domestic_and_foreign_components() -> None:
    resolved = resolve_interest_bearing_deposits(
        {
            "InterestBearingDepositLiabilitiesDomestic": 600.0,
            "InterestBearingDepositLiabilitiesForeign": 250.0,
            "Deposits": 1000.0,
        }
    )

    assert resolved is not None
    assert resolved.value == 850.0
    assert resolved.provenance is Provenance.SUMMED_COMPONENTS


def test_interest_bearing_falls_back_to_the_residual() -> None:
    resolved = resolve_interest_bearing_deposits(
        {"Deposits": 1000.0, "NoninterestBearingDepositLiabilities": 400.0}
    )

    assert resolved is not None
    assert resolved.value == 600.0
    assert resolved.provenance is Provenance.DERIVED_RESIDUAL


def test_interest_bearing_refuses_a_partial_noninterest_bearing_figure() -> None:
    resolved = resolve_interest_bearing_deposits(
        {"Deposits": 1000.0, "NoninterestBearingDepositLiabilitiesDomestic": 300.0}
    )

    assert resolved is None


def test_interest_bearing_rejects_a_non_positive_residual() -> None:
    resolved = resolve_interest_bearing_deposits(
        {"Deposits": 400.0, "NoninterestBearingDepositLiabilities": 400.0}
    )

    assert resolved is None


def test_interest_bearing_returns_nothing_without_a_usable_route() -> None:
    assert resolve_interest_bearing_deposits({"Deposits": 1000.0}) is None


def test_noninterest_bearing_sums_complete_components() -> None:
    resolved = resolve_noninterest_bearing_deposits(
        {
            "NoninterestBearingDepositLiabilitiesDomestic": 300.0,
            "NoninterestBearingDepositLiabilitiesForeign": 50.0,
        }
    )

    assert resolved is not None
    assert resolved.value == 350.0


def test_expense_prefers_the_reported_concept() -> None:
    resolved = resolve_deposit_interest_expense(
        {"InterestExpenseDeposits": 10.0, "InterestExpenseSavingsDeposits": 4.0}
    )

    assert resolved is not None
    assert resolved.value == 10.0
    assert resolved.provenance is Provenance.REPORTED


def test_expense_sums_leaf_components_when_no_total_is_reported() -> None:
    resolved = resolve_deposit_interest_expense(
        {
            "InterestExpenseSavingsDeposits": 4.0,
            "InterestExpenseTimeDeposits": 5.0,
            "InterestExpenseNegotiableOrderOfWithdrawalNOWDeposits": 1.0,
        }
    )

    assert resolved is not None
    assert resolved.value == 10.0
    assert resolved.provenance is Provenance.SUMMED_COMPONENTS


def test_average_balance_uses_both_period_ends() -> None:
    assert average_balance(800.0, 900.0) == (850.0, "endpoint")


def test_average_balance_marks_a_missing_opening_balance() -> None:
    assert average_balance(None, 900.0) == (900.0, "closing_only")


def test_cost_of_deposits_annualises_a_quarterly_expense() -> None:
    rate = cost_of_deposits(quarterly_expense=10.0, opening_balance=800.0, closing_balance=800.0)

    assert rate == pytest.approx(0.05)


def test_cost_of_deposits_returns_nothing_for_a_zero_base() -> None:
    assert cost_of_deposits(10.0, 0.0, 0.0) is None


def test_deposit_cost_reaches_tier_one_on_reported_concepts() -> None:
    current = {
        "InterestExpenseDeposits": 10.0,
        "InterestBearingDepositLiabilities": 820.0,
        "Deposits": 1000.0,
    }
    previous = {"InterestBearingDepositLiabilities": 780.0, "Deposits": 980.0}

    cost = resolve_deposit_cost(current, previous)

    assert cost is not None
    assert cost.tier is MetricTier.TIER_1
    assert cost.rate == pytest.approx(0.05)
    assert cost.avg_method == "endpoint"


def test_deposit_cost_falls_to_tier_two_without_an_interest_bearing_base() -> None:
    cost = resolve_deposit_cost(
        {"InterestExpenseDeposits": 10.0, "Deposits": 1000.0},
        {"Deposits": 1000.0},
    )

    assert cost is not None
    assert cost.tier is MetricTier.TIER_2
    assert cost.rate == pytest.approx(0.04)


def test_deposit_cost_is_tier_three_when_the_numerator_is_reconstructed() -> None:
    cost = resolve_deposit_cost(
        {
            "InterestExpenseSavingsDeposits": 6.0,
            "InterestExpenseTimeDeposits": 4.0,
            "InterestBearingDepositLiabilities": 800.0,
            "Deposits": 1000.0,
        },
        {"InterestBearingDepositLiabilities": 800.0},
    )

    assert cost is not None
    assert cost.tier is MetricTier.TIER_3


def test_deposit_cost_matches_the_opening_base_to_the_tier() -> None:
    current = {"InterestExpenseDeposits": 10.0, "Deposits": 1000.0}
    previous = {"InterestBearingDepositLiabilities": 500.0, "Deposits": 1000.0}

    cost = resolve_deposit_cost(current, previous)

    assert cost is not None
    assert cost.tier is MetricTier.TIER_2
    assert cost.rate == pytest.approx(0.04)


def test_deposit_cost_returns_nothing_without_an_expense() -> None:
    assert resolve_deposit_cost({"Deposits": 1000.0}) is None


def test_cumulative_beta_is_the_pass_through_share() -> None:
    beta = cumulative_beta(
        cost_start=0.0026,
        cost_end=0.0277,
        policy_rate_start=0.08,
        policy_rate_end=5.33,
    )

    assert beta == pytest.approx(0.0251 / 5.25, rel=1e-6)


def test_cumulative_beta_returns_nothing_when_policy_did_not_move() -> None:
    assert cumulative_beta(0.01, 0.02, 2.0, 2.0) is None


def test_implied_deposit_expense_removes_non_deposit_funding() -> None:
    implied = implied_deposit_expense(
        {
            "InterestExpense": 866.0,
            "InterestExpenseLongTermDebt": 101.0,
            "InterestExpenseShortTermBorrowings": 69.0,
        }
    )

    assert implied == pytest.approx(696.0)


def test_implied_deposit_expense_needs_a_total() -> None:
    assert implied_deposit_expense({"InterestExpenseLongTermDebt": 101.0}) is None


def test_component_coverage_measures_the_reconstructed_share() -> None:
    values = {
        "InterestExpense": 866.0,
        "InterestExpenseLongTermDebt": 101.0,
        "InterestExpenseShortTermBorrowings": 69.0,
    }

    assert component_coverage(values, 202.0) == pytest.approx(202.0 / 696.0)


def test_deposit_cost_excludes_an_incomplete_reconstructed_numerator() -> None:
    cost = resolve_deposit_cost(
        {
            "InterestExpenseTimeDeposits": 202.0,
            "InterestExpense": 866.0,
            "InterestExpenseLongTermDebt": 101.0,
            "InterestExpenseShortTermBorrowings": 69.0,
            "InterestBearingDepositLiabilities": 100000.0,
            "Deposits": 160000.0,
        },
        {"InterestBearingDepositLiabilities": 100000.0},
    )

    assert cost is not None
    assert cost.tier is MetricTier.EXCLUDED
    assert cost.component_coverage is not None
    assert cost.component_coverage < 0.80


def test_deposit_cost_keeps_a_complete_reconstructed_numerator() -> None:
    cost = resolve_deposit_cost(
        {
            "InterestExpenseTimeDeposits": 400.0,
            "InterestExpenseSavingsDeposits": 260.0,
            "InterestExpense": 866.0,
            "InterestExpenseLongTermDebt": 101.0,
            "InterestExpenseShortTermBorrowings": 69.0,
            "InterestBearingDepositLiabilities": 100000.0,
        },
        {"InterestBearingDepositLiabilities": 100000.0},
    )

    assert cost is not None
    assert cost.tier is MetricTier.TIER_3


def test_deposit_cost_keeps_components_when_no_total_is_available_to_check() -> None:
    cost = resolve_deposit_cost(
        {
            "InterestExpenseTimeDeposits": 10.0,
            "InterestBearingDepositLiabilities": 800.0,
        },
        {"InterestBearingDepositLiabilities": 800.0},
    )

    assert cost is not None
    assert cost.tier is MetricTier.TIER_3
    assert cost.component_coverage is None


def test_component_group_prefers_a_category_total_over_its_own_parts() -> None:
    """Several filers tag a combined savings, money market and NOW concept alongside the
    savings leaf. Summing both would count savings twice and overstate the numerator."""
    resolved = resolve_deposit_interest_expense(
        {
            "InterestExpenseNOWAccountsMoneyMarketAccountsAndSavingsDeposits": 10.0,
            "InterestExpenseSavingsDeposits": 4.0,
        }
    )

    assert resolved is not None
    assert resolved.value == 10.0


def test_component_group_sums_leaves_when_the_category_total_is_absent() -> None:
    resolved = resolve_deposit_interest_expense(
        {
            "InterestExpenseSavingsDeposits": 4.0,
            "InterestExpenseMoneyMarketDeposits": 3.0,
        }
    )

    assert resolved is not None
    assert resolved.value == 7.0


def test_components_are_summed_across_categories() -> None:
    """First Horizon tags time, savings and other domestic deposits separately, and the
    third was the category the earlier concept list omitted."""
    resolved = resolve_deposit_interest_expense(
        {
            "InterestExpenseTimeDeposits": 19.2,
            "InterestExpenseSavingsDeposits": 30.4,
            "InterestExpenseOtherDomesticDeposits": 17.6,
        }
    )

    assert resolved is not None
    assert resolved.value == pytest.approx(67.2)


def test_time_deposits_split_by_the_insurance_limit_is_used_only_without_a_total() -> None:
    with_total = resolve_deposit_interest_expense(
        {
            "InterestExpenseTimeDeposits": 9.0,
            "InterestExpenseTimeDeposits100000OrMore": 6.0,
            "InterestExpenseTimeDepositsLessThan100000": 3.0,
        }
    )
    without_total = resolve_deposit_interest_expense(
        {
            "InterestExpenseTimeDeposits100000OrMore": 6.0,
            "InterestExpenseTimeDepositsLessThan100000": 3.0,
        }
    )

    assert with_total is not None and with_total.value == 9.0
    assert without_total is not None and without_total.value == 9.0


def test_no_deposit_concepts_at_all_resolves_to_nothing() -> None:
    assert resolve_deposit_interest_expense({"InterestExpenseLongTermDebt": 5.0}) is None


def test_federal_home_loan_bank_advances_are_treated_as_non_deposit_funding() -> None:
    """FHLB advances are a primary regional-bank funding source. Leaving them in inflated
    implied deposit expense and made complete reconstructions look short."""
    implied = implied_deposit_expense(
        {
            "InterestExpense": 100.0,
            "InterestExpenseFederalHomeLoanBankAndFederalReserveBankAdvancesLongTerm": 20.0,
            "InterestExpenseSecuritiesSoldUnderAgreementsToRepurchase": 10.0,
        }
    )

    assert implied == pytest.approx(70.0)
