-- A cost read for one office alone is only meaningful if the offices partition the total.
-- The FDIC publishes in whole thousands, so a dollar of difference is already a mismatch.
-- A foreign balance without a foreign expense, or the reverse, would make a foreign cost
-- out of half a Call Report.

select cert, quarter_end, interest_bearing_deposits, domestic_interest_bearing_deposits,
    foreign_interest_bearing_deposits, foreign_deposit_expense
from {{ ref('stg_fdic__financials') }}
where abs(
        interest_bearing_deposits
        - domestic_interest_bearing_deposits
        - coalesce(foreign_interest_bearing_deposits, 0)
    ) >= 1000
    or (foreign_interest_bearing_deposits is null) <> (foreign_deposit_expense is null)
