-- The overview counts every resolved bank-quarter exactly once, so its coverage figures sum
-- to the cost table's.

select
    (select sum(cost_quarters) from {{ ref('mart_bank_overview') }}) as overview_quarters,
    (select count(*) from {{ ref('int_deposit_cost') }}) as resolved_quarters
where (select sum(cost_quarters) from {{ ref('mart_bank_overview') }})
   <> (select count(*) from {{ ref('int_deposit_cost') }})
