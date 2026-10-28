-- Two RSSD identifiers sharing one certificate in a quarter would sum two filers' items
-- under one bank.

select cert, quarter_end, count(*) as rows
from {{ ref('stg_ffiec__deposit_balances') }}
group by cert, quarter_end
having count(*) > 1
