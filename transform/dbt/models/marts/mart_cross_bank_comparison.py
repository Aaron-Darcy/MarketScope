"""Every member's cycle betas, the pre-registered samples it enters and its place in the
headline, for the site's comparison pages.

A Python model so the sample rules, ranks and quartiles are the ones `marketscope.persistence`
defines and the persistence analysis reports, not a second implementation in SQL
(decision 0042).
"""

from typing import Any

import pandas as pd

from marketscope.persistence import comparison_frame, read_filers


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    # read_filers queries these marts by name on the session. Referencing them declares the
    # dependency, so dbt builds this model after them.
    dbt.ref("fct_deposit_beta")
    dbt.ref("dim_bank")
    dbt.ref("bank_entity_events")
    dbt.ref("dim_rate_cycle")

    return comparison_frame(read_filers(session))
