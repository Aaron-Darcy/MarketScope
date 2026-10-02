-- A bank-quarter resolves to one cost of deposits at one tier. A duplicate would mean two
-- panels were built for the same filer, and a beta could take its endpoint from either.

select
    cik,
    quarter_end,
    count(*) as rows
from {{ ref('int_deposit_cost') }}
group by cik, quarter_end
having count(*) > 1
