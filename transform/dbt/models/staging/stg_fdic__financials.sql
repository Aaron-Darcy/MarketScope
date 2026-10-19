-- Call Report deposit figures per insured institution and quarter, in dollars.
--
-- The FDIC publishes in thousands. Quarterly deposit interest expense is the sum of domestic
-- and foreign offices. An institution filing the domestic-only Call Report has no foreign
-- offices and the FDIC leaves its foreign figures null, so they add nothing rather than
-- making the quarter unknown; the domestic figures are present on every row. The office
-- columns are kept null where the FDIC leaves them out, so a foreign cost is never read as
-- zero for a bank with no foreign offices.

select
    group_key,
    cik,
    cert,
    report_date as quarter_end,
    rssd_hcr,
    dep * 1000 as total_deposits,
    depi * 1000 as interest_bearing_deposits,
    depni * 1000 as noninterest_bearing_deposits,
    (edepdomq + coalesce(edepforq, 0)) * 1000 as deposit_expense,
    depidom * 1000 as domestic_interest_bearing_deposits,
    depifor * 1000 as foreign_interest_bearing_deposits,
    edepdomq * 1000 as domestic_deposit_expense,
    edepforq * 1000 as foreign_deposit_expense
from {{ source('raw', 'fdic_financials') }}
