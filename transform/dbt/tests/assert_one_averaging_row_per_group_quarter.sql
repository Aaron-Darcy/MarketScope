select group_key, quarter_end, count(*) as rows
from {{ ref('int_regulatory_average_balances') }}
group by group_key, quarter_end
having count(*) > 1
