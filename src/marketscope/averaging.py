"""Endpoint averaging measured against the quarterly averages Call Reports report.

Schedule RC-K averages interest-bearing transaction accounts and every nontransaction
account, interest-bearing or not, so its total is the interest-bearing base only where a
bank's nontransaction accounts all pay interest. Banks that reclassify demand balances into
savings for reserve purposes report them on RC-K inconsistently with RC-E, and some leave
them out of RC-K altogether. Each group is therefore measured on whichever of two bases its
averages reconcile to across the quarters held (decision 0039):

- interest-bearing: the whole RC-K total against quarter-end interest-bearing deposits;
- nontransaction: RC-K's nontransaction and foreign-office averages against quarter-end
  nontransaction accounts and interest-bearing deposits in foreign offices.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import pandas as pd

from marketscope.metrics import BASE_RECONCILIATION_TOLERANCE
from marketscope.panel import previous_quarter_end

# Borrowed from the base reconciliation of decision 0027 rather than read off the gaps
# measured here, so the rule that admits a group was not chosen by looking at which groups
# it admits.
RECONCILIATION_TOLERANCE = BASE_RECONCILIATION_TOLERANCE


class Basis(StrEnum):
    INTEREST_BEARING = "interest_bearing"
    NONTRANSACTION = "nontransaction"


@dataclass(frozen=True)
class GroupQuarter:
    """A group's Call Report deposits for one quarter, summed across its institutions."""

    group_key: str
    cik: int | None
    quarter_end: date
    institutions: int
    averaged_institutions: int
    average: dict[Basis, float]
    closing: dict[Basis, float]

    @property
    def complete(self) -> bool:
        """Whether every institution in the group reported RC-K for the quarter."""
        return self.averaged_institutions == self.institutions


@dataclass(frozen=True)
class Measurement:
    quarter: GroupQuarter
    endpoint: dict[Basis, float]

    def gap(self, basis: Basis) -> float:
        """Endpoint average against the reported average, less one."""
        return self.endpoint[basis] / self.quarter.average[basis] - 1


@dataclass(frozen=True)
class Reconciliation:
    """The basis a group is measured on, and the median gap on each basis."""

    basis: Basis | None
    gaps: dict[Basis, float]
    quarters: int


AVERAGING_COLUMNS: tuple[str, ...] = (
    "group_key",
    "cik",
    "quarter_end",
    "institutions",
    "interest_bearing_gap",
    "nontransaction_gap",
    "basis",
    "reported_average",
    "endpoint_average",
    "closing_balance",
    "averaging_error",
    "closing_only_error",
)


def measurements(quarters: Iterable[GroupQuarter]) -> dict[str, list[Measurement]]:
    """Every group-quarter whose endpoint average can be set against a reported one.

    Both quarters must be complete: a group with one institution missing from the archives
    would set part of its balance against all of it. A reported average that is not positive
    leaves the quarter unmeasured on both bases rather than dividing by it.
    """
    by_group: dict[str, dict[date, GroupQuarter]] = {}
    for quarter in quarters:
        by_group.setdefault(quarter.group_key, {})[quarter.quarter_end] = quarter

    measured: dict[str, list[Measurement]] = {}
    for group_key in sorted(by_group):
        held = by_group[group_key]
        for day in sorted(held):
            current = held[day]
            previous = held.get(previous_quarter_end(day))
            if previous is None or not (current.complete and previous.complete):
                continue
            if any(current.average[basis] <= 0 for basis in Basis):
                continue
            endpoint = {
                basis: (previous.closing[basis] + current.closing[basis]) / 2 for basis in Basis
            }
            measured.setdefault(group_key, []).append(Measurement(current, endpoint))
    return measured


def reconcile(measured: list[Measurement]) -> Reconciliation:
    """Choose the basis a group's averages reconcile to.

    A basis reconciles where the median gap across the group's quarters is within the
    tolerance. A definitional difference holds in every quarter and moves the median, while
    averaging error varies from one quarter to the next and largely does not. The
    interest-bearing basis is preferred where both reconcile, since it is the base the XBRL
    metric divides by.
    """
    gaps = {
        basis: statistics.median(measurement.gap(basis) for measurement in measured)
        for basis in Basis
    }
    basis = next((basis for basis in Basis if abs(gaps[basis]) <= RECONCILIATION_TOLERANCE), None)
    return Reconciliation(basis=basis, gaps=gaps, quarters=len(measured))


def averaging_frame(quarters: Iterable[GroupQuarter]) -> pd.DataFrame:
    """The endpoint-averaging error of every measurable group-quarter.

    Every measurable quarter has a row with its gap on both bases. The error columns are
    filled only on the basis the group reconciles to, and stay null for a group that
    reconciles to neither, which is reported rather than measured on a base known to differ.
    """
    rows: list[tuple[object, ...]] = []
    for group_key, measured in measurements(quarters).items():
        chosen = reconcile(measured).basis
        for measurement in measured:
            quarter = measurement.quarter
            reported = quarter.average[chosen] if chosen else None
            endpoint = measurement.endpoint[chosen] if chosen else None
            closing = quarter.closing[chosen] if chosen else None
            rows.append(
                (
                    group_key,
                    quarter.cik,
                    quarter.quarter_end,
                    quarter.institutions,
                    measurement.gap(Basis.INTEREST_BEARING),
                    measurement.gap(Basis.NONTRANSACTION),
                    chosen.value if chosen else None,
                    reported,
                    endpoint,
                    closing,
                    measurement.gap(chosen) if chosen else None,
                    closing / reported - 1 if closing is not None and reported else None,
                )
            )
    return pd.DataFrame(rows, columns=list(AVERAGING_COLUMNS))


def cost_on_reported_average(endpoint_cost: float, averaging_error: float) -> float:
    """A cost of deposits restated from the endpoint average to the reported one.

    The expense is unchanged, so the cost scales by the ratio of the two averages. Applied
    to a cost measured on interest-bearing deposits with an error measured on the
    nontransaction basis, it assumes interest-bearing transaction accounts moved within the
    quarter as the other balances did.
    """
    return endpoint_cost * (1 + averaging_error)
