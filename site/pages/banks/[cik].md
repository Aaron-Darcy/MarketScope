<script>
    import { BLUE, ORANGE, GREY, INK, MUTED, GRID, TIERS } from '../../../components/palette.js';

    $: dots = [...peers];
    $: stripConfig = {
        grid: { left: 110, right: 24, top: 8, bottom: 48 },
        tooltip: {
            trigger: 'item',
            formatter: (p) => `<b>${p.data[2]}</b><br/>beta ${p.data[0].toFixed(3)}`
        },
        xAxis: {
            min: 0,
            max: 1,
            name: 'Deposit beta',
            nameLocation: 'middle',
            nameGap: 28,
            nameTextStyle: { color: MUTED },
            axisLabel: { color: MUTED },
            splitLine: { lineStyle: { color: GRID } }
        },
        yAxis: {
            min: -0.5,
            max: 1.5,
            interval: 0.5,
            axisLabel: {
                color: INK,
                fontSize: 12,
                formatter: (v) => (v === 0 ? '2015–2019' : v === 1 ? '2022–2023' : '')
            },
            splitLine: { show: false },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        series: [
            {
                type: 'scatter',
                symbolSize: 9,
                itemStyle: { color: GREY, opacity: 0.8 },
                data: dots.filter((d) => !d.is_bank).map((d) => [d.deposit_beta, d.position, d.display_name]),
                z: 1
            },
            {
                type: 'scatter',
                symbolSize: 18,
                itemStyle: { color: ORANGE, borderColor: '#fff', borderWidth: 2 },
                data: dots.filter((d) => d.is_bank).map((d) => [d.deposit_beta, d.position, d.display_name]),
                label: {
                    show: true,
                    position: 'top',
                    distance: 6,
                    formatter: (p) => p.data[0].toFixed(2),
                    color: INK,
                    fontWeight: 600
                },
                z: 2
            }
        ]
    };
</script>

```sql bank
select
    overview.*,
    banks.display_name,
    banks.pinned_reason,
    case
        when overview.rank is not null
            then 'Ranked ' || cast(overview.rank as integer) || ' of the largest fifty by peak total assets'
        else 'Pinned beside the ranked fifty'
    end as rank_text,
    case overview.exit_type
        when 'exit_merger'
            then 'Merged into ' || overview.exit_counterparty || ' on ' || strftime(overview.exit_date, '%-d %B %Y')
        when 'failure' then 'Failed on ' || strftime(overview.exit_date, '%-d %B %Y')
        when 'exit_deregistration' then 'Deregistered on ' || strftime(overview.exit_date, '%-d %B %Y')
        else 'Still filing'
    end as status_text,
    coalesce(printf('%.2f', overview.calibration_beta), '–') as calibration_text,
    coalesce(printf('%.2f', overview.test_beta), '–') as test_text,
    printf('%.0f%%', overview.tier_1_share * 100) as tier_1_text,
    coalesce(printf('%.1f bp', overview.median_regulatory_gap_bp), '–') as gap_text,
    strftime(overview.first_cost_quarter, '%Y') as first_year,
    strftime(overview.last_cost_quarter, '%Y') as last_year
from marketscope.mart_bank_overview as overview
join marketscope.dim_bank as banks using (cik)
where overview.cik = ${params.cik}
```

```sql peers
with betas as (
    select
        betas.cik,
        banks.display_name,
        betas.cycle_name,
        betas.deposit_beta,
        case betas.cycle_name when 'calibration' then 0 else 1 end as cycle_position
    from marketscope.fct_deposit_beta as betas
    join marketscope.dim_bank as banks using (cik)
    where betas.deposit_beta is not null
)
select
    display_name,
    deposit_beta,
    cik = ${params.cik} as is_bank,
    cycle_position + case when cik = ${params.cik} then 0 else ((cik * 7919) % 41 - 20) / 80.0 end
        as position
from betas
```

```sql peer_rank
with own as (
    select cycle_name, deposit_beta
    from marketscope.fct_deposit_beta
    where cik = ${params.cik} and deposit_beta is not null
)
select
    'It passed on a larger share of the rate rise than '
        || string_agg(
            slower || ' of ' || others || ' other banks in '
                || case cycle_name when 'calibration' then '2015–2019' else '2022–2023' end,
            ', and than ' order by cycle_name
        ) || '.' as sentence
from (
    select own.cycle_name, count(*) filter (where peers.deposit_beta < own.deposit_beta) as slower,
        count(*) - 1 as others
    from own
    join marketscope.fct_deposit_beta as peers
        on peers.cycle_name = own.cycle_name and peers.deposit_beta is not null
    group by own.cycle_name
)
```

```sql cycles
select
    case cycle_name when 'calibration' then 'Calibration' else 'Test' end as label,
    start_quarter,
    end_quarter
from marketscope.dim_rate_cycle
where cycle_name is not null
```

```sql cost_against_policy
select quarter_end, 'This bank, from its SEC filings' as measure, cost_of_deposits as rate
from marketscope.fct_bank_quarter
where cik = ${params.cik} and cost_of_deposits is not null
union all
select quarter_end, 'This bank, from its Call Reports', regulatory_cost_of_deposits
from marketscope.fct_bank_quarter
where cik = ${params.cik} and regulatory_cost_of_deposits is not null
union all
select quarter_end, 'Federal funds rate', policy_rate_fraction
from marketscope.fct_bank_quarter
where cik = ${params.cik} and policy_rate_fraction is not null
order by quarter_end
```

```sql betas
select
    case cycle_name when 'calibration' then '2015–2019' else '2022–2023' end as cycle,
    strftime(start_quarter, '%Y') || 'Q' || quarter(start_quarter) as from_quarter,
    strftime(measured_end_quarter, '%Y') || 'Q' || quarter(measured_end_quarter) as to_quarter,
    metric_tier,
    start_cost_of_deposits,
    end_cost_of_deposits,
    end_rate_fraction - start_rate_fraction as policy_move,
    deposit_beta,
    concat_ws(', ',
        case when partial_cycle then 'cycle cut short' end,
        case when material_event_in_cycle then 'material acquisition' end,
        case when tier_changes_in_cycle then 'tier changes' end
    ) as flags
from marketscope.fct_deposit_beta
where cik = ${params.cik}
order by start_quarter
```

```sql tiers
select
    quarter_end,
    case metric_tier
        when '1' then 'Tier 1'
        when '2' then 'Tier 2'
        when '3' then 'Tier 3'
        when 'X' then 'Tier X'
        else 'Balance only'
    end as tier,
    1 as quarters
from marketscope.fct_bank_quarter
where cik = ${params.cik}
order by quarter_end
```

```sql deposits
select quarter_end, 'Interest-bearing' as kind, interest_bearing_deposits as deposits
from marketscope.fct_bank_quarter
where cik = ${params.cik} and interest_bearing_deposits is not null
union all
select quarter_end, 'Non-interest-bearing', noninterest_bearing_deposits
from marketscope.fct_bank_quarter
where cik = ${params.cik} and noninterest_bearing_deposits is not null
order by quarter_end
```

```sql events
select
    strftime(event_date, '%Y-%m-%d') as date,
    case event_type
        when 'acquisition' then 'Acquisition'
        when 'reverse_acquisition' then 'Reverse acquisition'
        when 'exit_merger' then 'Merged out'
        when 'exit_deregistration' then 'Deregistered'
        when 'failure' then 'Failure'
    end as event,
    counterparty,
    deposit_step,
    case when material then '●' else '' end as material,
    evidence_form,
    'https://www.sec.gov/Archives/edgar/data/' || cast(cast(cik as bigint) as varchar) || '/'
        || replace(evidence_accession, '-', '') || '/' as filing_link
from marketscope.bank_entity_events
where cik = ${params.cik}
order by event_date
```

{#if bank.length === 0}

No bank in the universe has CIK {params.cik}. [Return to the bank explorer](/banks).

{:else}

<div style="background: linear-gradient(135deg, #0d366b 0%, #1c5cab 60%, #2a78d6 100%); color: #fff; border-radius: 14px; padding: 26px 32px; margin: 8px 0 24px;">
  <div style="font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.8;">{bank[0].rank_text}</div>
  <div style="font-size: 38px; font-weight: 700; margin: 4px 0 2px;">{bank[0].display_name}</div>
  <div style="font-size: 15px; opacity: 0.9;">{bank[0].status_text} · {bank[0].sic_description} · SEC CIK {bank[0].cik}</div>
  <div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 22px;">
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 12px 16px;">
      <div style="font-size: 30px; font-weight: 700;">{bank[0].calibration_text}</div>
      <div style="font-size: 13px; opacity: 0.85;">deposit beta, 2015–2019</div>
    </div>
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 12px 16px;">
      <div style="font-size: 30px; font-weight: 700;">{bank[0].test_text}</div>
      <div style="font-size: 13px; opacity: 0.85;">deposit beta, 2022–2023</div>
    </div>
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 12px 16px;">
      <div style="font-size: 30px; font-weight: 700;">{bank[0].tier_1_text}</div>
      <div style="font-size: 13px; opacity: 0.85;">of {bank[0].cost_quarters} quarters at tier 1, {bank[0].first_year}–{bank[0].last_year}</div>
    </div>
    <div style="background: rgba(255,255,255,0.12); border-radius: 10px; padding: 12px 16px;">
      <div style="font-size: 30px; font-weight: 700;">{bank[0].gap_text}</div>
      <div style="font-size: 13px; opacity: 0.85;">median gap to its Call Reports</div>
    </div>
  </div>
</div>

{#if bank[0].pinned_reason}

{bank[0].pinned_reason}

{/if}

## What it paid depositors, against the Fed

Interest expense on deposits, annualised, over the average deposit base, from the bank's
SEC filings and, as a check, from its own Call Reports; where the two agree they draw as
one line. Shaded: the two tightening cycles.

<LineChart
    data={cost_against_policy}
    x=quarter_end
    y=rate
    series=measure
    yFmt=pct1
    seriesOrder={['Federal funds rate', 'This bank, from its Call Reports', 'This bank, from its SEC filings']}
    seriesColors={{
        'This bank, from its SEC filings': '#2a78d6',
        'This bank, from its Call Reports': '#eb6834',
        'Federal funds rate': '#b4b2ab'
    }}
    chartAreaHeight=300
>
    <ReferenceArea data={cycles} xMin=start_quarter xMax=end_quarter label=label color=#2a78d6 />
</LineChart>

## Where it sits among its peers

Every bank's deposit beta in each cycle (grey), with this one highlighted.
{peer_rank[0]?.sentence}

<ECharts config={stripConfig} height="220px" />

<DataTable data={betas}>
    <Column id=cycle title="Cycle" />
    <Column id=from_quarter title="From" />
    <Column id=to_quarter title="Measured to" />
    <Column id=metric_tier title="Tier" align=center />
    <Column id=start_cost_of_deposits title="Cost at start" fmt=pct2 />
    <Column id=end_cost_of_deposits title="Cost at end" fmt=pct2 />
    <Column id=policy_move title="Fed move" fmt=pct2 />
    <Column id=deposit_beta title="Beta" fmt='0.000' />
    <Column id=flags title="Notes" />
</DataTable>

## Comparability tier, quarter by quarter

<BarChart
    data={tiers}
    x=quarter_end
    y=quarters
    series=tier
    type=stacked
    seriesColors={TIERS}
    yAxisLabels=false
    yGridlines=false
    chartAreaHeight=70
/>

## Deposits

{#if deposits.length > 0}

<AreaChart
    data={deposits}
    x=quarter_end
    y=deposits
    series=kind
    yFmt=usd0b
    seriesColors={{ 'Interest-bearing': '#2a78d6', 'Non-interest-bearing': '#86b6ef' }}
    chartAreaHeight=240
/>

{:else}

This bank tags neither an interest-bearing nor a non-interest-bearing deposit balance.

{/if}

## Mergers, exits and failures

{#if events.length > 0}

Each links to the filing that reports it. An acquisition is material when it moves the
deposit base by a tenth or more in the quarter it completes.

<DataTable data={events}>
    <Column id=date title="Date" />
    <Column id=event title="Event" />
    <Column id=counterparty title="Counterparty" />
    <Column id=deposit_step title="Deposit step" fmt=pct1 />
    <Column id=material title="Material" align=center />
    <Column id=filing_link title="Filing" contentType=link linkLabel=evidence_form openInNewTab=true />
</DataTable>

{:else}

No merger, exit or failure is recorded for this bank.

{/if}

{/if}
