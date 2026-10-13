"""Cost of deposits per regulatory group and quarter, from Call Reports.

The regulatory counterpart of `int_deposit_cost`, built by the same library arithmetic so a
difference between the two is a difference in the figures rather than in the formula. A
group is summed across its insured institutions first, because SEC filings are at
holding-company level and Call Reports at institution level (specification 5).
"""

from typing import Any

import pandas as pd

from marketscope.deposit_cost import regulatory_cost_frame


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    groups = (
        dbt.ref("stg_fdic__financials")
        .query(
            "institutions",
            "select group_key, cik, quarter_end, count(*), sum(total_deposits), "
            "sum(interest_bearing_deposits), sum(deposit_expense) "
            "from institutions group by group_key, cik, quarter_end",
        )
        .fetchall()
    )
    return regulatory_cost_frame(groups)
