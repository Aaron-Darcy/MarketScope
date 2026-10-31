-- One row per universe member and quarter end at which a cost of deposits or a deposit
-- balance resolves, with the policy rate, the study cycle the quarter falls in and the
-- entity event completing in it.
--
-- The grain is the union of the two intermediate tables rather than either alone. A balance
-- matters where no cost resolves, as when an acquisition closes in a quarter whose expense
-- is untagged, and a cost can resolve on a closing balance the balance table does not carry
-- for the quarter before. Specification 4 asks for the bank-quarters an entity event affects
-- to be flagged, which decision 0033 moved here from Milestone 2.

{{ config(materialized='table') }}

with keys as (

    select cik, quarter_end from {{ ref('int_deposit_cost') }}
    union
    select cik, quarter_end from {{ ref('int_deposit_balances') }}

),

cycles as (

    select cycle_name, start_quarter, end_quarter
    from {{ ref('dim_rate_cycle') }}
    where cycle_name is not null

)

select
    keys.cik,
    keys.quarter_end,
    costs.cost_of_deposits,
    costs.metric_tier,
    costs.expense_provenance,
    costs.balance_provenance,
    costs.avg_method,
    costs.component_coverage,
    costs.q4_derived,
    balances.total_deposits,
    balances.interest_bearing_deposits,
    balances.interest_bearing_provenance,
    balances.noninterest_bearing_deposits,
    balances.noninterest_bearing_provenance,
    rates.rate_fraction as policy_rate_fraction,
    cycles.cycle_name,
    events.event_type,
    events.counterparty as event_counterparty,
    events.deposit_step as event_deposit_step,
    -- False rather than null where no acquisition completed, so a filter on the flag cannot
    -- drop the quarters it is meant to keep. An exit or failure is not an acquisition and
    -- has no materiality of its own.
    coalesce(events.material, false) as material_event
from keys
left join {{ ref('int_deposit_cost') }} as costs
  on costs.cik = keys.cik
 and costs.quarter_end = keys.quarter_end
left join {{ ref('int_deposit_balances') }} as balances
  on balances.cik = keys.cik
 and balances.quarter_end = keys.quarter_end
left join {{ ref('int_rate_cycles') }} as rates
  on rates.quarter_end = keys.quarter_end
left join cycles
  on keys.quarter_end between cycles.start_quarter and cycles.end_quarter
left join {{ ref('bank_entity_events') }} as events
  on events.cik = keys.cik
 and events.event_quarter = keys.quarter_end
