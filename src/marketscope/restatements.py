from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd

from marketscope.facts import Fact, Revision, facts_from_rows, revisions


class RevisionKind(StrEnum):
    """What a revision changed, judged from the two values and the revising form alone."""

    PRECISION = "precision"
    SIGN = "sign"
    SCALE = "scale"
    AMENDMENT = "amendment"
    SUBSTANTIVE = "substantive"


# Filers round to thousands at the finest and to billions at the coarsest.
_ROUNDING_UNITS: tuple[float, ...] = (1e9, 1e8, 1e7, 1e6, 1e5, 1e4, 1e3)


def _rounding_unit(value: float) -> float:
    """The coarsest power of ten from a thousand up that a value is a whole multiple of.

    Zero is a multiple of every unit, so it says nothing about how a figure was rounded and
    is given no rounding at all.
    """
    if value == 0:
        return 1.0
    return next((unit for unit in _ROUNDING_UNITS if value % unit == 0), 1.0)


def classify_revision(previous: float, revised: float, revised_form: str | None) -> RevisionKind:
    """Classify a change of published value by its mechanical signature.

    A figure republished at a coarser rounding, $53,263,000 as $53,000,000, is the same
    figure. A sign reversal of the same magnitude is a change of presentation convention,
    and a factor of a thousand is a scale error in one of the two filings. An amendment is
    named by its form. Whatever is left changed the number itself, by correction,
    reclassification or recast, which the values alone cannot tell apart.
    """
    unit = max(_rounding_unit(previous), _rounding_unit(revised))
    if unit > 1 and abs(revised - previous) <= unit / 2:
        return RevisionKind.PRECISION
    if revised == -previous:
        return RevisionKind.SIGN
    if (
        previous != 0
        and revised != 0
        and 999 <= max(abs(revised / previous), abs(previous / revised)) <= 1001
    ):
        return RevisionKind.SCALE
    if revised_form is not None and revised_form.endswith("/A"):
        return RevisionKind.AMENDMENT
    return RevisionKind.SUBSTANTIVE


REVISION_COLUMNS: tuple[str, ...] = (
    "cik",
    "taxonomy",
    "tag",
    "unit",
    "period_start",
    "period_end",
    "periodicity",
    "revision_number",
    "previous_value",
    "previous_filed",
    "previous_accession",
    "previous_form",
    "revised_value",
    "revised_filed",
    "revised_accession",
    "revised_form",
    "is_current",
)


def revision_rows(cik: int, facts: Iterable[Fact]) -> list[tuple[Any, ...]]:
    """Every revision in one filer's facts, in `REVISION_COLUMNS` order.

    Revisions are numbered from 1 within each period, so the first row for a period holds
    the value as originally published and the row marked current holds the value the panel
    uses.
    """
    # A period key carries no taxonomy, and one concept name in two taxonomies is two
    # concepts, so each taxonomy's revisions are found separately.
    by_taxonomy: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        by_taxonomy[fact.taxonomy].append(fact)

    rows: list[tuple[Any, ...]] = []
    for taxonomy in sorted(by_taxonomy):
        chains: dict[tuple[str, str, date | None, date], list[Revision]] = defaultdict(list)
        for revision in revisions(by_taxonomy[taxonomy]):
            chains[revision.revised.period_key].append(revision)

        for chain in chains.values():
            for number, revision in enumerate(chain, start=1):
                previous, revised = revision.previous, revision.revised
                rows.append(
                    (
                        cik,
                        taxonomy,
                        revised.tag,
                        revised.unit,
                        revised.period_start,
                        revised.period_end,
                        revised.periodicity.value,
                        number,
                        previous.value,
                        previous.filed,
                        previous.accession,
                        previous.form,
                        revised.value,
                        revised.filed,
                        revised.accession,
                        revised.form,
                        number == len(chain),
                    )
                )
    return rows


def revision_frame(rows: Iterable[tuple[Any, ...]]) -> pd.DataFrame:
    """Every revision across every filer in a set of staged fact rows."""
    found: list[tuple[Any, ...]] = []
    for cik, facts in sorted(facts_from_rows(rows).items()):
        found.extend(revision_rows(cik, facts))
    return pd.DataFrame(found, columns=list(REVISION_COLUMNS))
