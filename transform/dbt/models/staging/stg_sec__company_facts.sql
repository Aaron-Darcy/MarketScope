-- Every USD fact for a universe member, typed and classified by period length.
--
-- Periodicity is derived from the reported span rather than from the fiscal period label,
-- because the label describes the filing a fact appeared in and not the period the fact
-- covers: a Q3 10-Q carries year-to-date figures alongside quarterly ones under the same
-- label. Restatement precedence is deliberately not applied here — the superseded values
-- are the input to the filing behaviour question and are dropped downstream, once.

with facts as (

    select
        cik,
        taxonomy,
        tag,
        unit,
        value,
        period_start,
        period_end,
        filed,
        accession,
        form,
        fiscal_year,
        fiscal_period,
        frame
    from {{ source('raw', 'sec_facts') }}

),

classified as (

    select
        *,
        case
            when period_start is null then null
            else date_diff('day', period_start, period_end)
        end as period_days
    from facts

)

select
    cik,
    taxonomy,
    tag,
    unit,
    value,
    period_start,
    period_end,
    period_days,
    case
        when period_days is null then 'instant'
        when period_days between 80 and 100 then 'quarterly'
        when period_days between 170 and 190 then 'semiannual'
        when period_days between 260 and 290 then 'nine_month'
        when period_days between 350 and 380 then 'annual'
        else 'other'
    end as periodicity,
    filed,
    accession,
    form,
    fiscal_year,
    fiscal_period,
    frame
from classified
