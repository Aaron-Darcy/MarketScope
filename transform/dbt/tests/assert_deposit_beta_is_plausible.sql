-- A cumulative beta outside 0 to 1 cannot be a pass-through share: above 1 the bank raised
-- deposit rates by more than the policy rate moved, and below 0 its deposit cost fell
-- across a tightening cycle. Either marks a faulty endpoint rather than a bank. Warns
-- rather than fails, because the finding is recorded and carried (decisions 0022 and 0023)
-- and the beta stays on the row for the analysis to exclude openly.

{{ config(severity='warn') }}

select
    cik,
    registrant_name,
    cycle_name,
    metric_tier,
    start_cost_of_deposits,
    end_cost_of_deposits,
    deposit_beta
from {{ ref('fct_deposit_beta') }}
where deposit_beta < 0 or deposit_beta > 1
