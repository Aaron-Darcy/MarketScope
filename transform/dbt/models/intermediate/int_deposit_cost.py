"""Cost of deposits per bank-quarter, resolved at the most precise tier each supports.

A Python model rather than SQL so the metric has one implementation: the tier logic,
restatement precedence and fourth-quarter derivation are those `marketscope` tests
directly and the Milestone 2 analysis already reads. See decision 0024.
"""

from typing import Any

import pandas as pd

from marketscope.deposit_cost import FACT_FIELDS, deposit_cost_frame
from marketscope.panel import PANEL_TAGS


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    concepts = ", ".join(f"'{tag}'" for tag in sorted(PANEL_TAGS))
    facts = (
        dbt.ref("stg_sec__company_facts")
        .filter(f"tag in ({concepts})")
        .project(", ".join(FACT_FIELDS))
        .fetchall()
    )
    return deposit_cost_frame(facts)
