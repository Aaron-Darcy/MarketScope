-- The FFIEC archives and BankFind publish the same Call Reports, so a filer's quarter-end
-- interest-bearing deposits must agree to the thousand. A disagreement means the RSSD to
-- certificate mapping joined the wrong bank, or one source revised a report the other did
-- not.

select
    ffiec.cert,
    ffiec.quarter_end,
    ffiec.domestic_interest_bearing + coalesce(ffiec.foreign_interest_bearing, 0)
        as ffiec_interest_bearing,
    bankfind.interest_bearing_deposits as bankfind_interest_bearing
from {{ ref('stg_ffiec__deposit_balances') }} as ffiec
join (
    select distinct cert, quarter_end, interest_bearing_deposits
    from {{ ref('stg_fdic__financials') }}
) as bankfind
  on bankfind.cert = ffiec.cert
 and bankfind.quarter_end = ffiec.quarter_end
where abs(
    ffiec.domestic_interest_bearing + coalesce(ffiec.foreign_interest_bearing, 0)
    - bankfind.interest_bearing_deposits
) >= 1000
