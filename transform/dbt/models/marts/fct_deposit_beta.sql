-- Cumulative deposit beta per filer per study cycle, with the tier it was measured at.
--
-- Every universe member has a row for every study cycle, including those with no beta, so
-- a filer that stopped reporting is visible as a missing result rather than as an absent
-- one. Dropping it would reintroduce the survivorship bias specification 4 exists to
-- prevent.
--
-- A beta is taken between the cost of deposits at the two ends of the cycle, as
-- specification 3.2 defines it, against the policy move over exactly the same quarters.

{{ config(materialized='table') }}

with cycles as (

    select cycle_name, start_quarter, end_quarter
    from {{ ref('dim_rate_cycle') }}
    where cycle_name is not null

),

rates as (

    select quarter_end, rate_fraction
    from {{ ref('int_rate_cycles') }}

),

members as (

    select cik, registrant_name
    from {{ ref('stg_sec__submissions') }}

),

costs as (

    select cik, quarter_end, cost_of_deposits, metric_tier
    from {{ ref('int_deposit_cost') }}

),

last_resolved as (

    select cik, max(quarter_end) as last_quarter
    from costs
    group by cik

),

coverage as (

    select
        members.cik,
        cycles.cycle_name,
        count(*) as cycle_quarters,
        count(*) filter (where costs.metric_tier = '1') as tier_1_quarters,
        count(*) filter (where costs.metric_tier in ('1', '2')) as tier_1_or_2_quarters,
        count(distinct costs.metric_tier) as tiers_in_cycle
    from members
    cross join cycles
    join rates
      on rates.quarter_end between cycles.start_quarter and cycles.end_quarter
    left join costs
      on costs.cik = members.cik
     and costs.quarter_end = rates.quarter_end
    group by members.cik, cycles.cycle_name

),

windows as (

    select
        members.cik,
        members.registrant_name,
        cycles.cycle_name,
        cycles.start_quarter,
        cycles.end_quarter,
        -- A filer whose series ends inside the cycle is measured to its last resolved
        -- quarter and marked, rather than dropped or silently truncated into the full
        -- window. A filer that resolves later quarters but misses the peak is not partial:
        -- its gap is a coverage defect and it gets no beta.
        coalesce(
            last_resolved.last_quarter >= cycles.start_quarter
            and last_resolved.last_quarter < cycles.end_quarter,
            false
        ) as partial_cycle,
        last_resolved.last_quarter
    from members
    cross join cycles
    left join last_resolved using (cik)

),

endpoints as (

    select
        *,
        case when partial_cycle then last_quarter else end_quarter end as measured_end_quarter
    from windows

)

select
    endpoints.cik,
    endpoints.registrant_name,
    endpoints.cycle_name,
    endpoints.start_quarter,
    endpoints.end_quarter,
    endpoints.measured_end_quarter,
    endpoints.partial_cycle,
    start_cost.metric_tier as start_tier,
    end_cost.metric_tier as end_tier,
    -- The beta is only as comparable as its less precise endpoint. Tiers sort in order of
    -- decreasing precision, so the greater of the two is that endpoint's tier.
    greatest(start_cost.metric_tier, end_cost.metric_tier) as metric_tier,
    coverage.tiers_in_cycle > 1 as tier_changes_in_cycle,
    start_cost.cost_of_deposits as start_cost_of_deposits,
    end_cost.cost_of_deposits as end_cost_of_deposits,
    start_rate.rate_fraction as start_rate_fraction,
    end_rate.rate_fraction as end_rate_fraction,
    -- Tier X failed the completeness check, so its cost is known to be understated and a
    -- beta from it would read as a slow repricer rather than as missing data.
    case
        when start_cost.metric_tier <> 'X'
         and end_cost.metric_tier <> 'X'
         and end_rate.rate_fraction <> start_rate.rate_fraction
        then (end_cost.cost_of_deposits - start_cost.cost_of_deposits)
           / (end_rate.rate_fraction - start_rate.rate_fraction)
    end as deposit_beta,
    coverage.cycle_quarters,
    coverage.tier_1_quarters,
    coverage.tier_1_or_2_quarters
from endpoints
join coverage
  on coverage.cik = endpoints.cik
 and coverage.cycle_name = endpoints.cycle_name
join rates as start_rate
  on start_rate.quarter_end = endpoints.start_quarter
join rates as end_rate
  on end_rate.quarter_end = endpoints.measured_end_quarter
left join costs as start_cost
  on start_cost.cik = endpoints.cik
 and start_cost.quarter_end = endpoints.start_quarter
left join costs as end_cost
  on end_cost.cik = endpoints.cik
 and end_cost.quarter_end = endpoints.measured_end_quarter
