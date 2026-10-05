from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

import pandas as pd

from marketscope.facts import Fact, Revision, facts_from_rows, revisions

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
