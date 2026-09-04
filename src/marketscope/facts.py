from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

DEFAULT_TAXONOMY = "us-gaap"
DEFAULT_UNITS = ("USD",)

_QUARTER_DAYS = range(80, 101)
_SEMIANNUAL_DAYS = range(170, 191)
_NINE_MONTH_DAYS = range(260, 291)
_ANNUAL_DAYS = range(350, 381)


class Periodicity(StrEnum):
    INSTANT = "instant"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    NINE_MONTH = "nine_month"
    ANNUAL = "annual"
    OTHER = "other"


@dataclass(frozen=True)
class Fact:
    taxonomy: str
    tag: str
    unit: str
    value: float
    period_end: date
    filed: date
    period_start: date | None = None
    accession: str | None = None
    form: str | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    frame: str | None = None
    derived: bool = False

    @property
    def periodicity(self) -> Periodicity:
        return classify_period(self.period_start, self.period_end)

    @property
    def period_key(self) -> tuple[str, str, date | None, date]:
        return (self.tag, self.unit, self.period_start, self.period_end)


def classify_period(start: date | None, end: date) -> Periodicity:
    if start is None:
        return Periodicity.INSTANT

    span = (end - start).days
    if span in _QUARTER_DAYS:
        return Periodicity.QUARTERLY
    if span in _SEMIANNUAL_DAYS:
        return Periodicity.SEMIANNUAL
    if span in _NINE_MONTH_DAYS:
        return Periodicity.NINE_MONTH
    if span in _ANNUAL_DAYS:
        return Periodicity.ANNUAL
    return Periodicity.OTHER


def extract_facts(
    payload: dict[str, Any],
    *,
    taxonomy: str | None = DEFAULT_TAXONOMY,
    tags: Iterable[str] | None = None,
    units: Iterable[str] = DEFAULT_UNITS,
) -> list[Fact]:
    """Flatten a company facts payload into rows.

    Passing ``taxonomy=None`` reads every taxonomy present, including the filer's own
    extension namespace, which is where concepts absent from us-gaap are published.
    """
    wanted_tags = set(tags) if tags is not None else None
    wanted_units = set(units)
    facts: list[Fact] = []

    taxonomies: dict[str, Any] = payload.get("facts", {})
    selected = taxonomies if taxonomy is None else {taxonomy: taxonomies.get(taxonomy, {})}

    for taxonomy_name, concepts in selected.items():
        for tag, concept in concepts.items():
            if wanted_tags is not None and tag not in wanted_tags:
                continue
            for unit, observations in concept.get("units", {}).items():
                if unit not in wanted_units:
                    continue
                facts.extend(
                    _build_fact(taxonomy_name, tag, unit, observation)
                    for observation in observations
                )

    return facts


def _build_fact(taxonomy: str, tag: str, unit: str, observation: dict[str, Any]) -> Fact:
    start = observation.get("start")
    return Fact(
        taxonomy=taxonomy,
        tag=tag,
        unit=unit,
        value=float(observation["val"]),
        period_start=date.fromisoformat(start) if start else None,
        period_end=date.fromisoformat(observation["end"]),
        filed=date.fromisoformat(observation["filed"]),
        accession=observation.get("accn"),
        form=observation.get("form"),
        fiscal_year=observation.get("fy"),
        fiscal_period=observation.get("fp"),
        frame=observation.get("frame"),
    )


def latest_filed(facts: Iterable[Fact]) -> list[Fact]:
    """Resolve restatements by keeping the most recently filed value for each period.

    The company facts endpoint returns every value a filer has published for a period,
    including those later revised. Analysis uses the current value; the superseded ones
    are the input to the filing-behaviour investigation and are kept separately.
    """
    winners: dict[tuple[str, str, date | None, date], Fact] = {}

    for fact in facts:
        incumbent = winners.get(fact.period_key)
        if incumbent is None or _supersedes(fact, incumbent):
            winners[fact.period_key] = fact

    return sorted(winners.values(), key=lambda fact: (fact.tag, fact.period_end))


def superseded(facts: Iterable[Fact]) -> list[Fact]:
    """Return the values that a later filing replaced."""
    materialised = list(facts)
    current = {fact.period_key: fact for fact in latest_filed(materialised)}

    return [
        fact
        for fact in materialised
        if fact.accession != current[fact.period_key].accession
        or fact.value != current[fact.period_key].value
    ]


def _supersedes(candidate: Fact, incumbent: Fact) -> bool:
    if candidate.filed != incumbent.filed:
        return candidate.filed > incumbent.filed
    return (candidate.accession or "") > (incumbent.accession or "")


def derive_fourth_quarter(facts: Iterable[Fact]) -> list[Fact]:
    """Derive fourth-quarter flows that filers do not report directly.

    Most banks file a 10-K rather than a fourth 10-Q, so the fourth quarter exists only
    as the residual of the fiscal year. Where a nine-month year-to-date figure is
    published it is used directly; otherwise the first three quarters are summed, which
    requires all three to be present and contiguous.
    """
    durations = [fact for fact in facts if fact.period_start is not None]
    by_tag: dict[tuple[str, str], list[Fact]] = defaultdict(list)
    for fact in durations:
        by_tag[(fact.tag, fact.unit)].append(fact)

    derived: list[Fact] = []
    for group in by_tag.values():
        for annual in (fact for fact in group if fact.periodicity is Periodicity.ANNUAL):
            partial = _preceding_partial(group, annual)
            if partial is None:
                continue
            derived.append(
                replace(
                    annual,
                    value=annual.value - partial,
                    period_start=_partial_end(group, annual) + timedelta(days=1),
                    fiscal_period="Q4",
                    frame=None,
                    derived=True,
                )
            )

    return derived


def _preceding_partial(group: list[Fact], annual: Fact) -> float | None:
    nine_month = _nine_month_fact(group, annual)
    if nine_month is not None:
        return nine_month.value

    quarters = _tiled_quarters(group, annual)
    if quarters is None:
        return None
    return sum(quarter.value for quarter in quarters)


def _partial_end(group: list[Fact], annual: Fact) -> date:
    nine_month = _nine_month_fact(group, annual)
    if nine_month is not None:
        return nine_month.period_end

    quarters = _tiled_quarters(group, annual)
    if quarters is None:
        raise ValueError("No partial period available for the fiscal year")
    return quarters[-1].period_end


def _nine_month_fact(group: list[Fact], annual: Fact) -> Fact | None:
    candidates = [
        fact
        for fact in group
        if fact.periodicity is Periodicity.NINE_MONTH
        and fact.period_start == annual.period_start
        and fact.period_end < annual.period_end
    ]
    return max(candidates, key=lambda fact: fact.period_end, default=None)


def _tiled_quarters(group: list[Fact], annual: Fact) -> list[Fact] | None:
    quarters = sorted(
        (fact for fact in group if fact.periodicity is Periodicity.QUARTERLY),
        key=lambda fact: fact.period_end,
    )

    tiled: list[Fact] = []
    cursor = annual.period_start
    if cursor is None:
        return None

    for quarter in quarters:
        if quarter.period_start != cursor or quarter.period_end >= annual.period_end:
            continue
        tiled.append(quarter)
        cursor = quarter.period_end + timedelta(days=1)
        if len(tiled) == 3:
            return tiled

    return None
