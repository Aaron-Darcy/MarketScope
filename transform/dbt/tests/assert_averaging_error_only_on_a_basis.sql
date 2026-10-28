-- An error without a basis would be measured on a base known to differ from the reported
-- average by definition; a basis without an error would hide a quarter that was dropped.

select group_key, quarter_end, basis, averaging_error
from {{ ref('int_regulatory_average_balances') }}
where (basis is null) <> (averaging_error is null)
