# Specification

Version 1.0 · 2 September 2026

---

## 1. Scope

MarketScope measures deposit repricing behaviour across US bank holding companies using
primary SEC EDGAR filings and Federal Reserve data, and tests whether that behaviour is
persistent across monetary-tightening cycles.

The initial release covers the largest 50 US bank holding companies by total assets,
identified by SIC codes 6020, 6021, 6022, 6035 and 6036, restricted to filers with a 10-K
covering fiscal 2015 or later. Institutions that have since failed or been acquired are
retained.

### 1.1 Research question

Primary:

> Does deposit repricing behaviour observed during one monetary-tightening cycle help
> explain cross-bank funding-cost pressure during the next?

Secondary:

> Does filing behaviour — filing delay, amendments, restatements and late-filing notices —
> carry early-warning information about subsequent fundamental deterioration?

The secondary question uses metadata the ingestion layer produces regardless, and is
reported as a subordinate investigation rather than a co-headline result.

### 1.2 Out of scope

- Price prediction of any kind.
- Failure or distress prediction. The primary question concerns explanatory persistence of
  a measurable behaviour, not forecasting institutional outcomes, and published wording
  must not imply otherwise.
- Any data source with redistribution restrictions.
- Claims of novelty. Deposit betas are well documented in the literature. The contribution
  is reproduction from primary filings at coverage, with an out-of-sample design and a
  measured error rate against regulatory data.

---

## 2. Cycle definitions

| Cycle | Window | Move | Duration |
|---|---|---|---|
| Calibration | 2015Q4 – 2019Q2 | ~0.25% to ~2.50% | ~36 months |
| Trough | 2020Q2 – 2022Q1 | ~0.25% | — |
| Test | 2022Q1 – 2023Q4 | ~0.25% to ~5.33% | ~16 months |

Windows are derived from the FRED federal funds series into a `dim_rate_cycle` table
rather than hardcoded, so the boundary logic is inspectable and adjustable.

The cycles differ materially in pace and magnitude. Deposit betas are expected to run
higher in faster, larger cycles, so **absolute beta levels are not expected to transfer
between cycles and the project does not claim they will**. The hypothesis concerns
relative ordering: whether a bank that repriced faster than its peers in the calibration
cycle also repriced faster than its peers in the test cycle.

---

## 3. Metric definition

### 3.1 Comparability tiers

Different filers make different concepts available. Forcing every filer into one formula
destroys comparability silently. Cost of deposits is therefore computed at the most
precise tier each filer-quarter supports, and the tier is recorded on the row.

| Tier | Numerator | Denominator |
|---|---|---|
| 1 | Interest expense on deposits | Average interest-bearing deposits |
| 2 | Interest expense on deposits | Average total deposits |
| 3 | Interest expense on deposits, reconstructed from components | Average total deposits |
| X | — | Excluded as insufficiently comparable |

Rules:

- `metric_tier` is a column on the fact table, not a processing detail.
- Headline results are computed on tier 1 alone, then re-run including tier 2 as a
  robustness check. Both are reported.
- Cross-tier comparisons are never made without the tier being shown.
- A series whose tier changes mid-cycle is flagged and reported separately.
- Where average balances are not tagged, a two-point average of period-end balances is
  used and the row carries `avg_method = 'endpoint'` rather than `'reported'`.
- Coverage by tier and year is published on the data health page.

### 3.2 Deposit beta

Cumulative over each cycle rather than differenced quarter on quarter, which is the market
convention and materially more stable:

```
cumulative_beta = Δ cost_of_deposits (cycle start → cycle peak)
                ÷ Δ effective federal funds rate (same window)
```

### 3.3 Net interest margin

Computed where available, reported as secondary and explicitly caveated. Its denominator,
average earning assets, is inconsistently tagged and materially less reliable than cost of
deposits. It appears as context on bank pages and never as a headline result.

---

## 4. Data problems handled explicitly

Each item below is a section of `docs/methodology.md` and carries a corresponding test.

**Survivorship bias.** Failed banks stop filing. A pipeline that drops them understates
the effect being measured. Terminal filers are retained with `last_filed_period` and an
exit reason; every headline result is reported for the full sample and for surviving banks
only, and the difference is published.

**Partial-cycle coverage.** Terminal filers have filings through approximately fiscal 2022
but not through the mid-2023 cycle peak. Their cumulative beta is computed to the last
filed quarter, marked `partial_cycle`, and excluded from any calculation requiring a
complete cycle rather than silently truncated into it.

**Entity continuity.** Mergers create step-changes that resemble repricing behaviour. A
`bank_entity_events` table records mergers, acquisitions, CIK changes and failures;
affected bank-quarters are flagged and banks with a material mid-cycle acquisition are
shown separately in rankings.

**Fourth-quarter derivation.** Most filers do not file a fourth 10-Q, so Q4 flow items are
derived as fiscal year less the first three quarters. Derived rows carry `q4_derived` and
are tested for non-negativity and plausibility against neighbouring quarters.

**Tag drift and restatements.** The taxonomy changes annually and filers change which
concepts they use. The company facts endpoint returns multiple values for the same period
from original and amended filings. Precedence: the most recently filed value wins for the
analytical panel. Superseded values are retained in a separate table so restatement
magnitude can be measured, which is the input to the secondary question.

---

## 5. Independent validation

FFIEC Call Report and FDIC BankFind data carry the same deposit and interest-expense
concepts in standardised form, quarterly, for all insured institutions including those
that later failed. They are used as ground truth, not as the primary source: derived
cost-of-deposits values are compared against the regulatory figure and the agreement is
published as a measured error rate.

The mapping is not one-to-one. FDIC data is at insured-institution level (CERT) while SEC
filings are at holding-company level (CIK), and a holding company may own several insured
banks. Validation is therefore restricted to single-bank holding companies, or CERTs are
aggregated to the holding company with the residual mismatch stated. FR Y-9C is the
holding-company-level alternative if the mapping proves too lossy.

---

## 6. Analysis

Results are reported in this order of prominence:

1. Spearman rank correlation between calibration-cycle and test-cycle betas. This is the
   headline figure: it answers the question directly and is robust to the level shift
   between cycles.
2. Quartile transition matrix between cycles.
3. Pearson correlation and OLS with R², explicitly secondary.
4. Material deviators, with a stated hypothesis for each.
5. Descriptive characteristics of high-beta banks — funding mix, deposit composition,
   size. Descriptive, not causal.
6. Error attribution: how much cross-bank dispersion is plausibly reporting difference
   rather than behaviour, using section 5.
7. Survivorship sensitivity on every headline figure.

The project does not optimise for R². If persistence is weak, that is the finding and it
is published as such.

---

## 7. Architecture

```
SEC EDGAR (company facts, submissions)     FRED (FEDFUNDS, DGS2, DGS10)
                         │                          │
                         └────────────┬─────────────┘
                                      │
                          Python ingestion
                    rate limiting, caching, retry,
                         schema validation
                                      │
                              DuckDB (local)
                                      │
                                    dbt
                    staging → intermediate → marts
                                      │
                    ┌─────────────────┴─────────────────┐
              Evidence.dev site              FFIEC/FDIC validation
```

Orchestration is GitHub Actions on a weekly schedule. Filings are quarterly, so weekly
refresh is sufficient and no additional scheduler is warranted at this scale.

### 7.1 Model layout

```
staging/
  stg_sec__company_facts
  stg_sec__submissions
  stg_sec__tickers
  stg_fred__series

intermediate/
  int_bank_universe
  int_fact_precedence
  int_deposit_expense_harmonised
  int_deposit_balance_harmonised
  int_bank_quarter_panel
  int_rate_cycles
  int_deposit_cost
  int_filing_timeliness

marts/
  dim_bank
  dim_date
  dim_rate_cycle
  bank_entity_events
  fct_bank_quarter
  fct_deposit_beta
  mart_bank_overview
  mart_cross_bank_comparison
  mart_filing_behaviour
  mart_data_quality
```

Sources carry freshness checks. A snapshot on the raw fact table captures restatements
over time. Macros cover tag-fallback resolution and cycle-window logic. Generated dbt
documentation is published alongside the site.

### 7.2 Tests

Standard `unique`, `not_null`, `relationships` and `accepted_values` on all keys and
dimensions, plus:

- no duplicate bank-quarter in `fct_bank_quarter`
- `metric_tier` within the defined set
- `cost_of_deposits` within 0 to 8 percent annualised; breaches warn rather than null
- `deposits > 0` wherever deposit interest expense is non-null
- derived Q4 values non-negative and within band of neighbouring quarters
- at least 80 percent quarterly coverage for any bank in a headline result
- terminal filers present in the fact table, as a regression test against reintroducing
  survivorship bias
- row-count and tier-coverage change detection between runs

---

## 8. Presentation

Seven pages:

1. **Overview** — the finding, the survivorship comparison, and an explicit statement of
   what is and is not claimed.
2. **Bank explorer** — cost of deposits against federal funds, beta by cycle, metric tier
   and coverage, filing history, supporting fundamentals.
3. **Cross-bank comparison** — rankings, distributions, cycle-on-cycle scatter, quartile
   transitions.
4. **Deposit beta persistence** — full case study.
5. **Filing behaviour** — secondary case study.
6. **Data health** — pipeline status, test results, coverage, freshness.
7. **Methodology** — harmonisation, approximations, exclusions, validation error rates.

Built with Evidence.dev, deployed as a static site at no running cost.

---

## 9. Milestones

| # | Deliverable | Exit condition |
|---|---|---|
| 0 | Feasibility profiling on the twelve-bank sample | Gate criteria in 9.1 all pass |
| 1 | Hardened ingestion, DuckDB load, staging models | Full universe ingests reproducibly |
| 2 | Harmonisation, bank-quarter panel, restatement precedence, entity events, beta | `fct_deposit_beta` populated with tiers |
| 3 | Cycles, rank persistence, survivorship sensitivity, regulatory validation | Headline figure exists and is defensible |
| 4 | Site: overview, bank explorer, comparison, primary case study | Deploys publicly |
| 5 | Filing behaviour case study, data health page, dbt tests and docs | Tests green, coverage published |
| 6 | Methodology, README, scheduled refresh | Unattended refresh runs green |

### 9.1 Feasibility gate

Proceed past Milestone 0 only if all hold across the twelve-bank sample:

- **G1** At least nine banks yield a tier 1 or tier 2 cost-of-deposits series for at least
  80 percent of quarters in 2015Q4–2019Q2.
- **G2** The same holds for at least 80 percent of quarters in 2022Q1–2023Q4.
- **G3** Both terminal filers are retrievable through their final filed quarter.
- **G4** Ally Financial's test-cycle cost of deposits exceeds Zions Bancorporation's by a
  material and economically sensible margin. A direct bank with no branch network should
  reprice faster than a branch-funded regional. If this contrast is absent, the metric
  construction is wrong and work stops until it is corrected.
- **G5** Q4 values are derivable for at least 80 percent of bank-years.

### 9.2 Fallbacks

In order of preference, if the gate fails:

1. Broaden the metric to total interest expense over average interest-bearing liabilities.
   Less precise, more consistently tagged, still economically meaningful.
2. Shorten the calibration window to 2016Q1–2019Q2 if early coverage is the binding
   constraint.
3. Move the primary metric source to FFIEC Call Report data and reposition XBRL as a
   comparison exercise. This preserves the question but changes the engineering emphasis,
   so it is a last resort.

Whichever path is taken, the decision and its supporting evidence are recorded in
`docs/decisions.md`.

---

## 10. Deferred

Snowflake rebuild with marts materialised down for serving · broader company coverage and
comparator · Power BI layer distributed as a `.pbix` with screenshots and a recorded
walkthrough rather than hosted live · market risk analytics, which is the point at which a
paid data licence first becomes necessary · anomaly detection, capped at a z-score
baseline and one isolation forest with honest evaluation · a custom frontend, only if
Evidence.dev demonstrably constrains a feature users need.

---

## Revision history

| Date | Change |
|---|---|
| 2026-09-02 | Version 1.0. Initial specification. |
