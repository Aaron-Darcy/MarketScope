-- One row per universe member: what it is, how it entered the universe, and whether and how
-- it left the data.
--
-- Specification 4 retains terminal filers with their last filed period and an exit reason,
-- so that every headline result can be reported with and without them. The exit comes from
-- the event record, which a test requires of every member that stopped filing, so a filer
-- that left the data cannot appear here as one still reporting.

{{ config(materialized='table') }}

with members as (

    select
        cik,
        registrant_name,
        rank,
        pinned,
        pinned_reason,
        sic,
        sic_description,
        state_of_incorporation,
        fiscal_year_end
    from {{ ref('stg_sec__submissions') }}

),

periodic as (

    select
        cik,
        min(report_date) as first_filed_period,
        max(report_date) as last_filed_period
    from {{ source('raw', 'sec_filings') }}
    where form in ('10-K', '10-Q')
    group by cik

),

exits as (

    select
        cik,
        event_type as exit_type,
        event_date as exit_date,
        counterparty as exit_counterparty
    from {{ ref('entity_events') }}
    where event_type in ('exit_merger', 'exit_deregistration', 'failure')

),

acquisitions as (

    select
        cik,
        count(*) as acquisitions,
        count(*) filter (where material) as material_acquisitions
    from {{ ref('bank_entity_events') }}
    where event_type in ('acquisition', 'reverse_acquisition')
    group by cik

)

select
    members.cik,
    members.registrant_name,
    members.rank,
    members.pinned,
    members.pinned_reason,
    members.sic,
    members.sic_description,
    members.state_of_incorporation,
    members.fiscal_year_end,
    periodic.first_filed_period,
    periodic.last_filed_period,
    exits.exit_type is not null as is_terminal,
    exits.exit_type,
    exits.exit_date,
    exits.exit_counterparty,
    coalesce(acquisitions.acquisitions, 0) as acquisitions,
    coalesce(acquisitions.material_acquisitions, 0) as material_acquisitions
from members
left join periodic using (cik)
left join exits using (cik)
left join acquisitions using (cik)
