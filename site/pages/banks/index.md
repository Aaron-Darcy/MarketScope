---
title: Bank explorer
sidebar_position: 2
---

<script>
    import { TIERS, INK, MUTED, GRID } from '../../components/palette.js';

    $: rows = [...coverage];
    $: names = [...new Set(rows.map((r) => r.display_name))];
    $: coverageConfig = {
        grid: { left: 170, right: 24, top: 36, bottom: 36 },
        legend: { top: 0, icon: 'roundRect', textStyle: { color: MUTED } },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: {
            name: 'Quarters',
            nameLocation: 'middle',
            nameGap: 24,
            nameTextStyle: { color: MUTED },
            axisLabel: { color: MUTED },
            splitLine: { lineStyle: { color: GRID } }
        },
        yAxis: {
            type: 'category',
            data: names,
            inverse: true,
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: { color: INK, fontSize: 11 }
        },
        series: Object.entries(TIERS).map(([tier, color]) => ({
            name: tier,
            type: 'bar',
            stack: 'quarters',
            barWidth: 11,
            itemStyle: { color, borderColor: '#fff', borderWidth: 1 },
            data: names.map(
                (name) => rows.find((r) => r.display_name === name && r.tier === tier)?.quarters ?? 0
            )
        }))
    };
</script>

```sql members
select
    banks.display_name,
    overview.rank,
    case overview.exit_type
        when 'exit_merger' then 'Merged ' || strftime(overview.exit_date, '%Y')
        when 'failure' then 'Failed ' || strftime(overview.exit_date, '%Y')
        when 'exit_deregistration' then 'Deregistered ' || strftime(overview.exit_date, '%Y')
        else 'Filing'
    end as status,
    overview.cost_quarters,
    overview.tier_1_share,
    overview.calibration_beta,
    overview.test_beta,
    overview.median_regulatory_gap_bp,
    '/banks/' || cast(cast(overview.cik as bigint) as varchar) as bank_link
from marketscope.mart_bank_overview as overview
join marketscope.dim_bank as banks using (cik)
order by overview.rank nulls last, banks.display_name
```

```sql coverage
select
    banks.display_name,
    coalesce(overview.rank, 99) as rank,
    case facts.metric_tier
        when '1' then 'Tier 1'
        when '2' then 'Tier 2'
        when '3' then 'Tier 3'
        when 'X' then 'Tier X'
        else 'Balance only'
    end as tier,
    count(*) as quarters
from marketscope.fct_bank_quarter as facts
join marketscope.dim_bank as banks using (cik)
join marketscope.mart_bank_overview as overview using (cik)
group by all
order by rank, banks.display_name
```

```sql totals
select
    count(distinct cik) as banks,
    format('{:,}', count(cost_of_deposits)) as quarters_text,
    printf('%.0f%%', 100.0 * count(*) filter (where metric_tier = '1') / count(cost_of_deposits))
        as tier_1_text,
    count(distinct cik) filter (
        where cik in (select cik from marketscope.dim_bank where exit_type is not null)
    ) as exited
from marketscope.fct_bank_quarter
```

The largest fifty US deposit-taking banks by the highest total assets each reported across
2015–2023, and one terminal filer pinned beside them. **{totals[0].exited} of the
{totals[0].banks} have since merged, deregistered or failed, and every one is kept.** Select a
bank in the table for its full series.

## How much of each bank's history resolves

Every bank-quarter carries a comparability tier, from tier 1, the most precise, to tier X,
a reconstruction that failed its completeness check. {totals[0].quarters_text}
bank-quarters resolve a cost of deposits, {totals[0].tier_1_text} of them at tier 1.

<ECharts config={coverageConfig} height="980px" />

## Every bank

<DataTable data={members} link=bank_link search=true rows=all>
    <Column id=rank title="Rank" align=center />
    <Column id=display_name title="Bank" />
    <Column id=status title="Status" />
    <Column id=cost_quarters title="Quarters" align=right />
    <Column id=tier_1_share title="At tier 1" fmt=pct0 contentType=bar barColor=#86b6ef />
    <Column id=calibration_beta title="2015–19 beta" fmt='0.000' />
    <Column id=test_beta title="2022–23 beta" fmt='0.000' />
    <Column id=median_regulatory_gap_bp title="Gap (bp)" fmt='0.0' />
</DataTable>

Rank is by peak total assets; the pinned bank has none. A beta is blank where an endpoint of
the cycle is unresolved, and the gap, the median distance in basis points from its own Call Reports, is blank where the bank has no tier 1
quarter or no regulatory group to compare against.
