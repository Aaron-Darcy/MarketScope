from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta

from marketscope.facts import Fact, Periodicity, derive_fourth_quarter, latest_filed
from marketscope.metrics import (
    EXPENSE_COMPONENT_TAGS,
    EXPENSE_REPORTED_TAG,
    IB_COMPONENT_TAGS,
    IB_REPORTED_TAG,
    NIB_COMPONENT_TAGS,
    NIB_REPORTED_TAG,
    NON_DEPOSIT_FUNDING_TAGS,
    TOTAL_DEPOSITS_TAG,
    TOTAL_INTEREST_EXPENSE_TAG,
)

DEFAULT_TAXONOMY = "us-gaap"

# Balances are instants: a deposit base is a position at a date, not a flow over one.
BALANCE_TAGS: frozenset[str] = frozenset(
    (
        TOTAL_DEPOSITS_TAG,
        IB_REPORTED_TAG,
        NIB_REPORTED_TAG,
        *IB_COMPONENT_TAGS,
        *NIB_COMPONENT_TAGS,
    )
)

# Expenses are durations. The non-deposit funding lines are carried because the
# completeness check on a reconstructed numerator needs them, not because the metric
# consumes them directly.
EXPENSE_TAGS: frozenset[str] = frozenset(
    (
        EXPENSE_REPORTED_TAG,
        TOTAL_INTEREST_EXPENSE_TAG,
        *EXPENSE_COMPONENT_TAGS,
        *NON_DEPOSIT_FUNDING_TAGS,
    )
)

PANEL_TAGS: frozenset[str] = BALANCE_TAGS | EXPENSE_TAGS

_QUARTER_LAST_DAY = {3: 31, 6: 30, 9: 30, 12: 31}


def quarter_end(day: date) -> date:
    """Return the calendar quarter end the date falls within."""
    month = ((day.month - 1) // 3 + 1) * 3
    return date(day.year, month, _QUARTER_LAST_DAY[month])


def previous_quarter_end(day: date) -> date:
    """Return the quarter end before the quarter the date falls within.

    Stepping back from the first day of the quarter, not from the first day of the month.
    A quarter end is the last month of its quarter, so subtracting a day from the first of
    that month lands in the same quarter and returns the quarter unchanged.
    """
    end = quarter_end(day)
    first_of_quarter = date(end.year, end.month - 2, 1)
    return quarter_end(first_of_quarter - timedelta(days=1))


def quarterly_panel(
    facts: Iterable[Fact],
    *,
    taxonomy: str | None = DEFAULT_TAXONOMY,
) -> dict[date, dict[str, float]]:
    """Collapse a filer's facts into deposit metric inputs keyed by quarter end.

    Balances are taken from instants and expenses from quarterly durations, with the
    fourth quarter derived where a filer publishes no fourth 10-Q. Restatement precedence
    is applied per concept first, so a revised figure replaces the original rather than
    both reaching the panel.

    The taxonomy is pinned because a filer may declare a concept in its own extension
    namespace under a name the standard taxonomy also uses, and the two are not the same
    concept. Passing ``None`` reads every namespace and is only safe for profiling.
    """
    by_tag: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        if taxonomy is not None and fact.taxonomy != taxonomy:
            continue
        if fact.tag in PANEL_TAGS:
            by_tag[fact.tag].append(fact)

    panel: dict[date, dict[str, float]] = defaultdict(dict)

    for tag, group in by_tag.items():
        current = latest_filed(group)

        if tag in BALANCE_TAGS:
            for fact in current:
                if fact.periodicity is Periodicity.INSTANT:
                    panel[fact.period_end][tag] = fact.value
            continue

        quarterly = [fact for fact in current if fact.periodicity is Periodicity.QUARTERLY]
        for fact in quarterly + derive_fourth_quarter(current):
            panel[fact.period_end][tag] = fact.value

    return dict(panel)
