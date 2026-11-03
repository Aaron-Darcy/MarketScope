-- display_name is the registrant name as a reader knows the bank: the SEC's state suffix and
-- corporate words removed, and capitals only where the bank uses them.
with stems as (

    select
        *,
        trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
            registrant_name,
            '\s*[/\x5c][A-Za-z]{2,3}[/\x5c]?\s*$', ''),
            ',.*$', ''),
            '\s+(INC|CORP|CORPORATION|CO|COMPANY|GROUP|HOLDINGS)\.?$', '', 'i'),
            '\s+(INC|CORP|CORPORATION|CO|COMPANY|GROUP|FINANCIAL|FINANCIAL SERVICES|BANCSHARES|BANCORPORATION)\.?$', '', 'i'),
            '\s*&$', '')) as stem
    from read_parquet('dim_bank.parquet')

)

select
    * exclude (stem),
    case
        when registrant_name = 'SCHWAB CHARLES CORP' then 'Charles Schwab'
        when registrant_name = 'E TRADE FINANCIAL CORP' then 'E*TRADE'
        when stem <> upper(stem) then stem
        else array_to_string(list_transform(string_split(lower(stem), ' '), lambda w:
            case upper(w)
                when 'JPMORGAN' then 'JPMorgan'
                when 'PACWEST' then 'PacWest'
                when 'SUNTRUST' then 'SunTrust'
                when 'KEYCORP' then 'KeyCorp'
                when 'CULLEN/FROST' then 'Cullen/Frost'
                when 'M&T' then 'M&T'
                when 'US' then 'U.S.'
                else case
                    when upper(w) in ('PNC', 'BOK', 'CIT', 'SVB', 'HSBC', 'USA', 'BBVA', 'MUFG') then upper(w)
                    when w in ('of', '&') then w
                    else upper(w[1]) || w[2:]
                end
            end), ' ')
    end as display_name
from stems
