-- The deposit step of an entity event is read from one row per filer and quarter end. A
-- duplicate would let the step be measured against either of two balances.

select cik, quarter_end, count(*) as rows
from {{ ref('int_deposit_balances') }}
group by cik, quarter_end
having count(*) > 1
