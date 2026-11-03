-- The result mart and the comparison mart place filers through the same rules but in
-- separate models, so each sample's size is held to the filers the comparison admits to it.
-- A page stating a correlation over a sample the comparison page does not show would
-- contradict itself. The recovered sample is R4 plus the two banks decision 0034 names.

with admitted as (

    select 'headline' as sample, count(*) filter (where in_headline) as filers
    from {{ ref('mart_cross_bank_comparison') }}
    union all
    select 'R1', count(*) filter (where in_r1) from {{ ref('mart_cross_bank_comparison') }}
    union all
    select 'R2', count(*) filter (where in_r2) from {{ ref('mart_cross_bank_comparison') }}
    union all
    select 'R3', count(*) filter (where in_r3) from {{ ref('mart_cross_bank_comparison') }}
    union all
    select 'R4', count(*) filter (where in_r4) from {{ ref('mart_cross_bank_comparison') }}
    union all
    select 'R4+recovered', count(*) filter (where in_r4) + 2
    from {{ ref('mart_cross_bank_comparison') }}

)

select admitted.sample, admitted.filers as admitted, results.filers as reported
from admitted
full join {{ ref('mart_persistence_result') }} as results using (sample)
where admitted.filers is distinct from results.filers
