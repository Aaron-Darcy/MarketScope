-- A named cycle must run from a lower rate to a higher one. A negative move would mean
-- liftoff and peak have been paired the wrong way round, which the window functions that
-- build the pairing would otherwise do silently.

select
    cycle_name,
    start_quarter,
    end_quarter,
    move_fraction
from {{ ref('dim_rate_cycle') }}
where cycle_name is not null
  and move_fraction <= 0
