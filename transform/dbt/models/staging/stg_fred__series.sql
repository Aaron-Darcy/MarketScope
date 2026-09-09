-- Policy and Treasury rate observations, as percentages exactly as FRED publishes them.
--
-- Conversion to a decimal fraction happens where the beta is computed, not here, so the
-- staging layer stays a faithful restatement of the source and the unit conversion has one
-- home rather than two.

select
    series_id,
    observation_date,
    value as rate_percent,
    value / 100.0 as rate_fraction
from {{ source('raw', 'fred_observations') }}
where value is not null
