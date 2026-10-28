"""Endpoint averaging error per regulatory group and quarter, against Call Report averages.

Groups are the BankFind groups of `int_regulatory_deposit_cost`, summed across their
insured institutions, so the error applies to the same group-quarters as the regulatory
cost of deposits. Each group is measured on the basis its Schedule RC-K averages reconcile
to (decision 0039).
"""

from typing import Any

import pandas as pd

from marketscope.averaging import Basis, GroupQuarter, averaging_frame


# dbt passes its own context object and a DuckDB connection, neither of which is typed.
def model(dbt: Any, session: Any) -> pd.DataFrame:
    dbt.config(materialized="table")

    balances = dbt.ref("stg_ffiec__deposit_balances").project(
        "cert as ffiec_cert, quarter_end as ffiec_quarter_end, "
        "average_interest_bearing_transaction + average_savings + average_time "
        "+ coalesce(average_foreign_interest_bearing, 0) as average_interest_bearing, "
        "average_savings + average_time + coalesce(average_foreign_interest_bearing, 0) "
        "as average_nontransaction, "
        "domestic_interest_bearing + coalesce(foreign_interest_bearing, 0) "
        "as closing_interest_bearing, "
        "nontransaction + coalesce(foreign_interest_bearing, 0) as closing_nontransaction"
    )
    joined = dbt.ref("stg_fdic__financials").join(
        balances,
        "cert = ffiec_cert and quarter_end = ffiec_quarter_end",
        how="left",
    )
    # A quarter the archives do not hold has no average for any institution and is left
    # out. One held with an institution missing is passed on, and the library refuses it.
    rows = joined.query(
        "institutions",
        "select group_key, any_value(cik), quarter_end, count(*), count(ffiec_cert), "
        "sum(average_interest_bearing), sum(average_nontransaction), "
        "sum(closing_interest_bearing), sum(closing_nontransaction) "
        "from institutions group by group_key, quarter_end "
        "having count(ffiec_cert) > 0",
    ).fetchall()

    return averaging_frame(
        GroupQuarter(
            group_key=group_key,
            cik=cik,
            quarter_end=quarter_end,
            institutions=count,
            averaged_institutions=averaged,
            average={Basis.INTEREST_BEARING: average_ib, Basis.NONTRANSACTION: average_nt},
            closing={Basis.INTEREST_BEARING: closing_ib, Basis.NONTRANSACTION: closing_nt},
        )
        for (
            group_key,
            cik,
            quarter_end,
            count,
            averaged,
            average_ib,
            average_nt,
            closing_ib,
            closing_nt,
        ) in rows
    )
