-- One row per entity event, with the quarter it falls in and the step it produced in the
-- member's deposits.
--
-- The step is measured rather than taken from the deal announcement: total deposits at the
-- end of the quarter the event completed in, against the end of the quarter before. It
-- includes whatever organic change happened in the same quarter, so it overstates an
-- acquisition slightly in a quarter of strong growth.

{{ config(materialized='table') }}

with events as (

    select
        *,
        last_day(date_trunc('quarter', event_date) + interval 2 month) as event_quarter,
        last_day(date_trunc('quarter', event_date) - interval 1 day) as previous_quarter
    from {{ ref('entity_events') }}

),

balances as (

    select cik, quarter_end, total_deposits
    from {{ ref('int_deposit_balances') }}

),

measured as (

    select
        events.*,
        before.total_deposits as deposits_before,
        after.total_deposits as deposits_after,
        case
            when events.event_type in ('acquisition', 'reverse_acquisition')
             and before.total_deposits > 0
            then after.total_deposits / before.total_deposits - 1
        end as deposit_step
    from events
    left join balances as before
      on before.cik = events.cik
     and before.quarter_end = events.previous_quarter
    left join balances as after
      on after.cik = events.cik
     and after.quarter_end = events.event_quarter

)

select
    cik,
    event_date,
    event_quarter,
    event_type,
    counterparty,
    deposits_before,
    deposits_after,
    deposit_step,
    -- An acquisition is material when it moved the deposit base by a tenth or more in the
    -- quarter it completed. Acquired deposits that cost more or less than the acquirer's
    -- shift the end-point cost by their share of the base, so at a tenth an acquired base
    -- one point dearer moves a test-cycle beta by about 0.02. A step that cannot be measured
    -- counts as material, because a size that cannot be read is not evidence of a small one.
    case
        when event_type in ('acquisition', 'reverse_acquisition')
        then coalesce(deposit_step >= 0.10, true)
    end as material,
    evidence_accession,
    evidence_form,
    evidence_item,
    note
from measured
