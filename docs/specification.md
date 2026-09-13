# Specification

Version 1.0 · 2 September 2026

---

## 1. Scope

MarketScope measures deposit repricing behaviour across US bank holding companies using
primary SEC EDGAR filings and Federal Reserve data, and tests whether that behaviour is
persistent across monetary-tightening cycles.

The initial release covers the largest 50 US bank holding companies by total assets.
Institutions that have since failed or been acquired are retained.

Membership is decided by what a filer reports rather than by its SIC code, under four rules
answerable from EDGAR alone:

| Rule | Test |
|---|---|
| Rankable | Reports `Assets` in at least one quarter-end of the study window |
| Deposit funded | `Deposits` reach 5 percent of assets in at least one period |
| Deposit taking | Reports interest paid on deposits under any candidate concept |
| Domestic registrant | Files a 10-K, not a 20-F or 40-F, covering fiscal 2015 or later |

Filers are then ranked on the highest total assets reported across 2015Q4–2023Q4, rather
than on a current snapshot, so an institution that stopped filing inside the window is
ranked on what it was rather than dropped.

SIC codes 6020, 6021, 6022, 6035 and 6036 are recorded as a descriptive attribute and no
longer decide membership. Screening on them loses 8 of the largest 50 deposit-taking
filers, including Goldman Sachs, Morgan Stanley and Charles Schwab under broker-dealer
codes and American Express, Discover and Synchrony under consumer finance codes. SIC 6020
is a group heading for which EDGAR holds no entities at all. See decision 0015.

Deposit funding alone does not identify a deposit-taking institution: an insurer tags
annuity and other deposit-type contracts under the same `Deposits` concept a bank uses for
its funding base, so the interest test is required alongside it. The 5 percent threshold is
not load-bearing — above $20bn of assets the largest non-depository ratio is 0.024 and the
smallest depository ratio is 0.210.

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

| Tier | Numerator | Denominator | Sample availability |
|---|---|---|---|
| 1 | Interest expense on deposits | Interest-bearing deposits | 11 of 12 banks, 708 bank-quarters |
| 2 | Interest expense on deposits | Total deposits | 3 bank-quarters |
| 3 | Interest expense on deposits, reconstructed from components | Best available base | 181 bank-quarters |
| X | Reconstruction failed completeness check | — | 71 bank-quarters |

Counts are across the 51-filer universe, 3,066 bank-quarters in total. Tier 1 covers 75.8
percent and 43 filers; 37 filers carry headline coverage in both cycles and can support the
persistence test.

Reconstruction resolves deposit expense by mutually exclusive category — time deposits;
savings, money market and NOW; interest-bearing demand; other domestic; foreign. Within a
category the filer's own total is used where it publishes one and the leaf concepts present
are summed otherwise, never both, because several filers tag a combined concept alongside
its parts and adding them would double count. See decision 0021.

The denominator is interest-bearing deposits wherever it can be resolved. Non-interest-bearing
deposits have a beta of zero by construction, so including them scales a bank's measured beta
by its interest-bearing share — a share that varies with business model and moved sharply
during 2022 and 2023. Total deposits is therefore not comparable across banks and is used only
where no interest-bearing base can be resolved at all.

Three routes reach that base, in order of directness, each recorded on the row:

| Provenance | Route | Filers |
|---|---|---|
| `reported` | `InterestBearingDepositLiabilities` | 8 |
| `summed_components` | Domestic plus foreign components | JPMorgan, Citigroup |
| `derived_residual` | Total deposits less non-interest-bearing deposits | Zions |

The residual route requires a *complete* non-interest-bearing figure. A partial one, such as a
domestic component with no foreign counterpart, would understate what is subtracted and
silently overstate the base, so it is refused rather than approximated.

All denominators are two-point averages of period-end balances. Milestone 0 established
that no filer in the sample tags an average deposit balance in any taxonomy, including its
own extension namespace, so reported averages are not available and every row carries
`avg_method = 'endpoint'`. The distinction the field was intended to record does not arise
in practice; it is retained because a filer may begin tagging averages later.

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
cost_of_deposits = quarterly deposit interest expense × 4
                 ÷ average interest-bearing deposits for the quarter

cumulative_beta  = Δ cost_of_deposits (cycle start → cycle peak)
                 ÷ Δ effective federal funds rate (same window)
```

Annualisation is by simple multiplication rather than compounding, and the policy rate is
converted to a decimal fraction to match, following the convention used in Federal Reserve
work on FR Y-9C filings.

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

A stronger form of the same problem applies before ingestion begins. A bank with no
registered securities files its periodic reports with its primary federal banking regulator
rather than the SEC, so it has no 10-K and no XBRL facts in EDGAR at all. First Republic
Bank and Signature Bank are both absent for this reason, and both are institutions where
the effect under study was most acute.

The size of that gap is measured, not assumed. Against a ranking of the largest 50 US
depository groups built from FDIC data rather than from EDGAR, 40 are reachable in EDGAR —
38 through a top-tier registrant and 2, HSBC and Santander, through a US intermediate
holding company filing a 10-K against registered debt. Of the 10 that are not:

| Cause | Count | Institutions |
|---|---|---|
| No registered securities | 3 | First Republic ($213bn), USAA ($113bn), Signature ($110bn) |
| Foreign banking organisation | 7 | Toronto-Dominion ($423bn), Bank of Montreal, UBS, Royal Bank of Canada, BNP Paribas, Bank of China, Standard Chartered |

The driver is registered securities, not corporate structure: Zions Bancorporation
dissolved its holding company in 2018, files as the bank itself, and is fully covered. The
7 foreign banking organisations are a scope boundary rather than a coverage failure — they
are not US bank holding companies and file FR Y-9C rather than 10-K — and are not
recovered. The 3 without registered securities are recovered from regulatory data at
Milestone 3. Both counts are published on the data health page. See decision 0016.

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
that later failed. They serve two purposes.

As **ground truth**, derived cost-of-deposits values are compared against the regulatory
figure and the agreement is published as a measured error rate, so the accuracy of the tag
mapping is stated rather than asserted.

As a **coverage source**, they supply the institutions EDGAR does not hold at all. This is
not optional: without regulatory data, First Republic and Signature are simply missing, and
the survivorship comparison loses the two most consequential cases. Section 4 measures that
gap at 3 of the largest 50, which is small enough that this work stays at Milestone 3 and
Milestone 1 proceeds on EDGAR alone.

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
| 0 | Feasibility profiling on the twelve-bank sample | Gate criteria in 9.1 all pass. **Passed** |
| 1 | Hardened ingestion, DuckDB load, staging models | Full universe ingests reproducibly. **Passed:** 51 members, 1.81m facts, four staging models, 21 tests green |
| 2 | Harmonisation, bank-quarter panel, restatement precedence, entity events, beta | `fct_deposit_beta` populated with tiers |
| 3 | Cycles, rank persistence, survivorship sensitivity, regulatory validation | Headline figure exists and is defensible |
| 4 | Site: overview, bank explorer, comparison, primary case study | Deploys publicly |
| 5 | Filing behaviour case study, data health page, dbt tests and docs | Tests green, coverage published |
| 6 | Methodology, README, scheduled refresh | Unattended refresh runs green |

### 9.1 Feasibility gate

Proceed past Milestone 0 only if all hold across the twelve-bank sample:

- **G1** At least nine banks yield a tier 1 or tier 2 cost-of-deposits series for at least
  80 percent of quarters in 2015Q4–2019Q2. **Passed: 12 of 12.**
- **G2** The same holds for at least 80 percent of quarters in 2022Q1–2023Q4. **Passed: 11
  of 12.** The exception is SVB, whose filings end in 2022Q4 — a partial cycle by
  construction, handled under section 4 rather than a coverage defect.
- **G3** Every terminal filer is retrievable through its final filed quarter. **Passed:**
  SVB to 2022-12-31, PacWest to 2023-09-30.
- **G4** Ally Financial's test-cycle cost of deposits exceeds Zions Bancorporation's by a
  material and economically sensible margin. **Failed: +0.085 against a 0.10 threshold.**
  The contrast is present and correctly signed but below the margin set in advance. The
  premise that a branch-funded regional is a slow repricer does not hold for the test cycle:
  Zions carries the second-highest non-interest-bearing deposit share in the universe at 44.6
  percent and still reprices mid-pack at 0.612. See decisions 0019 and 0022.
- **G4′** Replacing G4 for construct validity: across the universe, a bank's
  non-interest-bearing deposit share correlates negatively with its cumulative deposit beta,
  since balances that pay nothing by construction cannot reprice. **Passed:** Spearman −0.358
  across 30 filers with a plausible headline-tier beta, −0.409 across all 32. Predicted
  negative before measurement.
- **G5** Q4 values are derivable for at least 80 percent of bank-years. **Passed: 92.3
  percent** on interest expense on deposits, 180 of 195 bank-years.
- **Benchmark** The industry cumulative interest-bearing deposit beta computed here must
  land near the published Federal Reserve figure of roughly 0.40 for both cycles, which
  tests units, averaging and tag mapping together. **Passed:** 0.354 calibration, 0.480
  test.

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
| 2026-09-13 | G4 recorded as failed and replaced by a cross-sectional construct-validity criterion. Deposit expense and non-deposit funding concept lists completed against the full universe and resolved by mutually exclusive category; tier X falls from 184 bank-quarters to 71. |
| 2026-09-09 | Milestone 1 closed: committed universe seed, DuckDB load of 51 filers, dbt staging models. Pinned filers seated alongside the ranked fifty, taking the universe to 51. |
| 2026-09-09 | Universe membership moved from SIC codes to four reported-behaviour rules; SIC retained as descriptive. EDGAR coverage gap measured against an FDIC-derived ranking at 3 of 50 for want of registered securities and 7 of 50 for foreign banking organisations. Regulatory ingestion confirmed at Milestone 3. |
| 2026-09-02 | Version 1.0. Initial specification. |
| 2026-09-08 | G4 and benchmark passed; Milestone 0 gate closed. Denominator fixed as interest-bearing deposits with three resolution routes. Completeness check added for reconstructed numerators, excluding 31 M&T bank-quarters. Annualisation convention recorded. |
| 2026-09-04 | Milestone 0 results. Tier denominators restated as endpoint averages, since no filer tags average deposit balances. Tier availability recorded. Survivorship section extended to banks absent from EDGAR entirely. Regulatory data promoted from validation to coverage source. Gate criteria annotated with outcomes; G4 remains open. |
