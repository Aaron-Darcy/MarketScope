-- Each headline filer has a rank in both cycles and no other filer has one, and the ranks of
-- each cycle are a full set from 1 to the sample size, ties averaged, so their sum is fixed.

with headline as (

    select
        count(*) as filers,
        sum(calibration_rank) as calibration_sum,
        sum(test_rank) as test_sum
    from {{ ref('mart_cross_bank_comparison') }}
    where in_headline

)

select 'misplaced' as failure, cik
from {{ ref('mart_cross_bank_comparison') }}
where in_headline <> (calibration_rank is not null and test_rank is not null)
   or (calibration_rank is null) <> (test_rank is null)
union all
select 'incomplete', null
from headline
where abs(calibration_sum - filers * (filers + 1) / 2.0) > 1e-9
   or abs(test_sum - filers * (filers + 1) / 2.0) > 1e-9
