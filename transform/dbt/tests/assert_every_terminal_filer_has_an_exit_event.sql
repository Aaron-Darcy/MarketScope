-- A member that stopped filing periodic reports has to have a recorded reason. Without an
-- exit or failure event, a filer that left the data is indistinguishable from one with a
-- coverage gap, and the survivorship comparison cannot tell the two apart. A member is
-- terminal once its last 10-K or 10-Q is more than six months older than the newest in the
-- load, two quarterly reports missed. A year let Comerica and Synovus through for most of
-- the year after their last 10-Q.

with last_report as (

    select cik, max(report_date) as last_periodic_report
    from {{ source('raw', 'sec_filings') }}
    where form in ('10-K', '10-Q')
    group by cik

),

newest as (

    select max(last_periodic_report) as newest_report
    from last_report

),

exits as (

    select distinct cik
    from {{ ref('entity_events') }}
    where event_type in ('exit_merger', 'exit_deregistration', 'failure')

)

select last_report.cik, last_report.last_periodic_report
from last_report
cross join newest
where last_report.last_periodic_report < newest.newest_report - interval 6 month
  and last_report.cik not in (select cik from exits)
