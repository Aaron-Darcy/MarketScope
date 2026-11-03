---
title: Deposit beta persistence
sidebar_position: 4
---

<script>
    import { BLUE, ORANGE, AQUA, GREY, INK, MUTED, GRID } from '../../components/palette.js';

    const axis = (name, extra = {}) => ({
        name,
        nameLocation: 'middle',
        nameGap: 34,
        nameTextStyle: { color: MUTED, fontSize: 12 },
        axisLabel: { color: MUTED },
        splitLine: { lineStyle: { color: GRID } },
        ...extra
    });
    const diagonal = (low, high) => ({
        type: 'line',
        data: [[low, low], [high, high]],
        symbol: 'none',
        silent: true,
        lineStyle: { color: GREY, width: 1 },
        z: 1
    });

    $: ranked = [...ranks];
    $: n = ranked.length;
    $: rankConfig = {
        grid: { left: 56, right: 24, top: 16, bottom: 72 },
        tooltip: {
            trigger: 'item',
            formatter: (p) =>
                p.data && p.data[2]
                    ? `<b>${p.data[2]}</b><br/>rank ${p.data[0]} in 2015–19, ${p.data[1]} in 2022–23`
                    : ''
        },
        legend: {
            bottom: 0,
            icon: 'circle',
            textStyle: { color: MUTED },
            data: ['Same quartile', 'One quartile apart', 'Two or more apart']
        },
        xAxis: axis('Rank in 2015–2019, 1 the slowest', { min: 0, max: n + 1 }),
        yAxis: axis('Rank in 2022–2023', { min: 0, max: n + 1, nameGap: 30 }),
        series: [
            diagonal(0, n + 1),
            ...[
                ['Same quartile', 0, BLUE],
                ['One quartile apart', 1, GREY],
                ['Two or more apart', 2, ORANGE]
            ].map(([name, shift, color]) => ({
                name,
                type: 'scatter',
                symbolSize: 12,
                itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
                data: ranked
                    .filter((r) => Math.min(Math.abs(r.quartile_shift), 2) === shift)
                    .map((r) => [r.calibration_rank, r.test_rank, r.display_name]),
                label: {
                    show: shift === 2,
                    formatter: (p) => p.data[2],
                    position: 'right',
                    color: INK,
                    fontSize: 12,
                    fontWeight: 600
                }
            }))
        ]
    };

    $: forest = [...samples];
    $: forestConfig = {
        grid: { left: 250, right: 32, top: 12, bottom: 44 },
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const s = forest[p.dataIndex];
                return `<b>${s.sample_label}</b><br/>${s.description}<br/>${s.filers} banks · Spearman ${s.spearman_text}<br/>95% interval ${s.interval_text} · p ${s.p_text}`;
            }
        },
        xAxis: axis('Rank correlation and 95% interval; zero is no relationship', {
            min: -0.2,
            max: 1,
            nameGap: 26
        }),
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
                silent: true,
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
                    label: { show: false },
                    lineStyle: { color: MUTED, type: 'solid', width: 1 },
                    data: [{ xAxis: 0 }]
                },
                z: 2
            }
        ]
    };

    $: survivors = [...survivorship];
    $: survivorConfig = {
        grid: { left: 56, right: 24, top: 16, bottom: 72 },
        tooltip: {
            trigger: 'item',
            formatter: (p) =>
                p.data && p.data[2]
                    ? `<b>${p.data[2]}</b><br/>2015–19 beta ${p.data[0].toFixed(3)}<br/>2022–23 beta ${p.data[1].toFixed(3)}${p.data[3] ? '<br/>' + p.data[3] : ''}`
                    : ''
        },
        legend: {
            bottom: 0,
            icon: 'circle',
            textStyle: { color: MUTED },
            data: ['Kept filing', 'Failed']
        },
        xAxis: axis('Deposit beta, 2015–2019', { min: 0.1, max: 0.9 }),
        yAxis: axis('Deposit beta, 2022–2023', { min: 0.1, max: 0.9, nameGap: 40 }),
        series: [
            diagonal(0.1, 0.9),
            {
                name: 'Kept filing',
                type: 'scatter',
                symbolSize: 11,
                itemStyle: { color: BLUE, opacity: 0.75, borderColor: '#fff', borderWidth: 1.5 },
                data: survivors.filter((s) => !s.failed).map((s) => [s.calibration_beta, s.test_beta, s.display_name, s.note])
            },
            {
                name: 'Failed',
                type: 'scatter',
                symbolSize: 15,
                itemStyle: { color: ORANGE, borderColor: '#fff', borderWidth: 2 },
                data: survivors.filter((s) => s.failed).map((s) => [s.calibration_beta, s.test_beta, s.display_name, s.note]),
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

    $: checks = [...validation_points];
    $: validationConfig = {
        grid: { left: 64, right: 24, top: 16, bottom: 56 },
        tooltip: {
            trigger: 'item',
            formatter: (p) =>
                p.data && p.data[2]
                    ? `<b>${p.data[2]}</b> ${p.data[3]}<br/>XBRL ${(p.data[0] * 100).toFixed(2)}%<br/>Call Reports ${(p.data[1] * 100).toFixed(2)}%`
                    : ''
        },
        xAxis: axis('Cost of deposits from SEC XBRL filings', {
            min: 0,
            max: 0.05,
            axisLabel: { color: MUTED, formatter: (v) => `${(v * 100).toFixed(0)}%` }
        }),
        yAxis: axis('Cost of deposits from Call Reports', {
            min: 0,
            max: 0.05,
            nameGap: 44,
            axisLabel: { color: MUTED, formatter: (v) => `${(v * 100).toFixed(0)}%` }
        }),
        series: [
            diagonal(0, 0.05),
            {
                type: 'scatter',
                symbolSize: 6,
                large: true,
                itemStyle: { color: BLUE, opacity: 0.45 },
                data: checks.map((c) => [c.cost_of_deposits, c.regulatory_cost_of_deposits, c.display_name, c.quarter_label])
            }
        ]
    };
</script>

```sql headline
select
    filers,
    printf('%+.2f', spearman) as spearman_text,
    printf('%.3f', p_value) as p_text,
    printf('%+.2f', interval_low) as low_text,
    printf('%+.2f', interval_high) as high_text,
    supported
from marketscope.mart_persistence_result
where sample = 'headline'
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
    end_quarter,
    strftime(start_quarter, '%Y') || 'Q' || quarter(start_quarter) as start_text,
    strftime(end_quarter, '%Y') || 'Q' || quarter(end_quarter) as end_text,
    printf('%.2f%%', start_rate_fraction * 100) as start_rate_text,
    printf('%.2f%%', end_rate_fraction * 100) as end_rate_text,
    months
from marketscope.dim_rate_cycle
where cycle_name is not null
order by start_quarter
```

```sql ranks
select
    banks.display_name,
    comparison.calibration_rank,
    comparison.test_rank,
    comparison.quartile_shift
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
where comparison.in_headline
```

```sql secondary
select
    printf('%+.2f', corr(test_beta, calibration_beta)) as pearson_text,
    printf('%.2f', regr_slope(test_beta, calibration_beta)) as slope_text,
    printf('%.2f', regr_r2(test_beta, calibration_beta)) as r2_text,
    printf('%.2f', median(calibration_beta)) as median_calibration_text,
    printf('%.2f', median(test_beta)) as median_test_text
from marketscope.mart_cross_bank_comparison
where in_headline
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
    description,
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

```sql recovered_result
select
    filers,
    printf('%+.2f', spearman) as spearman_text
from marketscope.mart_persistence_result
where sample = 'R4+recovered'
```

```sql survivorship
select
    banks.display_name,
    comparison.calibration_beta,
    comparison.test_beta,
    coalesce(banks.exit_type = 'failure', false) as failed,
    case
        when banks.exit_type = 'failure'
            then 'Test beta to its last filing, ' || strftime(banks.last_filed_period, '%Y-%m-%d')
    end as note
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
where comparison.in_r4
union all
select
    bank,
    calibration_beta,
    test_beta,
    true,
    'From its Call Reports; test beta to ' || strftime(test_end, '%Y-%m-%d')
from marketscope.mart_recovered_beta
```

```sql deviators
select
    banks.display_name,
    printf('%.3f', comparison.calibration_beta) as calibration_beta,
    'Q' || cast(comparison.calibration_quartile as integer) as calibration_quartile,
    printf('%.3f', comparison.test_beta) as test_beta,
    'Q' || cast(comparison.test_quartile as integer) as test_quartile,
    '/banks/' || cast(cast(comparison.cik as bigint) as varchar) as bank_link
from marketscope.mart_cross_bank_comparison as comparison
join marketscope.dim_bank as banks using (cik)
where comparison.material_deviator
order by comparison.quartile_shift desc
```

```sql validation_points
select
    banks.display_name,
    strftime(facts.quarter_end, '%Y') || 'Q' || quarter(facts.quarter_end) as quarter_label,
    facts.cost_of_deposits,
    facts.regulatory_cost_of_deposits
from marketscope.fct_bank_quarter as facts
join marketscope.dim_bank as banks using (cik)
where facts.metric_tier = '1'
  and facts.cost_of_deposits is not null
  and facts.regulatory_cost_of_deposits is not null
```

```sql validation
select
    format('{:,}', count(*)) as pairs_text,
    count(distinct cik) as banks,
    printf('%.1f', median(abs(cost_of_deposits - regulatory_cost_of_deposits)) * 10000)
        as median_gap_text,
    printf('%.0f%%', 100 * avg(case when abs(cost_of_deposits - regulatory_cost_of_deposits) <= 0.001 then 1 else 0 end))
        as within_text
from marketscope.fct_bank_quarter
where metric_tier = '1'
  and cost_of_deposits is not null
  and regulatory_cost_of_deposits is not null
```

When the Federal Reserve raises rates, each bank decides how much of the rise to pass on to
its depositors. A bank that passes on little keeps its funding cheap; one that passes on a
lot pays to keep its deposits. The share it passes on over a cycle is its **deposit beta**.
This study asks whether that is a property of the bank: whether the banks that repriced
fastest in one tightening cycle did so again in the next.

## Two cycles, one fast and one slow

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

The calibration cycle ran from {cycles[0].start_text} to {cycles[0].end_text}, taking the
policy rate from {cycles[0].start_rate_text} to {cycles[0].end_rate_text} over
{cycles[0].months} months. The test cycle ran from {cycles[1].start_text} to
{cycles[1].end_text}, from {cycles[1].start_rate_text} to {cycles[1].end_rate_text} in
{cycles[1].months}. Betas run higher in a cycle like the second, so levels are not
compared. The test is of the **ordering**, by rank correlation, which a level shift does not
move.

## The plan, fixed before the result

Written down on 10 October 2026, before any cross-cycle figure was computed
([decision 0034](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/decisions.md)):

<Grid cols=2>
<div>

**Sample.** Ranked banks with a tier 1 beta in both cycles, tier 1 cost of deposits in at
least 80 percent of each cycle's quarters, no partial cycle and no material acquisition
inside either cycle. No bank is excluded for the value of its beta.

</div>
<div>

**Test.** Spearman correlation, judged by a one-sided permutation test (100,000
permutations) with a 95 percent bootstrap interval (10,000 resamples), seed 20261010.
Persistence is supported if the correlation is positive with p below 0.05.

</div>
</Grid>

## The result

<div style="background: linear-gradient(135deg, #0d366b 0%, #1c5cab 60%, #2a78d6 100%); color: #fff; border-radius: 14px; padding: 26px 32px; margin: 20px 0; display: flex; flex-wrap: wrap; gap: 28px; align-items: center;">
  <div style="font-size: 64px; font-weight: 700; line-height: 1;">{headline[0].spearman_text}</div>
  <div style="flex: 1 1 320px; font-size: 16px; line-height: 1.5;">
    Spearman correlation across {headline[0].filers} banks, one-sided p {headline[0].p_text},
    95% interval {headline[0].low_text} to {headline[0].high_text}.
    {#if headline[0].supported}<b>Persistence is supported</b> by the rule fixed in advance.{:else}<b>Persistence is not shown</b> by the rule fixed in advance.{/if}
  </div>
</div>

Each dot is a bank, placed by its rank in each cycle. A bank on the diagonal kept its exact
place. The fast end holds best: the cluster at the top right is the same banks in both
cycles, several of them direct banks with no branch network. The slow end is looser.

<ECharts config={rankConfig} height="460px" />

Secondary, and not the result, since levels are not expected to transfer: Pearson
{secondary[0].pearson_text}, and a least-squares fit of test beta on calibration beta with
slope {secondary[0].slope_text} and R² {secondary[0].r2_text}. The median beta rose from
{secondary[0].median_calibration_text} to {secondary[0].median_test_text}.

## Robust to every registered variant

<ECharts config={forestConfig} height="300px" />

## Survivorship strengthens it

A sample of banks that kept filing is survivors by construction. Silicon Valley Bank stopped
filing inside the test cycle; First Republic and Signature never filed with the SEC, so
their betas are recovered from their own Call Reports. Adding all three takes the
correlation to {recovered_result[0].spearman_text} across {recovered_result[0].filers}
banks. Leaving out the failed banks, as an EDGAR-only study must, slightly understates the
persistence.

<ECharts config={survivorConfig} height="440px" />

## Three banks that moved

Two or more quartiles apart between the cycles:

<DataTable data={deviators} link=bank_link>
    <Column id=display_name title="Bank" />
    <Column id=calibration_beta title="2015–19 beta" align=right />
    <Column id=calibration_quartile title="Quartile" align=center />
    <Column id=test_beta title="2022–23 beta" align=right />
    <Column id=test_quartile title="Quartile" align=center />
</DataTable>

Each hypothesis was formed after the result was seen, and only State Street's has been
tested.

- **State Street.** A custody bank with much of its deposits in other currencies, while euro
  rates stayed negative through 2015–2019. Tested against the Call Report split between
  domestic and foreign offices, the mechanism is there but does not explain the move: on its
  domestic offices alone State Street moves further. Its deviation is open.
- **Zions.** A commercially funded regional with a large uninsured base, exposed to the
  2023 regional bank deposit flight in a way it was not in 2015–2019.
- **Wells Fargo.** Under the Federal Reserve's asset cap throughout the test cycle, with
  little reason to pay for deposits it could not deploy. The cap came in February 2018, late
  in the calibration cycle.

## Is it the banks, or the tagging?

Every cost of deposits here is built from XBRL tags, and banks tag differently. So each one
is checked against the cost computed from the same bank's Call Reports. Each dot below is a
bank-quarter at tier 1: {validation[0].pairs_text} of them across {validation[0].banks}
banks. The median gap is **{validation[0].median_gap_text} basis points**, and
{validation[0].within_text} agree within 10.

<ECharts config={validationConfig} height="440px" />

Recomputed entirely on Call Report betas, and again on the Call Reports' own average
balances, the headline barely moves
([methodology 7.5 and 7.6](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md#7-validation-completed-so-far)).
The persistence belongs to the banks, not to how their filings are tagged.

## What it does not show

- A forecast for any one bank. The interval runs {headline[0].low_text} to
  {headline[0].high_text}.
- Anything about failure or distress.
- Three headline betas rest on an interest-bearing base that cannot be reconciled at one
  endpoint, and State Street's move is unexplained. The
  [methodology](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md)
  lists every limitation, including those resolved unsatisfactorily.
