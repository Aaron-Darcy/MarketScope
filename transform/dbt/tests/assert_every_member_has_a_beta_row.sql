-- Every universe member appears once in every study cycle, whether or not a beta can be
-- measured for it. A filer that failed or stopped reporting must stay visible, or every
-- result built on the fact table silently becomes a survivors-only result.

with expected as (

    select universe.cik, cycles.cycle_name
    from {{ source('raw', 'universe') }} as universe
    cross join {{ ref('dim_rate_cycle') }} as cycles
    where cycles.cycle_name is not null

),

actual as (

    select cik, cycle_name, count(*) as rows
    from {{ ref('fct_deposit_beta') }}
    group by cik, cycle_name

)

select
    expected.cik,
    expected.cycle_name,
    coalesce(actual.rows, 0) as rows
from expected
left join actual using (cik, cycle_name)
where coalesce(actual.rows, 0) <> 1
