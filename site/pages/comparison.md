---
title: Cross-bank comparison
sidebar_position: 3
---

<script>
    import { BLUE, ORANGE, AQUA, GREY, INK, MUTED, GRID } from '../../components/palette.js';

    const placement = (shift) =>
        Math.abs(shift) >= 2 ? 'moved' : shift === 0 ? 'held' : 'shifted';
    const colour = { held: BLUE, shifted: GREY, moved: ORANGE };

    $: banks = [...ranking];
    $: slopeConfig = {
        grid: { left: 170, right: 170, top: 36, bottom: 24 },
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const b = banks[p.seriesIndex];
                return `<b>${b.display_name}</b><br/>2015–19: rank ${b.calibration_rank} of ${banks.length}, beta ${b.calibration_beta.toFixed(3)}<br/>2022–23: rank ${b.test_rank} of ${banks.length}, beta ${b.test_beta.toFixed(3)}`;
            }
        },
        xAxis: {
            type: 'category',
            data: ['2015–2019 cycle', '2022–2023 cycle'],
            boundaryGap: false,
            position: 'top',
            axisLabel: { color: INK, fontSize: 13, fontWeight: 600 },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        yAxis: { type: 'value', min: 0.5, max: banks.length + 0.5, show: false },
        series: banks.map((b) => {
            const kind = placement(b.quartile_shift);
            return {
                type: 'line',
                data: [b.calibration_rank, b.test_rank],
                symbol: 'circle',
                symbolSize: 8,
                lineStyle: { color: colour[kind], width: kind === 'shifted' ? 1.5 : 2.5 },
                itemStyle: { color: colour[kind], borderColor: '#fff', borderWidth: 1.5 },
                z: kind === 'shifted' ? 1 : 2,
                label: {
                    show: true,
                    position: 'left',
                    formatter: (p) => (p.dataIndex === 0 ? b.display_name : ''),
                    color: kind === 'shifted' ? MUTED : INK,
                    fontSize: 11
                },
                endLabel: {
                    show: true,
                    formatter: b.display_name,
                    color: kind === 'shifted' ? MUTED : INK,
                    fontSize: 11
                }
            };
        })
    };

    $: pairs = [...dumbbell];
    $: dumbbellConfig = {
        grid: { left: 200, right: 32, top: 40, bottom: 40 },
        legend: {
            top: 0,
            icon: 'circle',
            textStyle: { color: MUTED },
            data: ['2015–2019 beta', '2022–2023 beta']
        },
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const b = pairs[p.dataIndex];
                return `<b>${b.display_name}</b>${b.note ? '<br/>' + b.note : ''}<br/>2015–19 beta ${b.calibration_beta.toFixed(3)}<br/>2022–23 beta ${b.test_beta.toFixed(3)}`;
            }
        },
        xAxis: {
            min: 0,
            max: 1,
            name: 'Deposit beta: the share of the policy rate rise passed on to depositors',
            nameLocation: 'middle',
            nameGap: 26,
            nameTextStyle: { color: MUTED },
            axisLabel: { color: MUTED },
            splitLine: { lineStyle: { color: GRID } }
        },
        yAxis: {
            type: 'category',
            data: pairs.map((b) => b.display_name),
            inverse: true,
            axisTick: { show: false },
            axisLine: { show: false },
            axisLabel: {
                formatter: (value, i) =>
                    pairs[i].in_headline ? `{in|${value}}` : `{out|${value}}`,
                rich: {
                    in: { color: INK, fontSize: 11 },
                    out: { color: MUTED, fontSize: 11, fontStyle: 'italic' }
                }
            }
        },
        series: [
            {
                type: 'custom',
                silent: true,
                renderItem: (params, api) => {
                    const from = api.coord([api.value(0), api.value(2)]);
                    const to = api.coord([api.value(1), api.value(2)]);
                    return {
                        type: 'line',
                        shape: { x1: from[0], y1: from[1], x2: to[0], y2: to[1] },
                        style: { stroke: GREY, lineWidth: 2 }
                    };
                },
                encode: { x: [0, 1], y: 2 },
                data: pairs.map((b, i) => [b.calibration_beta, b.test_beta, i]),
                z: 1
            },
            {
                name: '2015–2019 beta',
                type: 'scatter',
                symbolSize: 10,
                itemStyle: { color: BLUE, borderColor: '#fff', borderWidth: 1.5 },
                data: pairs.map((b, i) => [b.calibration_beta, i]),
                z: 2
            },
            {
                name: '2022–2023 beta',
                type: 'scatter',
                symbolSize: 10,
                itemStyle: { color: ORANGE, borderColor: '#fff', borderWidth: 1.5 },
                data: pairs.map((b, i) => [b.test_beta, i]),
                z: 2
            }
        ]
    };
</script>

```sql ranking
select
    banks.display_name,
    comparison.calibration_beta,
    comparison.test_beta,
    comparison.calibration_rank,
    comparison.test_rank,
    comparison.quartile_shift
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
where comparison.in_headline
order by comparison.calibration_rank
```

```sql dumbbell
select
    banks.display_name,
    comparison.calibration_beta,
    comparison.test_beta,
    comparison.in_headline,
    case when not comparison.in_headline then 'Outside the headline sample' end as note
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
where comparison.calibration_beta is not null and comparison.test_beta is not null
union all
select
    bank || ' (failed)',
    calibration_beta,
    test_beta,
    false,
    'Failed; never filed with the SEC. Betas from its Call Reports, test cycle to '
        || strftime(test_end, '%Y-%m-%d')
from marketscope.mart_recovered_beta
order by test_beta desc
```

```sql transitions
with grid as (
    select calibration.q as calibration_quartile, test.q as test_quartile
    from range(1, 5) as calibration(q)
    cross join range(1, 5) as test(q)
)
select
    case grid.calibration_quartile
        when 1 then '2015–19: slowest quarter'
        when 4 then '2015–19: fastest quarter'
        else '2015–19: Q' || cast(grid.calibration_quartile as integer)
    end as calibration,
    case grid.test_quartile
        when 1 then '2022–23: slowest'
        when 4 then '2022–23: fastest'
        else '2022–23: Q' || cast(grid.test_quartile as integer)
    end as test,
    grid.calibration_quartile,
    grid.test_quartile,
    count(comparison.cik) as banks
from grid
left join marketscope.mart_cross_bank_comparison as comparison
    on comparison.in_headline
    and comparison.calibration_quartile = grid.calibration_quartile
    and comparison.test_quartile = grid.test_quartile
group by all
order by grid.calibration_quartile desc, grid.test_quartile
```

```sql summary
select
    count(*) as banks,
    count(*) filter (where quartile_shift = 0) as held,
    count(*) filter (where abs(quartile_shift) >= 2) as moved
from marketscope.mart_cross_bank_comparison
where in_headline
```

```sql membership
select
    banks.display_name,
    printf('%.3f', comparison.calibration_beta) as calibration_beta,
    comparison.calibration_tier,
    printf('%.3f', comparison.test_beta) as test_beta,
    comparison.test_tier,
    case when comparison.in_headline then '●' else '' end as headline,
    case when comparison.in_r1 then '●' else '' end as r1,
    case when comparison.in_r2 then '●' else '' end as r2,
    case when comparison.in_r3 then '●' else '' end as r3,
    case when comparison.in_r4 then '●' else '' end as r4,
    '/banks/' || cast(cast(comparison.cik as bigint) as varchar) as bank_link
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
order by comparison.in_headline desc, banks.display_name
```

```sql variants
select sample as variant, description as change_to_the_sample, filers as banks
from marketscope.mart_persistence_result
where sample like 'R%'
order by sample
```

Where each bank sits among its peers, cycle by cycle. Of the {summary[0].banks} banks in the
headline sample, **{summary[0].held} kept exactly the same quartile** and only
**{summary[0].moved} moved two quartiles or more**.

## Who kept their place

Each line is one bank, ranked from the slowest repricer at the bottom to the fastest at the
top. A flat line kept its rank. Blue banks stayed in the same quartile, orange ones moved
two quartiles or more, grey ones moved one.

<ECharts config={slopeConfig} height="640px" />

## Every bank, both cycles

Each bank's beta in the calibration cycle (blue) and the test cycle (orange). Every bank
moved right, because the second cycle was faster and larger; what persists is the order.
Italic names are outside the headline sample: most for a material acquisition inside a
cycle, the rest for a tier 2 or 3 beta or a cycle cut short, and two are failed banks
recovered from their Call Reports.

<ECharts config={dumbbellConfig} height="860px" />

## Quartile transitions

Read along a row: where the banks of one 2015–2019 quartile ended up in 2022–2023. The
diagonal is a bank that kept its quartile; by chance alone a quarter would.

<Heatmap
    data={transitions}
    x=test
    y=calibration
    value=banks
    xSort=test_quartile
    ySort=calibration_quartile
    ySortOrder=desc
    valueFmt=num0
    colorScale={['#eef4fc', '#104281']}
    cellHeight=52
/>

## Who enters which sample

The headline admits a ranked bank with a tier 1 beta in both cycles, tier 1 cost of
deposits in at least 80 percent of each cycle's quarters, no partial cycle and no material
acquisition inside either cycle. Each robustness variant turns one of those rules.

<DataTable data={variants}>
    <Column id=variant title="Variant" />
    <Column id=change_to_the_sample title="Change to the sample" />
    <Column id=banks title="Banks" />
</DataTable>

<DataTable data={membership} link=bank_link search=true rows=15>
    <Column id=display_name title="Bank" />
    <Column id=calibration_beta title="2015–19 beta" align=right />
    <Column id=calibration_tier title="Tier" align=center />
    <Column id=test_beta title="2022–23 beta" align=right />
    <Column id=test_tier title="Tier" align=center />
    <Column id=headline title="Headline" align=center />
    <Column id=r1 title="R1" align=center />
    <Column id=r2 title="R2" align=center />
    <Column id=r3 title="R3" align=center />
    <Column id=r4 title="R4" align=center />
</DataTable>
