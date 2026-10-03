-- A beta's tier is the less precise of its two endpoint tiers, so it exists only where
-- both endpoints resolved. A tier on a row with a missing endpoint would let a filer with
-- no beta pass a filter on tier as though it had been measured.

select
    cik,
    registrant_name,
    cycle_name,
    start_tier,
    end_tier,
    metric_tier
from {{ ref('fct_deposit_beta') }}
where (start_tier is null or end_tier is null) <> (metric_tier is null)
