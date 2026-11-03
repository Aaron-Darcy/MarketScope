"""Cycle betas of First Republic and Signature, the failed banks EDGAR does not hold,
recovered from their Call Reports for the survivorship comparison (decision 0034).

They are not members, so they appear in no other mart, and the comparison page states them
beside the result as 0042 requires. Read through the library the persistence analysis uses
(decision 0043).
"""

from typing import Any

import pandas as pd

from marketscope.persistence import read_recovered, recovered_frame


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    # read_recovered queries these models by name on the session. Referencing them declares
    # the dependency, so dbt builds this model after them.
    dbt.ref("dim_rate_cycle")
    dbt.ref("int_rate_cycles")
    dbt.ref("int_regulatory_deposit_cost")

    return recovered_frame(read_recovered(session))
