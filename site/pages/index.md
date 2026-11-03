---
title: Do banks reprice deposits the same way twice?
sidebar_position: 1
---

<script>
    import { BLUE, ORANGE, AQUA, GREY, INK, MUTED, GRID } from '../components/palette.js';

    $: points = [...headline_banks];
    $: kept = points.filter((p) => !p.material_deviator);
    $: moved = points.filter((p) => p.material_deviator);
    $: scatterConfig = {
        grid: { left: 56, right: 24, top: 24, bottom: 64 },
        tooltip: {
            trigger: 'item',
            formatter: (p) =>
                p.seriesName === 'Equal betas'
                    ? ''
                    : `<b>${p.data[2]}</b><br/>2015–19 beta ${p.data[0].toFixed(3)}<br/>2022–23 beta ${p.data[1].toFixed(3)}`
        },
        legend: {
            bottom: 0,
            textStyle: { color: MUTED },
            icon: 'circle',
            data: ['Kept its place, within a quartile', 'Moved two quartiles or more']
        },
        labelLayout: { moveOverlap: 'shiftY' },
        xAxis: {
            name: 'Deposit beta, 2015–2019',
            nameLocation: 'middle',
            nameGap: 30,
            nameTextStyle: { color: MUTED, fontSize: 12 },
            min: 0.1,
            max: 0.9,
            axisLabel: { color: MUTED },
            axisLine: { lineStyle: { color: GRID } },
            splitLine: { lineStyle: { color: GRID } }
        },
        yAxis: {
            name: 'Deposit beta, 2022–2023',
            nameLocation: 'middle',
            nameGap: 40,
            nameTextStyle: { color: MUTED, fontSize: 12 },
            min: 0.1,
            max: 0.9,
            axisLabel: { color: MUTED },
            splitLine: { lineStyle: { color: GRID } }
        },
        series: [
            {
                name: 'Equal betas',
                type: 'line',
                data: [[0.1, 0.1], [0.9, 0.9]],
                symbol: 'none',
                silent: true,
                lineStyle: { color: GREY, width: 1 },
                z: 1
            },
            {
                name: 'Kept its place, within a quartile',
                type: 'scatter',
                symbolSize: 12,
                data: kept.map((p) => [p.calibration_beta, p.test_beta, p.display_name]),
                itemStyle: { color: BLUE, borderColor: '#fff', borderWidth: 2 }
            },
            {
                name: 'Moved two quartiles or more',
                type: 'scatter',
                symbolSize: 12,
                data: moved.map((p) => [p.calibration_beta, p.test_beta, p.display_name]),
                itemStyle: { color: ORANGE, borderColor: '#fff', borderWidth: 2 },
                label: {
                    show: true,
                    formatter: (p) => p.data[2],
                    position: 'right',
                    distance: 8,
                    color: INK,
                    fontSize: 12,
                    fontWeight: 600
                }
            }
        ]
    };

    $: forest = [...samples];
    $: forestConfig = {
        grid: { left: 250, right: 32, top: 12, bottom: 40 },
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const s = forest[p.dataIndex];
                return `<b>${s.sample_label}</b><br/>${s.filers} filers<br/>Spearman ${s.spearman_text}<br/>95% interval ${s.interval_text}<br/>p ${s.p_text}`;
            }
        },
        xAxis: {
            min: -0.2,
            max: 1,
            name: 'Rank correlation and 95% interval; zero is no relationship',
            nameLocation: 'middle',
            nameGap: 26,
            nameTextStyle: { color: MUTED, fontSize: 12 },
            axisLabel: { color: MUTED },
            splitLine: { lineStyle: { color: GRID } }
        },
        yAxis: {
            type: 'category',
            inverse: true,
            data: forest.map((s) => `${s.sample_label}  (${s.filers})`),
            axisLabel: { color: INK, fontSize: 12 },
            axisTick: { show: false },
            axisLine: { show: false }
        },
        series: [
            {
                type: 'custom',
                renderItem: (params, api) => {
                    const low = api.coord([api.value(0), api.value(2)]);
                    const high = api.coord([api.value(1), api.value(2)]);
                    return {
                        type: 'line',
                        shape: { x1: low[0], y1: low[1], x2: high[0], y2: high[1] },
                        style: { stroke: params.dataIndex === 0 ? BLUE : GREY, lineWidth: 3, lineCap: 'round' }
                    };
                },
                encode: { x: [0, 1], y: 2 },
                data: forest.map((s, i) => [s.interval_low, s.interval_high, i]),
                silent: true,
                z: 1
            },
            {
                type: 'scatter',
                symbolSize: 13,
                data: forest.map((s, i) => ({
                    value: [s.spearman, i],
                    itemStyle: { color: i === 0 ? BLUE : AQUA, borderColor: '#fff', borderWidth: 2 }
                })),
                label: {
                    show: true,
                    position: 'top',
                    formatter: (p) => forest[p.dataIndex].spearman_text,
                    color: INK,
                    fontSize: 11
                },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    lineStyle: { color: MUTED, type: 'solid', width: 1 },
                    label: { show: false },
                    data: [{ xAxis: 0 }]
                },
                z: 2
            }
        ]
    };
</script>

```sql headline
select
    filers,
    printf('%+.2f', spearman) as spearman_text,
    printf('%.3f', p_value) as p_text,
    printf('%+.2f to %+.2f', interval_low, interval_high) as interval_text,
    supported
from marketscope.mart_persistence_result
where sample = 'headline'
```

```sql samples
select
    case sample
        when 'headline' then 'Headline: survivors only'
        when 'R1' then 'R1: tiers 1 and 2'
        when 'R2' then 'R2: acquirers inside a cycle'
        when 'R3' then 'R3: acquirers between cycles out'
        when 'R4' then 'R4: SVB added'
        when 'R4+recovered' then 'R4 + First Republic, Signature'
    end as sample_label,
    filers,
    spearman,
    interval_low,
    interval_high,
    printf('%+.3f', spearman) as spearman_text,
    printf('%+.3f to %+.3f', interval_low, interval_high) as interval_text,
    printf('%.4f', p_value) as p_text
from marketscope.mart_persistence_result
order by case sample when 'headline' then 0 when 'R4+recovered' then 6 else 1 end, sample
```

```sql headline_banks
select
    banks.display_name,
    comparison.calibration_beta,
    comparison.test_beta,
    comparison.material_deviator
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
where comparison.in_headline
```

```sql fastest
with sample as (
    select count(*) as filers from marketscope.mart_cross_bank_comparison where in_headline
)
select
    count(*) filter (where calibration_rank > filers - 6 and test_rank > filers - 6)
        as stayed_fastest,
    count(*) filter (where quartile_shift = 0) as same_quartile
from marketscope.mart_cross_bank_comparison, sample
where in_headline
```

```sql validation
select
    printf('%.1f', median(abs(cost_of_deposits - regulatory_cost_of_deposits)) * 10000)
        as median_gap_text,
    printf('%.0f%%', 100 * avg(case when abs(cost_of_deposits - regulatory_cost_of_deposits) <= 0.001 then 1 else 0 end))
        as within_text,
    format('{:,}', count(*)) as pairs_text
from marketscope.fct_bank_quarter
where metric_tier = '1'
  and cost_of_deposits is not null
  and regulatory_cost_of_deposits is not null
```

```sql coverage
select
    format('{:,}', count(cost_of_deposits)) as quarters_text,
    count(distinct cik) as members
from marketscope.fct_bank_quarter
```

```sql policy
select distinct quarter_end, policy_rate_fraction as rate
from marketscope.fct_bank_quarter
where policy_rate_fraction is not null
order by quarter_end
```

```sql cycles
select
    case cycle_name when 'calibration' then 'Calibration cycle' else 'Test cycle' end as label,
    start_quarter,
    end_quarter
from marketscope.dim_rate_cycle
where cycle_name is not null
```

When the Federal Reserve raises rates, each bank decides how much of the rise to pass on to
its depositors. That share is its **deposit beta**. MarketScope measures it for the largest
US deposit-taking banks, straight from their SEC filings, across two tightening cycles, and
asks whether the banks that moved fastest the first time moved fastest again.

<div style="background: linear-gradient(135deg, #0d366b 0%, #1c5cab 60%, #2a78d6 100%); color: #fff; border-radius: 14px; padding: 32px 36px; margin: 28px 0 8px; display: flex; flex-wrap: wrap; gap: 32px; align-items: center;">
  <div style="flex: 1 1 280px;">
    <div style="font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.8;">Headline result</div>
    <div style="font-size: 72px; font-weight: 700; line-height: 1.05; margin: 6px 0;">{headline[0].spearman_text}</div>
    <div style="font-size: 15px; opacity: 0.9; max-width: 340px;">rank correlation between each bank's deposit beta in 2015–2019 and in 2022–2023, across {headline[0].filers} banks</div>
  </div>
  <div style="flex: 2 1 460px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px;">
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 14px 16px;">
      <div style="font-size: 30px; font-weight: 700;">{fastest[0].stayed_fastest} of 6</div>
      <div style="font-size: 13px; opacity: 0.85;">fastest repricers stayed among the six fastest</div>
    </div>
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 14px 16px;">
      <div style="font-size: 30px; font-weight: 700;">p {headline[0].p_text}</div>
      <div style="font-size: 13px; opacity: 0.85;">on a test fixed before the result was computed</div>
    </div>
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 14px 16px;">
      <div style="font-size: 30px; font-weight: 700;">{validation[0].median_gap_text} bp</div>
      <div style="font-size: 13px; opacity: 0.85;">median gap to the banks' own Call Reports</div>
    </div>
  </div>
</div>

## Fast repricers stayed fast

{#if headline[0].supported}

**Yes, mostly.** Across {headline[0].filers} banks, the ordering by deposit beta in 2015–2019
carries into 2022–2023 with a rank correlation of {headline[0].spearman_text}, which clears
the test fixed before the result was computed. {fastest[0].stayed_fastest} of the six fastest
repricers stayed among the six fastest, and {fastest[0].same_quartile} banks sat in the same
quartile both times, twice what chance would give.

{:else}

**Not shown.** Across {headline[0].filers} banks the rank correlation is
{headline[0].spearman_text}, which does not clear the test fixed before the result was
computed. At this sample size that is not evidence of its absence.

{/if}

<ECharts config={scatterConfig} height="460px" />

Every bank sits above the diagonal because the second cycle was faster and larger, so all
betas rose. The claim is about order, not level: banks to the right sit higher. The three
labelled banks moved two quartiles or more; the
[case study](/persistence) gives a hypothesis for each.

## The result survives every check

Four variants of the sample were registered beside the headline before anything was
computed. Each gives the same answer, and adding the failed banks that an EDGAR-only study
leaves out — Silicon Valley Bank, and First Republic and Signature from their Call
Reports — makes it stronger, not weaker.

<ECharts config={forestConfig} height="300px" />

## Two very different cycles

The first tightening took three years to move rates about two points. The second moved them
more than five in under two. Betas rise in a cycle like that, which is why levels are not
compared across them and the ordering is.

<LineChart
    data={policy}
    x=quarter_end
    y=rate
    yFmt=pct1
    yAxisTitle="Federal funds, quarterly average"
    colorPalette={['#2a78d6']}
    chartAreaHeight=220
>
    <ReferenceArea data={cycles} xMin=start_quarter xMax=end_quarter label=label color=#eb6834 />
</LineChart>

## What is and is not claimed

<Grid cols=2>
<div>

**Claimed**

- Across these banks, a bank's place in the deposit beta ordering in one cycle is
  associated with its place in the next, on a test fixed in advance.
- The figures behind it match the banks' own Call Reports: a median gap of
  {validation[0].median_gap_text} basis points, and {validation[0].within_text} of
  {validation[0].pairs_text} bank-quarters within 10.

</div>
<div>

**Not claimed**

- A forecast for any one bank. The interval runs {headline[0].interval_text}.
- Anything about failure or distress.
- That beta levels carry over between cycles, or that deposit betas are a new idea.

</div>
</Grid>

## Explore

{coverage[0].quarters_text} bank-quarters across {coverage[0].members} filers, built from
SEC EDGAR XBRL and FRED, checked against FDIC and FFIEC Call Reports.

- [Bank explorer](/banks): every bank's cost of deposits against the Fed, cycle by cycle
- [Cross-bank comparison](/comparison): who moved, who held, and by how much
- [Deposit beta persistence](/persistence): the full case study
- [Methodology](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md):
  how every figure is produced, and what is not yet handled
