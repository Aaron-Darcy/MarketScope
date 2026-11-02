-- Specification 7.2: at least 80 percent quarterly coverage for any bank in a headline
-- result. The rule is applied by the persistence library (0034); this holds the warehouse's
-- headline flag to it independently, on tier 1 quarters over each full cycle.

select comparison.cik, betas.cycle_name, betas.tier_1_quarters, betas.cycle_quarters
from {{ ref('mart_cross_bank_comparison') }} as comparison
join {{ ref('fct_deposit_beta') }} as betas using (cik)
where comparison.in_headline
  and betas.tier_1_quarters < 0.8 * betas.cycle_quarters
