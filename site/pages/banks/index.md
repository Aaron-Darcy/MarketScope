---
title: Bank explorer
sidebar_position: 2
---

```sql members
select
    cik,
    registrant_name,
    rank,
    case exit_type
        when 'exit_merger' then 'Merged ' || strftime(exit_date, '%Y-%m-%d')
        when 'failure' then 'Failed ' || strftime(exit_date, '%Y-%m-%d')
        when 'exit_deregistration' then 'Deregistered ' || strftime(exit_date, '%Y-%m-%d')
        else 'Filing'
    end as status,
    cost_quarters,
    tier_1_share,
    calibration_beta,
    calibration_tier,
    test_beta,
    test_tier,
    median_regulatory_gap_bp,
    '/banks/' || cast(cast(cik as bigint) as varchar) as bank_link
from marketscope.mart_bank_overview
order by rank nulls last, registrant_name
```

Every member of the universe: the largest fifty US deposit-taking filers by the highest
total assets each reported across 2015Q4–2023Q4, and one terminal filer pinned beside them.
Filers that merged, deregistered or failed are kept. Select a bank for its series.

<DataTable data={members} link=bank_link search=true rows=all>
    <Column id=rank title="Rank" />
    <Column id=registrant_name title="Filer" />
    <Column id=status title="Status" />
    <Column id=cost_quarters title="Quarters resolved" />
    <Column id=tier_1_share title="At tier 1" fmt=pct0 />
    <Column id=calibration_beta title="Calibration beta" fmt='0.000' />
    <Column id=calibration_tier title="Tier" />
    <Column id=test_beta title="Test beta" fmt='0.000' />
    <Column id=test_tier title="Tier" />
    <Column id=median_regulatory_gap_bp title="Median gap to Call Reports, bp" fmt='0.0' />
</DataTable>

Rank is by peak total assets; the pinned filer has none. A beta is blank where an endpoint
of the cycle is unresolved, and the gap to Call Reports is blank where the filer has no
tier 1 quarter or no regulatory group to compare against.

