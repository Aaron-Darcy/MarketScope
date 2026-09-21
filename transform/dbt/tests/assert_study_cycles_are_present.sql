-- The analysis reads the calibration and test cycles by name. A rate series that ends
-- before the latest peak, or a derivation change that merges two cycles, would leave one
-- unnamed, and the failure belongs here rather than in whichever script reads it first.
--
-- Uniqueness is tested separately and is not incidental. A plateau at the peak marks every
-- quarter on it as a peak, and the model collapses them to one cycle only because no
-- quarter lies strictly between two adjacent peaks for the floor join to find.

select required.cycle_name
from (values ('calibration'), ('test')) as required(cycle_name)
left join {{ ref('dim_rate_cycle') }} as cycles
  on cycles.cycle_name = required.cycle_name
where cycles.cycle_name is null
