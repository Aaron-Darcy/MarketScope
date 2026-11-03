```sql bank
select
    overview.*,
    members.state_of_incorporation,
    members.first_filed_period,
    members.pinned_reason,
    members.acquisitions,
    members.material_acquisitions,
    'Stopped filing after its report for the period ending '
        || strftime(overview.last_filed_period, '%Y-%m-%d') || '. '
        || case overview.exit_type
            when 'exit_merger' then 'Merged into ' || overview.exit_counterparty || ' on '
            when 'failure' then 'Failed on '
            when 'exit_deregistration' then 'Deregistered on '
        end
        || strftime(overview.exit_date, '%Y-%m-%d') || '.' as exit_text
from marketscope.mart_bank_overview as overview
join marketscope.dim_bank as members using (cik)
where overview.cik = ${params.cik}
```

```sql cycles
select cycle_name, start_quarter, end_quarter
from marketscope.dim_rate_cycle
where cycle_name is not null
```

```sql cost_against_policy
select quarter_end, 'Cost of deposits, XBRL' as measure, cost_of_deposits as rate
from marketscope.fct_bank_quarter
where cik = ${params.cik} and cost_of_deposits is not null
union all
select quarter_end, 'Cost of deposits, Call Reports', regulatory_cost_of_deposits
from marketscope.fct_bank_quarter
where cik = ${params.cik} and regulatory_cost_of_deposits is not null
union all
select quarter_end, 'Federal funds, quarterly average', policy_rate_fraction
from marketscope.fct_bank_quarter
where cik = ${params.cik} and policy_rate_fraction is not null
order by quarter_end
```

```sql betas
select
    cycle_name,
    start_quarter,
    measured_end_quarter,
    partial_cycle,
    metric_tier,
    start_cost_of_deposits,
    end_cost_of_deposits,
    end_rate_fraction - start_rate_fraction as policy_move,
    deposit_beta,
    tier_1_quarters,
    cycle_quarters,
    material_event_in_cycle
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
    event_date,
    case event_type
        when 'acquisition' then 'Acquisition'
        when 'reverse_acquisition' then 'Reverse acquisition'
        when 'exit_merger' then 'Merged out'
        when 'exit_deregistration' then 'Deregistered'
        when 'failure' then 'Failure'
    end as event_type,
    counterparty,
    deposit_step,
    material,
    evidence_form,
    evidence_accession,
    note
from marketscope.bank_entity_events
where cik = ${params.cik}
order by event_date
```

```sql quarters
select
    quarter_end,
    cost_of_deposits,
    metric_tier,
    expense_provenance,
    balance_provenance,
    avg_method,
    q4_derived,
    regulatory_cost_of_deposits,
    total_deposits,
    event_type
from marketscope.fct_bank_quarter
where cik = ${params.cik}
order by quarter_end desc
```

{#if bank.length === 0}

No filer in the universe has CIK {params.cik}. [Return to the bank explorer](/banks).

{:else}

# {bank[0].registrant_name}

{#if bank[0].rank}

Ranked {bank[0].rank} of the largest fifty by peak total assets. {bank[0].sic_description}.
SEC CIK {bank[0].cik}.

{:else}

Pinned beside the ranked fifty. {bank[0].sic_description}. SEC CIK {bank[0].cik}.
{bank[0].pinned_reason}

{/if}

{#if bank[0].exit_type}

{bank[0].exit_text}

{/if}

<Grid cols=4>
<BigValue data={bank} value=calibration_beta title="Calibration beta, 2015–2019" fmt='0.000' />
<BigValue data={bank} value=test_beta title="Test beta, 2022–2023" fmt='0.000' />
<BigValue data={bank} value=tier_1_share title="Quarters at tier 1" fmt=pct0 />
<BigValue data={bank} value=median_regulatory_gap_bp title="Median gap to Call Reports, bp" fmt='0.0' />
</Grid>

## Cost of deposits against the policy rate

Interest expense on deposits, annualised, over the mean of the opening and closing deposit
base its tier names, beside the same arithmetic on the Call Reports of the bank's insured
institutions and the federal funds rate. Shaded: the two study cycles.

<LineChart data={cost_against_policy} x=quarter_end y=rate series=measure yFmt=pct2 chartAreaHeight=280>
    <ReferenceArea data={cycles} xMin=start_quarter xMax=end_quarter label=cycle_name />
</LineChart>

## Beta by cycle

A cycle's beta is the change in cost of deposits from its first quarter to its last,
divided by the change in the policy rate over the same quarters. Partial cycles end at the
filer's last resolved quarter.

<DataTable data={betas}>
    <Column id=cycle_name title="Cycle" />
    <Column id=start_quarter title="From" fmt='yyyy-mm-dd' />
    <Column id=measured_end_quarter title="Measured to" fmt='yyyy-mm-dd' />
    <Column id=partial_cycle title="Partial" />
    <Column id=metric_tier title="Tier" />
    <Column id=start_cost_of_deposits title="Cost at start" fmt=pct2 />
    <Column id=end_cost_of_deposits title="Cost at end" fmt=pct2 />
    <Column id=policy_move title="Policy move" fmt=pct2 />
    <Column id=deposit_beta title="Beta" fmt='0.000' />
    <Column id=tier_1_quarters title="Tier 1 quarters" />
    <Column id=cycle_quarters title="Of" />
    <Column id=material_event_in_cycle title="Material acquisition" />
</DataTable>

## Metric tier and coverage

Each quarter's comparability tier. Tier 1 divides interest expense on deposits by
interest-bearing deposits; tier 2 divides it by total deposits, where no interest-bearing
base resolves; tier 3 reconstructs the expense from its components over the best base
available; tier X is a reconstruction that failed the completeness check and enters no
beta. A quarter with a balance but no cost is shown as balance
only. <Value data={bank} column=cost_quarters /> quarters resolve a cost, from
<Value data={bank} column=first_cost_quarter fmt='yyyy-mm-dd' /> to
<Value data={bank} column=last_cost_quarter fmt='yyyy-mm-dd' />.

<BarChart data={tiers} x=quarter_end y=quarters series=tier type=stacked yAxisLabels=false yGridlines=false chartAreaHeight=80 />

## Deposits

{#if deposits.length > 0}

<AreaChart data={deposits} x=quarter_end y=deposits series=kind yFmt=usd1b />

{:else}

This filer tags neither an interest-bearing nor a non-interest-bearing deposit balance.

{/if}

## Mergers, exits and failures

{#if events.length > 0}
Each event cites the filing that reports it. A deposit step of a tenth or more in the
quarter an acquisition completes makes it material.

<DataTable data={events}>
    <Column id=event_date title="Date" fmt='yyyy-mm-dd' />
    <Column id=event_type title="Event" />
    <Column id=counterparty title="Counterparty" />
    <Column id=deposit_step title="Deposit step" fmt=pct1 />
    <Column id=material title="Material" />
    <Column id=evidence_form title="Form" />
    <Column id=evidence_accession title="Accession" />
    <Column id=note title="Note" wrap=true />
</DataTable>
{:else}
No merger, exit or failure is recorded for this filer.
{/if}

<Details title="Every quarter">

<DataTable data={quarters} rows=20>
    <Column id=quarter_end title="Quarter" fmt='yyyy-mm-dd' />
    <Column id=cost_of_deposits title="Cost of deposits" fmt=pct2 />
    <Column id=metric_tier title="Tier" />
    <Column id=expense_provenance title="Expense from" />
    <Column id=balance_provenance title="Balance from" />
    <Column id=avg_method title="Averaging" />
    <Column id=q4_derived title="Q4 derived" />
    <Column id=regulatory_cost_of_deposits title="Call Reports" fmt=pct2 />
    <Column id=total_deposits title="Total deposits" fmt=usd1b />
    <Column id=event_type title="Event" />
</DataTable>

</Details>

{/if}
