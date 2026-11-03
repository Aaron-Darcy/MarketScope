---
title: Deposit beta persistence
sidebar_position: 4
---

```sql headline
select * from marketscope.mart_persistence_result where sample = 'headline'
```

```sql cycles
select
    cycle_name,
    start_quarter,
    end_quarter,
    start_rate_fraction,
    end_rate_fraction,
    move_fraction,
    months,
    move_fraction / months * 12 as move_per_year
from marketscope.dim_rate_cycle
where cycle_name is not null
order by start_quarter
```

```sql ranks
select
    registrant_name,
    calibration_rank,
    test_rank,
    case when material_deviator then 'Material deviator' else 'Within one quartile' end as placement
from marketscope.mart_cross_bank_comparison
where in_headline
order by placement
```

```sql fastest
with sample as (
    select count(*) as filers from marketscope.mart_cross_bank_comparison where in_headline
)
select
    count(*) filter (where calibration_rank > filers - 6) as fastest_calibration,
    count(*) filter (where calibration_rank > filers - 6 and test_rank > filers - 6)
        as stayed_fastest
from marketscope.mart_cross_bank_comparison, sample
where in_headline
```

```sql secondary
select
    corr(test_beta, calibration_beta) as pearson,
    regr_slope(test_beta, calibration_beta) as slope,
    regr_intercept(test_beta, calibration_beta) as intercept,
    regr_r2(test_beta, calibration_beta) as r_squared,
    median(calibration_beta) as median_calibration,
    median(test_beta) as median_test
from marketscope.mart_cross_bank_comparison
where in_headline
```

```sql samples
select
    case sample
        when 'headline' then 'Headline'
        when 'R4+recovered' then 'R4 with recovered banks'
        else sample
    end as sample_label,
    description,
    filers,
    spearman,
    p_value,
    interval_low,
    interval_high,
    supported
from marketscope.mart_persistence_result
order by case sample when 'headline' then 0 else 1 end, sample
```

```sql deviators
select
    registrant_name,
    calibration_beta,
    calibration_quartile,
    test_beta,
    test_quartile,
    '/banks/' || cast(cast(cik as bigint) as varchar) as bank_link
from marketscope.mart_cross_bank_comparison
where material_deviator
order by quartile_shift desc
```

```sql validation
select
    count(*) as pairs,
    count(distinct cik) as filers,
    median(abs(cost_of_deposits - regulatory_cost_of_deposits)) * 10000 as median_gap_bp,
    avg(case when abs(cost_of_deposits - regulatory_cost_of_deposits) <= 0.001 then 1 else 0 end)
        as within_10bp
from marketscope.fct_bank_quarter
where metric_tier = '1'
  and cost_of_deposits is not null
  and regulatory_cost_of_deposits is not null
```

## The question

When the Federal Reserve raises rates, a bank decides how much of the rise to pass on to
its depositors. The share it passes on over a tightening cycle is its deposit beta. A bank
that passes on little keeps its funding cheap and its margin wide; one that passes on a lot
pays to keep its deposits. The question here is whether that behaviour is a property of the
bank: whether a bank that repriced faster than its peers in one cycle did so again in the
next.

The two cycles are very different, which is what makes them a test:

<DataTable data={cycles}>
    <Column id=cycle_name title="Cycle" />
    <Column id=start_quarter title="From" fmt='yyyy-mm-dd' />
    <Column id=end_quarter title="To" fmt='yyyy-mm-dd' />
    <Column id=start_rate_fraction title="Policy rate at start" fmt=pct2 />
    <Column id=end_rate_fraction title="At end" fmt=pct2 />
    <Column id=months title="Months" />
    <Column id=move_per_year title="Rise per year" fmt=pct2 />
</DataTable>

Betas run higher in a faster and larger cycle, so levels are not expected to carry over and
are not compared. The test is of the ordering, by rank correlation, which a level shift
does not move.

## The plan, fixed before the result

The sample, statistic, test, interval and robustness variants were written down on 10
October 2026, before any cross-cycle figure had been computed
([decision 0034](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/decisions.md)).

- **Sample.** A filer in the ranked fifty with a tier 1 beta in both cycles, tier 1 cost of
  deposits in at least 80 percent of each cycle's quarters, no partial cycle, and no
  material acquisition inside either cycle. No filer is excluded for the value of its beta.
- **Statistic.** The Spearman correlation between calibration-cycle and test-cycle betas.
- **Test.** One-sided permutation test of a positive correlation, 100,000 permutations,
  with a 95 percent percentile bootstrap interval from 10,000 resamples, seed 20261010.
- **Reading.** Persistence is supported if the correlation is positive with p below 0.05.
  A result that misses the bar is reported as not shown, not as absent.

## The result

<Grid cols=4>
<BigValue data={headline} value=filers title="Filers" />
<BigValue data={headline} value=spearman title="Spearman" fmt='+0.000' />
<BigValue data={headline} value=p_value title="One-sided p" fmt='0.0000' />
<BigValue data={headline} value=interval_low title="95% interval from" fmt='+0.000' />
</Grid>

The interval runs from <Value data={headline} column=interval_low fmt='+0.000' /> to
<Value data={headline} column=interval_high fmt='+0.000' />.

{#if headline[0].supported}

By the rule fixed in advance, persistence is supported: a bank that passed more of the
2015–2019 tightening through to its depositors than its peers tended to pass more of the
2022–2023 tightening through as well.

{:else}

By the rule fixed in advance, persistence is not shown. At this sample size that is not
evidence of its absence.

{/if}

<ScatterPlot
    data={ranks}
    x=calibration_rank
    y=test_rank
    series=placement
    tooltipTitle=registrant_name
    xAxisTitle="Calibration rank, 1 the slowest"
    yAxisTitle="Test rank"
    chartAreaHeight=360
/>

The persistence is strongest at the fast end: <Value data={fastest} column=stayed_fastest /> of the <Value data={fastest} column=fastest_calibration /> fastest repricers of the calibration
cycle were among the six fastest of the test cycle. The slow end of the ordering is less
stable. The [comparison page](/comparison) shows every bank's place and the full quartile
transition matrix.

Secondary, and not the result, since levels are not expected to transfer: the Pearson
correlation is <Value data={secondary} column=pearson fmt='+0.000' />, and a least-squares
fit of test beta on calibration beta has slope
<Value data={secondary} column=slope fmt='0.000' /> and R²
<Value data={secondary} column=r_squared fmt='0.000' />. The median beta rose from
<Value data={secondary} column=median_calibration fmt='0.000' /> to
<Value data={secondary} column=median_test fmt='0.000' />.

## Robustness and survivorship

Each variant was registered beside the headline and none replaces it. R4 and its extension
are the survivorship comparison: the headline is survivors by construction, since a bank
that stopped filing inside the test cycle has only a partial beta.

<DataTable data={samples}>
    <Column id=sample_label title="Sample" />
    <Column id=description title="Change to the sample" wrap=true />
    <Column id=filers title="Filers" />
    <Column id=spearman title="Spearman" fmt='+0.000' />
    <Column id=p_value title="p" fmt='0.0000' />
    <Column id=interval_low title="95% interval, low" fmt='+0.000' />
    <Column id=interval_high title="High" fmt='+0.000' />
    <Column id=supported title="Supported" />
</DataTable>

Silicon Valley Bank enters R4 on a test beta measured to its last filed quarter. First
Republic and Signature never filed with the SEC, so their betas come from their own Call
Reports by the same arithmetic. Adding the failed banks strengthens the correlation, which
is the direction survivorship bias was expected to run: an EDGAR-only sample slightly
understates the persistence. Two of the betas in that comparison come from Call Reports and
the rest from XBRL; the two sources order banks almost identically within each cycle
([methodology 7.5](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md#75-error-attribution)).

## Material deviators

Filers two or more quartiles apart between the cycles:

<DataTable data={deviators} link=bank_link>
    <Column id=registrant_name title="Filer" />
    <Column id=calibration_beta title="Calibration beta" fmt='0.000' />
    <Column id=calibration_quartile title="Quartile" />
    <Column id=test_beta title="Test beta" fmt='0.000' />
    <Column id=test_quartile title="Quartile" />
</DataTable>

Each hypothesis below was formed after the result was seen, and only State Street's has
been tested.

- **State Street.** A custody bank holds much of its deposits in other currencies, and euro
  policy rates stayed negative through 2015–2019 while the dollar rate rose. Tested against
  the Call Report split between domestic and foreign offices, the mechanism is there but
  does not explain the move: measured on its domestic offices alone, State Street moves
  further. Its deviation is open.
- **Zions.** A commercially funded regional with a large uninsured deposit base, exposed to
  the 2023 regional bank deposit flight in a way it was not in 2015–2019.
- **Wells Fargo.** Under the Federal Reserve's asset cap throughout the test cycle, it had
  little use for deposits it could not deploy and so little reason to pay for them. The cap
  was imposed in February 2018, late in the calibration cycle.

## Is it the banks, or the tagging?

Every cost of deposits here is built from XBRL tags, and filers tag differently. Each
bank-quarter is therefore checked against the cost computed from the same group's Call
Reports by the same arithmetic. At tier 1, across <Value data={validation} column=pairs fmt=num0 /> bank-quarters and <Value data={validation} column=filers /> filers, the median gap is <Value data={validation} column=median_gap_bp fmt='0.0' /> basis points and <Value data={validation} column=within_10bp fmt=pct1 /> agree within 10. Recomputed
entirely on Call Report betas, and again on the Call Reports' own average balances in place
of the endpoint averages the XBRL metric has to use, the headline barely moves
([methodology 7.5 and 7.6](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md#7-validation-completed-so-far)).
The persistence belongs to the banks' reported deposit costs, not to how their filings are
tagged.

## What the result does not show

- It is an association across <Value data={headline} column=filers /> banks, not a
  forecast for any one of them, and nothing here predicts failure or distress.
- Its interval is wide. The data are consistent with a correlation as modest as <Value data={headline} column=interval_low fmt='0.00' /> or as strong as <Value data={headline} column=interval_high fmt='0.00' />.
- Three of the headline betas rest on an interest-bearing base that cannot be reconciled
  at one endpoint, and the explanation for State Street's move is open. The
  [methodology](https://github.com/Aaron-Darcy/MarketScope/blob/main/docs/methodology.md)
  lists every limitation, including those resolved unsatisfactorily.
