from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import pandas as pd

from marketscope.facts import Fact
from marketscope.metrics import (
    EXPENSE_COMPONENT_TAGS,
    EXPENSE_REPORTED_TAG,
    DepositCost,
    Provenance,
    resolve_deposit_cost,
)
from marketscope.panel import Panel, build_panel, previous_quarter_end

# The staging columns a fact is rebuilt from, in the order `facts_from_rows` reads them.
FACT_FIELDS: tuple[str, ...] = (
    "cik",
    "taxonomy",
    "tag",
    "unit",
    "value",
    "period_start",
    "period_end",
    "filed",
    "accession",
    "form",
    "fiscal_year",
    "fiscal_period",
    "frame",
)

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


def facts_from_rows(rows: Iterable[tuple[Any, ...]]) -> dict[int, list[Fact]]:
    """Group staged fact rows, ordered as `FACT_FIELDS`, into facts by filer."""
    by_cik: dict[int, list[Fact]] = defaultdict(list)
    for row in rows:
        record = dict(zip(FACT_FIELDS, row, strict=True))
        cik = int(record.pop("cik"))
        by_cik[cik].append(Fact(**record))
    return dict(by_cik)


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
