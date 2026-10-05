"""Every change of value for a us-gaap period, across the filings that reported it.

The record specification 4 requires of the values restatement precedence discards, and the
input to the filing behaviour question. Built by the same precedence the panel applies, so
the last revision of a period always ends on the value the metric uses. See decision 0028.
"""

from typing import Any

import pandas as pd

from marketscope.facts import DEFAULT_TAXONOMY as TAXONOMY
from marketscope.facts import FACT_FIELDS
from marketscope.restatements import revision_frame

PERIOD = "partition by cik, taxonomy, tag, unit, period_start, period_end"


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    # The financial statements are tagged in us-gaap. Of the other taxonomies, ffd carries
    # filing fees from prospectus supplements, where every note offered on a date reports
    # its own amount against the same instant, so separate offerings read as revisions of
    # one fact. That accounted for 18,978 of the 19,022 changes outside us-gaap.
    #
    # A period reported with one value throughout cannot have been revised. Those periods
    # hold more than nine in ten staged facts, so they are left in SQL rather than rebuilt
    # in Python only to produce nothing.
    facts = (
        dbt.ref("stg_sec__company_facts")
        .query(
            "facts",
            f"select {', '.join(FACT_FIELDS)} from facts where taxonomy = '{TAXONOMY}' "
            f"qualify min(value) over ({PERIOD}) <> max(value) over ({PERIOD})",
        )
        .fetchall()
    )
    return revision_frame(facts)
