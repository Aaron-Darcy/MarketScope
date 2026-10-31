-- Specification 7.2: no bank-quarter appears twice. A second row would count a quarter's
-- cost twice in any coverage figure built on the table.

select cik, quarter_end, count(*) as rows
from {{ ref('fct_bank_quarter') }}
group by cik, quarter_end
having count(*) > 1
