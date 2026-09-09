-- One row per universe member, joining registrant metadata to its filing history summary.
--
-- The registrant name comes from the submissions endpoint. The entityName field on company
-- facts reports whichever entity published a given fact rather than the registrant — CIK
-- 70858 is Bank of America but reports BofA Finance LLC — so it is never used as a key.

with registrants as (

    select
        cik,
        registrant_name,
        sic,
        sic_description,
        entity_type,
        state_of_incorporation,
        fiscal_year_end
    from {{ source('raw', 'sec_registrants') }}

),

annual_reports as (

    select
        cik,
        count(*) filter (where form = '10-K') as ten_k_count,
        count(*) filter (where form in ('20-F', '40-F')) as foreign_annual_forms,
        min(report_date) filter (where form = '10-K') as first_ten_k,
        max(report_date) filter (where form = '10-K') as last_ten_k,
        max(filing_date) as last_filing_date
    from {{ source('raw', 'sec_filings') }}
    group by cik

),

universe as (

    select cik, rank, pinned, pinned_reason
    from {{ source('raw', 'universe') }}

)

select
    universe.cik,
    registrants.registrant_name,
    registrants.sic,
    registrants.sic_description,
    registrants.entity_type,
    registrants.state_of_incorporation,
    registrants.fiscal_year_end,
    universe.rank,
    universe.pinned,
    universe.pinned_reason,
    coalesce(annual_reports.ten_k_count, 0) as ten_k_count,
    coalesce(annual_reports.foreign_annual_forms, 0) as foreign_annual_forms,
    annual_reports.first_ten_k,
    annual_reports.last_ten_k,
    annual_reports.last_filing_date
from universe
left join registrants using (cik)
left join annual_reports using (cik)
