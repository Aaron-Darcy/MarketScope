---
title: Deposit repricing across two tightening cycles
sidebar_position: 1
---

```sql headline
select * from marketscope.mart_persistence_result where sample = 'headline'
```

```sql survivorship
select
    case sample
        when 'headline' then 'Survivors only (headline)'
        when 'R4' then 'Adding SVB, measured to its last quarter'
        when 'R4+recovered' then 'Adding SVB, First Republic and Signature'
    end as sample_label,
    filers,
    spearman,
    p_value,
    interval_low,
    interval_high
from marketscope.mart_persistence_result
where sample in ('headline', 'R4', 'R4+recovered')
order by filers
```

```sql variants
select
    min(spearman) as lowest,
    max(spearman) as highest,
    bool_and(supported) as all_supported
from marketscope.mart_persistence_result
where sample in ('R1', 'R2', 'R3', 'R4')
```

```sql cycles
select
    cycle_name,
    strftime(start_quarter, '%Y') || 'Q' || quarter(start_quarter) as start_label,
    strftime(end_quarter, '%Y') || 'Q' || quarter(end_quarter) as end_label,
    start_rate_fraction,
    end_rate_fraction,
    move_fraction,
    months
from marketscope.dim_rate_cycle
where cycle_name is not null
order by start_quarter
```

```sql coverage
select
    count(distinct cik) as members,
    count(cost_of_deposits) as resolved_quarters,
    count(*) filter (where metric_tier = '1') / count(cost_of_deposits) as tier_1_share
from marketscope.fct_bank_quarter
```

```sql validation
select
    count(*) as pairs,
    median(abs(cost_of_deposits - regulatory_cost_of_deposits)) * 10000 as median_gap_bp,
    avg(case when abs(cost_of_deposits - regulatory_cost_of_deposits) <= 0.001 then 1 else 0 end)
        as within_10bp
from marketscope.fct_bank_quarter
where metric_tier = '1'
  and cost_of_deposits is not null
  and regulatory_cost_of_deposits is not null
```

> Does deposit repricing behaviour observed during one monetary-tightening cycle help
> explain cross-bank funding-cost pressure during the next?

A bank's deposit beta is the share of a policy rate rise it passes through to the rate it
pays depositors. MarketScope measures it for the largest US deposit-taking filers directly
from their SEC XBRL filings, over the 2015–2019 tightening and again over the far faster
2022–2023 one, and asks whether banks keep their place in the ordering.

<Grid cols=4>
<BigValue data={headline} value=spearman title="Spearman, calibration against test" fmt='+0.000' />
<BigValue data={headline} value=p_value title="One-sided permutation p" fmt='0.0000' />
<BigValue data={headline} value=interval_low title="95% interval, low" fmt='+0.000' />
<BigValue data={headline} value=interval_high title="95% interval, high" fmt='+0.000' />
</Grid>

## The finding

Across the <Value data={headline} column=filers /> filers that meet the sample rules fixed
before the result was computed, the rank correlation between each bank's calibration-cycle
and test-cycle beta is <Value data={headline} column=spearman fmt='+0.000' />. The four
robustness variants registered beside the headline give
<Value data={variants} column=lowest fmt='+0.000' /> to
<Value data={variants} column=highest fmt='+0.000' />.

{#if headline[0].supported}

By the rule set in advance, a positive correlation with p below 0.05, persistence is
supported: banks that passed more of the 2015–2019 tightening through to their depositors
than their peers tended to pass more of the 2022–2023 tightening through as well.

{:else}

That does not clear the bar set in advance, a positive correlation with p below 0.05, so
persistence is not shown. At this sample size that is not evidence of its absence.

{/if}

The two cycles differ in size and pace, so beta levels are not expected to carry over and
are not compared. The claim concerns the ordering.

<DataTable data={cycles}>
    <Column id=cycle_name title="Cycle" />
    <Column id=start_label title="From" />
    <Column id=end_label title="To" />
    <Column id=start_rate_fraction title="Policy rate at start" fmt=pct2 />
    <Column id=end_rate_fraction title="Policy rate at end" fmt=pct2 />
    <Column id=months title="Months" />
</DataTable>

Rates are quarterly averages of the effective federal funds rate, the values each beta is
computed against.

## Survivorship

A sample of banks that kept filing is survivors by construction. Silicon Valley Bank
stopped filing inside the test cycle, and First Republic and Signature never filed with
the SEC at all, so their betas are recovered from their own Call Reports. Adding them
strengthens the result rather than weakening it: leaving out the failed banks, as an
EDGAR-only sample must, slightly understates the persistence.

<DataTable data={survivorship}>
    <Column id=sample_label title="Sample" />
    <Column id=filers title="Filers" />
    <Column id=spearman title="Spearman" fmt='+0.000' />
    <Column id=p_value title="p" fmt='0.0000' />
    <Column id=interval_low title="95% interval, low" fmt='+0.000' />
    <Column id=interval_high title="95% interval, high" fmt='+0.000' />
</DataTable>

## What is and is not claimed

Claimed:

- Across these banks, the ordering by deposit beta in one tightening cycle is associated
  with the ordering in the next, on a test, sample and interval fixed before the result was
  computed.
- The cost of deposits behind it is measured, not assumed, to agree with the banks' Call
  Reports: at tier 1 the median gap is
  <Value data={validation} column=median_gap_bp fmt='0.0' /> basis points, and
  <Value data={validation} column=within_10bp fmt=pct1 /> of
  <Value data={validation} column=pairs fmt=num0 /> bank-quarters agree within 10.

Not claimed:

- A forecast for any one bank. This is an association across
  <Value data={headline} column=filers /> banks, and its interval is wide: the data are
  consistent with a correlation as modest as
  <Value data={headline} column=interval_low fmt='+0.00' /> or as strong as
  <Value data={headline} column=interval_high fmt='+0.00' />.
- Anything about failure or distress. The question is whether a measurable behaviour
  persists, not which institutions come to harm.
- That beta levels transfer between cycles, or that the measure is new. Deposit betas are
  well documented; the contribution is measuring them from primary filings at coverage, with
  an out-of-sample design and a stated error rate.

## The data

<Value data={coverage} column=resolved_quarters fmt=num0 /> bank-quarters of cost of
deposits across <Value data={coverage} column=members /> filers, built from SEC EDGAR XBRL
company facts and the FRED federal funds series, with FDIC and FFIEC Call Reports used to
check them. <Value data={coverage} column=tier_1_share fmt=pct0 /> resolve at tier 1, the
most precise of the comparability tiers, and no tier is mixed with another without being
marked. Every merger, exit and failure is recorded from the filing that reports it, and
filers that stopped reporting are kept.

- [Bank explorer](/banks): every filer's series, beta by cycle, tier and coverage
- [Cross-bank comparison](/comparison): rankings, distributions and quartile transitions
- [Deposit beta persistence](/persistence): the case study in full
- [Methodology](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md):
  how each figure is produced, and what is not yet handled
