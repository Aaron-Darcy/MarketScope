-- The comparison mart reads its betas through the library rather than by a ref, so it is
-- held to the fact table it should have read: a mart built from a stale or different table
-- would place banks on betas the site's other pages do not show.

select comparison.cik, betas.cycle_name, betas.deposit_beta,
    comparison.calibration_beta, comparison.test_beta
from {{ ref('mart_cross_bank_comparison') }} as comparison
join {{ ref('fct_deposit_beta') }} as betas using (cik)
where betas.deposit_beta is distinct from case betas.cycle_name
        when 'calibration' then comparison.calibration_beta
        when 'test' then comparison.test_beta
    end
