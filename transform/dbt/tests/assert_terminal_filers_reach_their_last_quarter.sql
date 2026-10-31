-- Specification 7.2: terminal filers stay in the fact table, as a regression test against
-- reintroducing survivorship bias. Each member that stopped filing must carry a resolved
-- cost of deposits in the last quarter it filed, which is the endpoint a partial-cycle beta
-- is measured to and the point gate criterion G3 required to be retrievable.

select members.cik, members.registrant_name, members.last_filed_period
from {{ ref('dim_bank') }} as members
left join {{ ref('fct_bank_quarter') }} as quarters
  on quarters.cik = members.cik
 and quarters.quarter_end = members.last_filed_period
 and quarters.cost_of_deposits is not null
where members.is_terminal
  and quarters.cik is null
