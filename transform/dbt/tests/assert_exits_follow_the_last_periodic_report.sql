-- An exit dated before the period of the filer's last 10-K or 10-Q would mean the filer
-- went on reporting after leaving, so either the date or the event is wrong.

with last_report as (

    select cik, max(report_date) as last_periodic_report
    from {{ source('raw', 'sec_filings') }}
    where form in ('10-K', '10-Q')
    group by cik

)

select events.cik, events.event_date, last_report.last_periodic_report
from {{ ref('entity_events') }} as events
join last_report using (cik)
where events.event_type in ('exit_merger', 'exit_deregistration', 'failure')
  and events.event_date < last_report.last_periodic_report
