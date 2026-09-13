-- One row per monetary cycle, derived from the policy rate rather than hardcoded.
--
-- A tightening cycle runs from liftoff to peak. Liftoff is the last quarter the rate sat at
-- its floor, not the first: the rate is flat at the floor for years before a cycle begins,
-- so taking the earliest trough quarter would start the 2022 cycle in 2020 and dilute the
-- move across eight quarters in which nothing happened.

{{ config(materialized='table') }}

with cycles as (

    select
        quarter_end as peak_quarter,
        rate_percent as peak_rate,
        lag(quarter_end) over (order by quarter_end) as previous_peak
    from {{ ref('int_rate_cycles') }}
    where is_peak
      and rate_percent > (select min(rate_percent) from {{ ref('int_rate_cycles') }}) + 1.0

),

floors as (

    select
        cycles.peak_quarter,
        cycles.peak_rate,
        min(rates.rate_percent) as floor_rate
    from cycles
    join {{ ref('int_rate_cycles') }} as rates
      on rates.quarter_end < cycles.peak_quarter
     and (cycles.previous_peak is null or rates.quarter_end > cycles.previous_peak)
    group by 1, 2

),

liftoff as (

    select
        floors.peak_quarter,
        floors.peak_rate,
        floors.floor_rate,
        -- The last quarter still at the floor, within a tolerance that absorbs the drift
        -- of an administered rate held in a target range rather than at a point.
        max(rates.quarter_end) as start_quarter
    from floors
    join {{ ref('int_rate_cycles') }} as rates
      on rates.quarter_end < floors.peak_quarter
     and rates.rate_percent <= floors.floor_rate + 0.15
    group by 1, 2, 3

),

named as (

    select
        liftoff.*,
        -- Named by recency rather than by date, so the study follows the rate series
        -- forward without anyone editing a window. Earlier cycles are retained unnamed:
        -- they cost nothing and they are the context for saying this one was unusually fast.
        row_number() over (order by liftoff.start_quarter desc) as recency
    from liftoff

)

select
    row_number() over (order by named.start_quarter) as cycle_key,
    case named.recency when 1 then 'test' when 2 then 'calibration' end as cycle_name,
    'tightening' as phase,
    named.start_quarter,
    named.peak_quarter as end_quarter,
    start_rate.rate_fraction as start_rate_fraction,
    end_rate.rate_fraction as end_rate_fraction,
    end_rate.rate_fraction - start_rate.rate_fraction as move_fraction,
    datediff('month', named.start_quarter, named.peak_quarter) as months
from named
join {{ ref('int_rate_cycles') }} as start_rate
  on start_rate.quarter_end = named.start_quarter
join {{ ref('int_rate_cycles') }} as end_rate
  on end_rate.quarter_end = named.peak_quarter
order by named.start_quarter
