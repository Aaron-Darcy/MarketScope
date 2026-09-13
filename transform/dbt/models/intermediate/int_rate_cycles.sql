-- Quarterly policy rate with its turning points marked.
--
-- Turning points are found on the level series with a centred four-quarter window rather
-- than from quarter-on-quarter changes. The 2015 to 2019 tightening was slow and punctuated
-- by pauses, so a change-based rule fragments it into three separate runs, and a
-- year-on-year rule mislabels both ends because the comparison lags the turn.

{{ config(materialized='view') }}

with quarterly as (

    select
        -- FRED publishes the policy rate monthly; the metric is quarterly.
        last_day(date_trunc('quarter', observation_date) + interval 2 month) as quarter_end,
        avg(rate_percent) as rate_percent
    from {{ ref('stg_fred__series') }}
    where series_id = 'FEDFUNDS'
    group by 1

),

windowed as (

    select
        quarter_end,
        rate_percent,
        min(rate_percent) over (
            order by quarter_end rows between 4 preceding and 4 following
        ) as window_low,
        max(rate_percent) over (
            order by quarter_end rows between 4 preceding and 4 following
        ) as window_high
    from quarterly

)

select
    quarter_end,
    rate_percent,
    rate_percent / 100.0 as rate_fraction,
    rate_percent = window_low as is_trough,
    rate_percent = window_high as is_peak
from windowed
