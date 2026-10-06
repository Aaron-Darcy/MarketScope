-- A revised period ends on exactly one value, the one restatement precedence keeps. Two
-- current rows would mean the revisions and the panel disagree about which filing won;
-- none would mean a chain was cut short.

select
    cik,
    taxonomy,
    tag,
    unit,
    period_start,
    period_end,
    count(*) filter (where is_current) as current_rows
from {{ ref('int_fact_revisions') }}
group by all
having count(*) filter (where is_current) <> 1
