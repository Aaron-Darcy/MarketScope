-- Call Report quarterly average deposits and the quarter-end balances on the same
-- definitions, per filer and quarter, in dollars.
--
-- Schedule RC-K averages interest-bearing transaction accounts but every nontransaction
-- account, interest-bearing or not. A bank that reclassifies demand balances into savings
-- for reserve purposes can report them differently on RC-K and RC-E, so neither RC-K total
-- is the interest-bearing base at every filer. Both bases are carried here and the choice
-- is made per group downstream (decision 0039).
--
-- Average time deposits were split at $100,000 until 2016Q4 and at $250,000 after. A
-- quarter carries one pair, and either pair sums to the same quantity. Foreign-office items
-- are blank for a filer of the domestic-only forms, which has no foreign offices, and stay
-- null here, as in stg_fdic__financials.

with items as (

    select cert, report_date, item, value * 1000 as value
    from {{ source('raw', 'ffiec_call_items') }}

)

select
    cert,
    report_date as quarter_end,
    max(value) filter (where item = 'RCON3485') as average_interest_bearing_transaction,
    max(value) filter (where item = 'RCONB563') as average_savings,
    sum(value) filter (
        where item in ('RCONA514', 'RCONA529', 'RCONHK16', 'RCONHK17')
    ) as average_time,
    max(value) filter (where item = 'RCFN3404') as average_foreign_interest_bearing,
    max(value) filter (where item = 'RCON2385') as nontransaction,
    max(value) filter (where item = 'RCON6636') as domestic_interest_bearing,
    max(value) filter (where item = 'RCFN6636') as foreign_interest_bearing
from items
group by cert, report_date
