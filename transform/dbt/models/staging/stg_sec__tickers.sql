-- One row per listed security, unnested from the pipe-delimited registrant fields.
--
-- A filer carries several tickers where preferred shares are separately listed, and a few
-- carry none at all: a US intermediate holding company of a foreign bank files against
-- registered debt with no listed equity, and a terminal filer is delisted on exit while
-- its filings remain. Those filers are absent here rather than present with a null ticker.

with registrants as (

    select
        cik,
        registrant_name,
        tickers,
        exchanges
    from {{ source('raw', 'sec_registrants') }}
    where tickers <> ''

),

split as (

    select
        cik,
        registrant_name,
        string_split(tickers, '|') as ticker_list,
        string_split(exchanges, '|') as exchange_list
    from registrants

)

select
    cik,
    registrant_name,
    ticker,
    -- EDGAR publishes the two lists positionally; a shorter exchange list leaves the tail
    -- unmatched rather than misaligned against the wrong ticker.
    case
        when position <= len(exchange_list) then exchange_list[position]
    end as exchange,
    position as ticker_position
from split,
    unnest(ticker_list) with ordinality as t (ticker, position)
