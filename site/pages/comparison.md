---
title: Cross-bank comparison
sidebar_position: 3
---

```sql headline
select * from marketscope.mart_persistence_result where sample = 'headline'
```

```sql ranking
select
    registrant_name,
    calibration_beta,
    calibration_rank,
    calibration_quartile,
    test_beta,
    test_rank,
    test_quartile,
    quartile_shift,
    material_deviator,
    '/banks/' || cast(cast(cik as bigint) as varchar) as bank_link
from marketscope.mart_cross_bank_comparison
where in_headline
order by calibration_rank
```

```sql scatter
select
    registrant_name,
    calibration_beta,
    test_beta,
    case
        when in_headline then 'Headline sample'
        else 'Outside the headline'
    end as sample
from marketscope.mart_cross_bank_comparison
where calibration_beta is not null and test_beta is not null
union all
select
    bank || ' (Call Reports)',
    calibration_beta,
    test_beta,
    'Failed, not in EDGAR'
from marketscope.mart_recovered_beta
order by sample
```

```sql distribution
with betas as (
    select 'Calibration, 2015–2019' as cycle, calibration_beta as beta
    from marketscope.mart_cross_bank_comparison
    where in_headline
    union all
    select 'Test, 2022–2023', test_beta
    from marketscope.mart_cross_bank_comparison
    where in_headline
)
select
    cycle,
    min(beta) as low,
    quantile_cont(beta, 0.25) as lower_quartile,
    median(beta) as median_beta,
    quantile_cont(beta, 0.75) as upper_quartile,
    max(beta) as high
from betas
group by cycle
order by cycle
```

```sql transitions
with grid as (
    select calibration.q as calibration_quartile, test.q as test_quartile
    from range(1, 5) as calibration(q)
    cross join range(1, 5) as test(q)
)
select
    'Calibration Q' || grid.calibration_quartile as calibration,
    'Test Q' || grid.test_quartile as test,
    count(comparison.cik) as filers
from grid
left join marketscope.mart_cross_bank_comparison as comparison
    on comparison.in_headline
    and comparison.calibration_quartile = grid.calibration_quartile
    and comparison.test_quartile = grid.test_quartile
group by grid.calibration_quartile, grid.test_quartile
order by grid.calibration_quartile, grid.test_quartile
```

```sql same_quartile
select
    count(*) filter (where quartile_shift = 0) as filers,
    count(*) filter (where quartile_shift = 0) / count(*) as share
from marketscope.mart_cross_bank_comparison
where in_headline
```

```sql membership
select
    registrant_name,
    calibration_beta,
    calibration_tier,
    test_beta,
    test_tier,
    in_headline,
    in_r1,
    in_r2,
    in_r3,
    in_r4,
    '/banks/' || cast(cast(cik as bigint) as varchar) as bank_link
from marketscope.mart_cross_bank_comparison
order by in_headline desc, registrant_name
```

```sql variants
select sample, description, filers
from marketscope.mart_persistence_result
where sample like 'R%'
order by sample
```

```sql recovered
select bank, calibration_beta, test_beta, test_end
from marketscope.mart_recovered_beta
order by bank
```

Where each bank sits among its peers in each cycle. Ranks and quartiles are within the
<Value data={headline} column=filers />-filer headline sample, rank 1 the slowest
repricer, quartile 1 the slowest quarter.

## Cycle on cycle

Each bank's beta in one cycle against the next. Levels rise between the cycles, as they were
expected to in a faster and larger tightening, so the question is not whether a bank's beta
held but whether its place in the order did.

<ScatterPlot
    data={scatter}
    x=calibration_beta
    y=test_beta
    series=sample
    tooltipTitle=registrant_name
    xAxisTitle="Calibration beta"
    yAxisTitle="Test beta"
    xFmt='0.00'
    yFmt='0.00'
    chartAreaHeight=360
/>

First Republic and Signature never filed with the SEC. Their betas come from their own Call
Reports by the same arithmetic, and their test betas end at the last quarter each reported.

## Distributions

The headline sample's betas in each cycle: lowest, quartiles, median and highest.

<BoxPlot
    data={distribution}
    name=cycle
    min=low
    intervalBottom=lower_quartile
    midpoint=median_beta
    intervalTop=upper_quartile
    max=high
    yFmt='0.00'
/>

## Quartile transitions

<Value data={same_quartile} column=filers /> of the
<Value data={headline} column=filers /> filers sit in the same quartile in both cycles,
<Value data={same_quartile} column=share fmt=pct0 />, against a quarter by chance.

<Heatmap data={transitions} x=test y=calibration value=filers valueFmt=num0 />

## Rankings

<DataTable data={ranking} link=bank_link rows=all>
    <Column id=registrant_name title="Filer" />
    <Column id=calibration_beta title="Calibration beta" fmt='0.000' />
    <Column id=calibration_rank title="Rank" fmt=num1 />
    <Column id=calibration_quartile title="Quartile" />
    <Column id=test_beta title="Test beta" fmt='0.000' />
    <Column id=test_rank title="Rank" fmt=num1 />
    <Column id=test_quartile title="Quartile" />
    <Column id=quartile_shift title="Quartile shift" />
    <Column id=material_deviator title="Material deviator" />
</DataTable>

A material deviator is two or more quartiles apart between the cycles. The
[persistence case study](/persistence) states a hypothesis for each.

## Who enters which sample

The headline admits a ranked filer with a tier 1 beta in both cycles, tier 1 cost of
deposits in at least 80 percent of each cycle's quarters, no partial cycle, and no material
acquisition inside either cycle. Each robustness variant turns one of those rules:

<DataTable data={variants}>
    <Column id=sample title="Variant" />
    <Column id=description title="Change to the sample" />
    <Column id=filers title="Filers" />
</DataTable>

<DataTable data={membership} link=bank_link search=true rows=all>
    <Column id=registrant_name title="Filer" />
    <Column id=calibration_beta title="Calibration beta" fmt='0.000' />
    <Column id=calibration_tier title="Tier" />
    <Column id=test_beta title="Test beta" fmt='0.000' />
    <Column id=test_tier title="Tier" />
    <Column id=in_headline title="Headline" />
    <Column id=in_r1 title="R1" />
    <Column id=in_r2 title="R2" />
    <Column id=in_r3 title="R3" />
    <Column id=in_r4 title="R4" />
</DataTable>

Recovered from Call Reports into the survivorship comparison, and members of no sample
above:

<DataTable data={recovered}>
    <Column id=bank title="Bank" />
    <Column id=calibration_beta title="Calibration beta" fmt='0.000' />
    <Column id=test_beta title="Test beta" fmt='0.000' />
    <Column id=test_end title="Test measured to" fmt='yyyy-mm-dd' />
</DataTable>
