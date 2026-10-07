"""The deposit base at every quarter end, whether or not a cost of deposits resolves there.

Resolved by the same library functions as the cost of deposits, so the interest-bearing base
here is the one a cost divides by, reconciliation included. Kept apart from
`int_deposit_cost` because a balance is needed where no cost resolves, as when an
acquisition closes in a quarter whose expense is untagged.
"""

from typing import Any

import pandas as pd

from marketscope.deposit_cost import deposit_balance_frame
from marketscope.facts import FACT_FIELDS
from marketscope.panel import BALANCE_TAGS


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    concepts = ", ".join(f"'{tag}'" for tag in sorted(BALANCE_TAGS))
    facts = (
        dbt.ref("stg_sec__company_facts")
        .filter(f"tag in ({concepts})")
        .project(", ".join(FACT_FIELDS))
        .fetchall()
    )
    return deposit_balance_frame(facts)
