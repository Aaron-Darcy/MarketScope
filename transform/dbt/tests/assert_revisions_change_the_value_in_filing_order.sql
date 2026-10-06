-- A revision replaces one value with a different one from a filing no earlier than the
-- one it replaces. A row failing either condition is a comparative or a mis-ordered pair
-- counted as a restatement.

select *
from {{ ref('int_fact_revisions') }}
where revised_value = previous_value
   or revised_filed < previous_filed
