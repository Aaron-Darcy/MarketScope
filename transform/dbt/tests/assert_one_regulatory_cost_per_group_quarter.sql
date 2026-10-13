-- The validation pairs each bank-quarter with one regulatory figure. A duplicate group-quarter
-- would let the error be measured against either of two.

select group_key, quarter_end, count(*) as rows
from {{ ref('int_regulatory_deposit_cost') }}
group by group_key, quarter_end
having count(*) > 1
