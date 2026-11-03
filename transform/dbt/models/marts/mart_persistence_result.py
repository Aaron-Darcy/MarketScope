"""The pre-registered statistic, test and interval for the headline, each robustness variant
and R4 with the banks recovered from Call Reports, one row per sample.

A Python model so the site states the result the persistence analysis reports, computed by
the same functions on the same seed, rather than figures copied into a page (decision 0043).
"""

from typing import Any

import pandas as pd

from marketscope.persistence import read_filers, read_recovered, result_frame


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    # read_filers and read_recovered query these models by name on the session. Referencing
    # them declares the dependency, so dbt builds this model after them.
    dbt.ref("fct_deposit_beta")
    dbt.ref("dim_bank")
    dbt.ref("bank_entity_events")
    dbt.ref("dim_rate_cycle")
    dbt.ref("int_rate_cycles")
    dbt.ref("int_regulatory_deposit_cost")

    return result_frame(read_filers(session), read_recovered(session))
