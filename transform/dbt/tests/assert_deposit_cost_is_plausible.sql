-- Specification 7.2: an annualised cost of deposits outside 0 to 8 percent is a data fault
-- rather than a bank. Breaches warn rather than fail and the row is kept, because nulling
-- it would hide the fault from every result built on it. Tier X is excluded: its numerator
-- is already known to be incomplete and no result uses it.

{{ config(severity='warn') }}

select
    cik,
    quarter_end,
    metric_tier,
    cost_of_deposits
from {{ ref('int_deposit_cost') }}
where metric_tier <> 'X'
  and (cost_of_deposits < 0 or cost_of_deposits > 0.08)
