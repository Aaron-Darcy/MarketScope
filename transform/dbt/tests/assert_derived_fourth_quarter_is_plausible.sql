-- Specification 7.2: a fourth quarter derived as fiscal year less nine months must be
-- non-negative and within band of its neighbouring quarters. The derivation subtracts two
-- separately reported figures, so a mismatch between them lands entirely in one quarter.
--
-- The band is one percentage point outside the range of the two neighbours, three times
-- the largest such distance among second quarters, whose neighbours are both reported
-- (decision 0025). A quarter lying on a trend between its neighbours is never flagged.
-- Warns rather than fails, because the finding is carried and the row kept.

{{ config(severity='warn') }}

with quarters as (

    select
        cik,
        quarter_end,
        metric_tier,
        cost_of_deposits,
        q4_derived,
        lag(quarter_end) over by_filer as previous_quarter,
        lag(cost_of_deposits) over by_filer as previous_cost,
        lead(quarter_end) over by_filer as next_quarter,
        lead(cost_of_deposits) over by_filer as next_cost
    from {{ ref('int_deposit_cost') }}
    -- Tier X is known to be understated and would distort its neighbours' band.
    where metric_tier <> 'X'
    window by_filer as (partition by cik order by quarter_end)

),

banded as (

    select
        *,
        case
            when datediff('month', previous_quarter, quarter_end) = 3
             and datediff('month', quarter_end, next_quarter) = 3
            then greatest(
                least(previous_cost, next_cost) - cost_of_deposits,
                cost_of_deposits - greatest(previous_cost, next_cost),
                0
            )
        end as distance_outside_neighbours
    from quarters

)

select
    cik,
    quarter_end,
    metric_tier,
    previous_cost,
    cost_of_deposits,
    next_cost,
    distance_outside_neighbours
from banded
where q4_derived
  and (cost_of_deposits < 0 or distance_outside_neighbours > 0.01)
