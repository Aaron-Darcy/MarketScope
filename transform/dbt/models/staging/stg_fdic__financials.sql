-- Call Report deposit figures per insured institution and quarter, in dollars.
--
-- The FDIC publishes in thousands. Quarterly deposit interest expense is the sum of domestic
-- and foreign offices. An institution filing the domestic-only Call Report has no foreign
-- offices and the FDIC leaves its foreign figure null, so that figure adds nothing rather
-- than making the quarter unknown; the domestic figure is present on every row.

select
    group_key,
    cik,
    cert,
    report_date as quarter_end,
    rssd_hcr,
    dep * 1000 as total_deposits,
    depi * 1000 as interest_bearing_deposits,
    depni * 1000 as noninterest_bearing_deposits,
    (edepdomq + coalesce(edepforq, 0)) * 1000 as deposit_expense
from {{ source('raw', 'fdic_financials') }}
