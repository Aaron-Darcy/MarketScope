from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from marketscope.facts import facts_from_rows
from marketscope.metrics import (
    EXPENSE_COMPONENT_TAGS,
    EXPENSE_REPORTED_TAG,
    TOTAL_DEPOSITS_TAG,
    DepositCost,
    Provenance,
    average_balance,
    cost_of_deposits,
    resolve_deposit_cost,
    resolve_interest_bearing_deposits,
    resolve_noninterest_bearing_deposits,
)
from marketscope.panel import Panel, build_panel, previous_quarter_end, quarter_end

DEPOSIT_COST_COLUMNS: tuple[str, ...] = (
    "cik",
    "quarter_end",
    "cost_of_deposits",
    "metric_tier",
    "expense_provenance",
    "balance_provenance",
    "avg_method",
    "component_coverage",
    "q4_derived",
)

REGULATORY_COST_COLUMNS: tuple[str, ...] = (
    "group_key",
    "cik",
    "quarter_end",
    "institutions",
    "total_deposits",
    "interest_bearing_deposits",
    "deposit_expense",
    "cost_of_deposits",
    "avg_method",
)

DEPOSIT_BALANCE_COLUMNS: tuple[str, ...] = (
    "cik",
    "quarter_end",
    "total_deposits",
    "interest_bearing_deposits",
    "interest_bearing_provenance",
    "noninterest_bearing_deposits",
    "noninterest_bearing_provenance",
)


def numerator_derived(cost: DepositCost, derived: frozenset[str]) -> bool:
    """Whether the deposit expense behind a cost was derived as fiscal year less nine months.

    A reconstructed numerator counts as derived if any component concept is, since one
    derived component carries the derivation's failure modes into the sum.
    """
    if cost.expense_provenance is Provenance.REPORTED:
        return EXPENSE_REPORTED_TAG in derived
    return any(tag in derived for tag in EXPENSE_COMPONENT_TAGS)


def bank_quarter_rows(cik: int, panel: Panel) -> list[tuple[Any, ...]]:
    """Resolve every quarter of one filer's panel, in `DEPOSIT_COST_COLUMNS` order.

    Quarters with no resolvable numerator or denominator produce no row, so an absent
    bank-quarter is distinguishable from one resolved at tier X.
    """
    rows: list[tuple[Any, ...]] = []
    for quarter in sorted(panel.values):
        cost = resolve_deposit_cost(
            panel.values[quarter], panel.values.get(previous_quarter_end(quarter))
        )
        if cost is None:
            continue
        rows.append(
            (
                cik,
                quarter,
                cost.rate,
                cost.tier.value,
                cost.expense_provenance.value,
                cost.balance_provenance.value,
                cost.avg_method,
                cost.component_coverage,
                numerator_derived(cost, panel.derived.get(quarter, frozenset())),
            )
        )
    return rows


def deposit_cost_frame(rows: Iterable[tuple[Any, ...]]) -> pd.DataFrame:
    """Resolve the bank-quarter cost of deposits for every filer in a set of fact rows.

    Concepts outside the panel are ignored by `build_panel`, so a caller may pass
    unfiltered facts; filtering to `PANEL_TAGS` first only saves building them.
    """
    resolved: list[tuple[Any, ...]] = []
    for cik, facts in sorted(facts_from_rows(rows).items()):
        resolved.extend(bank_quarter_rows(cik, build_panel(facts)))
    return pd.DataFrame(resolved, columns=list(DEPOSIT_COST_COLUMNS))


def deposit_balance_rows(cik: int, panel: Panel) -> list[tuple[Any, ...]]:
    """The deposit base at every calendar quarter end, in `DEPOSIT_BALANCE_COLUMNS` order.

    Kept apart from the cost of deposits because a balance matters where no cost resolves:
    Schwab reports total deposits throughout 2020 but no cost resolves before 2021, and the
    step its TD Ameritrade acquisition produced falls in that gap. A quarter end with none
    of the three figures produces no row.
    """
    rows: list[tuple[Any, ...]] = []
    for day in sorted(panel.values):
        if day != quarter_end(day):
            continue
        values = panel.values[day]
        interest_bearing = resolve_interest_bearing_deposits(values)
        noninterest_bearing = resolve_noninterest_bearing_deposits(values)
        total = values.get(TOTAL_DEPOSITS_TAG)
        if total is None and interest_bearing is None and noninterest_bearing is None:
            continue
        rows.append(
            (
                cik,
                day,
                total,
                interest_bearing.value if interest_bearing else None,
                interest_bearing.provenance.value if interest_bearing else None,
                noninterest_bearing.value if noninterest_bearing else None,
                noninterest_bearing.provenance.value if noninterest_bearing else None,
            )
        )
    return rows


def deposit_balance_frame(rows: Iterable[tuple[Any, ...]]) -> pd.DataFrame:
    """The quarter-end deposit base for every filer in a set of fact rows."""
    resolved: list[tuple[Any, ...]] = []
    for cik, facts in sorted(facts_from_rows(rows).items()):
        resolved.extend(deposit_balance_rows(cik, build_panel(facts)))
    return pd.DataFrame(resolved, columns=list(DEPOSIT_BALANCE_COLUMNS))


def regulatory_cost_frame(rows: Iterable[tuple[Any, ...]]) -> pd.DataFrame:
    """Cost of deposits per regulatory group and quarter, by the arithmetic of the XBRL metric.

    Each row is a group's quarter summed across its insured institutions: group key, CIK,
    quarter end, institution count, total deposits, interest-bearing deposits and quarterly
    deposit interest expense. The cost annualises the expense by simple multiplication over
    the two-point average of interest-bearing deposits, as `cost_of_deposits` does for a
    filer, so the two measures differ only where their figures do.
    """
    groups: dict[str, tuple[Any, dict[Any, tuple[Any, ...]]]] = {}
    for group_key, cik, quarter, institutions, total, interest_bearing, expense in rows:
        groups.setdefault(group_key, (cik, {}))[1][quarter] = (
            institutions,
            total,
            interest_bearing,
            expense,
        )

    resolved: list[tuple[Any, ...]] = []
    for group_key in sorted(groups):
        cik, quarters = groups[group_key]
        for quarter in sorted(quarters):
            institutions, total, interest_bearing, expense = quarters[quarter]
            previous = quarters.get(previous_quarter_end(quarter))
            opening = previous[2] if previous is not None else None
            rate = cost_of_deposits(expense, opening, interest_bearing)
            if rate is None:
                continue
            _, avg_method = average_balance(opening, interest_bearing)
            resolved.append(
                (
                    group_key,
                    cik,
                    quarter,
                    institutions,
                    total,
                    interest_bearing,
                    expense,
                    rate,
                    avg_method,
                )
            )
    return pd.DataFrame(resolved, columns=list(REGULATORY_COST_COLUMNS))
