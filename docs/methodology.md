# Methodology

How MarketScope turns SEC filings and the federal funds rate into a cumulative deposit beta
for each bank and cycle, what each step assumes, and where the result is known to be weak.

The specification says what is measured and the decision record says why each choice was
made. This document says how, in enough detail to reproduce every figure from a clean
checkout. Decisions are cited by number, for example (0021), and specification sections as
"specification 3.1".

**State at writing, 1 October 2026: Milestone 2 in progress.** Everything up to
`fct_deposit_beta` is built and tested. The restatement table, the entity events table,
the survivorship comparison and the regulatory validation are not. Each section says which
parts are in force and which are still to be built. A planned control is never written up
as a working one.

---

## 1. Sources

| Source | Endpoint | Used for |
|---|---|---|
| SEC EDGAR | XBRL company facts, `data.sec.gov/api/xbrl/companyfacts` | Every financial value |
| SEC EDGAR | Submissions, `data.sec.gov/submissions`, including older-filing pages | Registrant name, filing history, form types |
| SEC EDGAR | XBRL frames, `data.sec.gov/api/xbrl/frames` | Universe ranking only |
| FRED | `FEDFUNDS`, monthly effective federal funds rate | Cycle windows and the policy move in every beta |
| FRED | `DGS2`, `DGS10` | Context on bank pages; not used in any result |
| FDIC BankFind | Institution financials at 2022-12-31 | Sizing the EDGAR coverage gap only (0016) |

All of these are public and free to redistribute. Nothing licensed is used (specification
1.2).

### 1.1 Ingestion

`python -m marketscope.pipeline` reads the committed universe from
`data/seeds/universe.csv` and loads four raw tables into `data/marketscope.duckdb`:
`raw.sec_facts`, `raw.sec_filings`, `raw.sec_registrants` and `raw.fred_observations`.

- **Rate limit.** SEC requests are held to 8 a second by default and can never be
  configured above 10, the SEC's published ceiling. The User-Agent must contain contact
  details or configuration fails at startup.
- **Retries.** Transport errors and status 429 and 5xx responses are retried up to four
  times, with backoff that doubles each time up to a 30-second cap. A filer that still
  fails is skipped and recorded, the other filers load, and the run exits non-zero. Because
  each run fully replaces the raw tables (below), a run that exits non-zero has loaded
  without that filer. It must be rerun before anything is built on it.
- **Cache.** JSON responses are cached on disk under `data/cache`, keyed by URL, for 24
  hours.
- **Units.** Only USD facts are loaded. Share counts, ratios and per-share figures are most
  of each payload and nothing downstream reads them.
- **Taxonomies.** Facts are loaded from every taxonomy present, including each filer's own
  extension namespace. Section 3.3 explains why the metric then reads `us-gaap` alone.
- **Full replace.** Every run replaces the raw tables inside one transaction rather than
  merging into them. The company facts endpoint republishes a filer's whole history when a
  value is revised, so an upsert would leave the superseded value in place looking current.
  One transaction covers facts, filings and registrants. If the load raises partway, the
  transaction rolls back and the previous load remains. Facts, filings and registrants
  always describe the same set of filers.
- **FRED missing values.** FRED marks a missing observation with `.`. The client turns it
  into a null and staging drops it, so it cannot reach an average as a zero.

**Filer identity.** The registrant name comes from the submissions endpoint and never from
`entityName` on the company facts payload. That field names whichever entity published a
fact: CIK 70858, Bank of America, reports `BofA Finance LLC` there (0009). No step keys on
it.

The current load holds 1,809,702 facts for 51 filers.

---

## 2. Universe

### 2.1 Membership rules

The universe is decided by what a filer reports. SIC code plays no part (0015).
Specification section 1 lists the four rules: the filer reports total assets; deposits
reach 5 percent of assets in some period; it reports interest paid on deposits under any
candidate concept; and it files a 10-K. Filers that pass are ranked on their highest
reported total assets across 2015Q4 to 2023Q4, so a bank that shrank or stopped filing is
ranked on its peak size and stays in.

Two of the rules exist because the obvious alternatives fail on real data:

- **Deposit funding alone admits insurers.** Insurers tag annuity deposit-type contracts
  under the same `Deposits` concept banks use, which is how Fidelity National Financial
  entered the ranking before the interest test was added. The 5 percent threshold carries
  no weight. Above $20bn of assets, the highest ratio among non-depositories is 0.024 and the
  lowest among depositories is 0.210, so any cut between them selects the same set.
- **SIC codes miss banks.** A bank-SIC screen loses 8 of the largest 50 deposit-taking
  filers, including Goldman Sachs, Morgan Stanley and Charles Schwab. SIC 6020 is a group
  heading under which EDGAR holds no entities at all.

The membership test reads the whole list of deposit-interest concepts, not just the
aggregate. M&T, Flagstar and Valley National tag only the component categories.

### 2.2 Pinned filers and the committed seed

PacWest Bancorp is pinned by CIK. It peaked at $41bn and ranks 58th, so it never qualifies
on size. It is in the universe as a terminal filer that spans both cycles and exited by
merger (0010). Pinned filers are added to the ranked fifty rather than displacing the
fiftieth, which makes the universe 51 (0017). A pinned CIK that fails the membership rules
raises an error instead of being seated anyway.

The resolved universe is committed as a seed, and ingestion reads the seed rather than
rebuilding the universe (0018). The fiftieth place is decided by a $50bn cut with banks a few
hundred million dollars apart around it, so a single restated total-assets figure can
reorder it. Rebuilding is a deliberate step: `build_universe.py --check` fails if a fresh
build has drifted from the seed, and `--write-seed` adopts the new build.

### 2.3 What EDGAR cannot reach

A universe built from EDGAR cannot see a bank that files nothing there, so the gap was
measured against an outside source (0016). Depository groups were ranked by rolling FDIC
insured-institution assets at 2022-12-31 up to their regulatory high holder. The largest
fifty were then mapped to SEC registrants through a pinned, hand-verified table. An earlier
attempt matched on names: it mapped First Republic Bank onto Republic First Bancorp and
would have reported no gap at all.

The result: 40 of the 50 are in EDGAR. Of the 10 that are not, 3 have no registered
securities (First Republic, USAA, Signature) and 7 are US operations of foreign banking
organisations. The 7 are outside the project's scope; they are not US bank holding
companies. The 3 are a coverage failure, and they are to be recovered from regulatory data
at Milestone 3. Reproduce with `python analysis/universe/reference_audit.py`.

---

## 3. From facts to a bank-quarter panel

`marketscope.panel.quarterly_panel` reduces one filer's facts to the metric's inputs, keyed
by quarter end. The panel is built from a fixed set of concepts, `PANEL_TAGS`.

### 3.1 Period classification

A fact's period is classified by the number of days it spans, never by its fiscal-period
label. The label describes the filing a fact appeared in, not the period the fact covers: a
third-quarter 10-Q carries year-to-date figures under the same `Q3` label as the quarter's
own figures.

| Span in days | Periodicity |
|---|---|
| none (instant) | instant |
| 80–100 | quarterly |
| 170–190 | semiannual |
| 260–290 | nine-month |
| 350–380 | annual |

Balances are read from instants and expenses from quarterly durations. A balance reported
as a duration is ignored.

### 3.2 Restatement precedence

Within each concept, the most recently filed value for a period wins, where a period is the
concept, unit, start date and end date. When two values were filed on the same date, the
higher accession number wins. Precedence is applied concept by concept before the panel is
assembled, so a revised figure replaces the original instead of both reaching the panel.

Staging deliberately keeps every value. The superseded ones are the input to the secondary
question, so they are dropped in one place, inside the panel. Section 8.5 covers what is
not yet built.

### 3.3 Taxonomy pin

The panel reads `us-gaap` only. A filer can declare a concept in its own extension
namespace under a name the standard taxonomy also uses, and the two are not the same
concept. Reading every namespace is only for profiling, and the Milestone 0 search for
tagged average balances is the one place it was used (0011).

### 3.4 Fourth-quarter derivation

Most banks file a 10-K instead of a fourth 10-Q, so a fourth-quarter flow exists only as
the fiscal year minus the first nine months. For each annual fact,
`derive_fourth_quarter` subtracts:

1. the nine-month year-to-date figure with the same start date, where one is published; or
   otherwise
2. the sum of three quarterly facts that tile the year from its start date without a gap.

If neither is available, no fourth quarter is derived. A year with a missing quarter is
never filled by assumption. Balances need no derivation, because a 10-K reports the
year-end instant directly.

Section 8.4 records where this fails.

---

## 4. Cost of deposits

`marketscope.metrics.resolve_deposit_cost` resolves each bank-quarter. In the warehouse it
runs inside `int_deposit_cost`, a dbt Python model that calls the same library the analysis
scripts use, so the metric has one implementation (0024). Run against the current
warehouse, the model reproduces the tier coverage script exactly.

```
cost_of_deposits = quarterly deposit interest expense × 4
                 ÷ average deposit base for the quarter
```

The quarterly figure is annualised by simple multiplication, not compounding, following
Federal Reserve work on FR Y-9C filings.

### 4.1 Numerator

1. `InterestExpenseDeposits` where the filer reports it. Provenance `reported`.
2. Otherwise a reconstruction from five categories that do not overlap: time deposits;
   savings, money market and NOW; interest-bearing demand; other domestic; and foreign.
   Within each category the filer's own category total is used if it publishes one, and
   the leaf concepts present are summed if it does not. Totals and leaves are never added
   together, because several filers tag both and the sum would double count (0021).
   Provenance `summed_components`.

### 4.2 Denominator

The base is interest-bearing deposits wherever it can be resolved (0012). Non-interest-bearing
deposits pay nothing by construction, so including them scales each bank's beta by its
interest-bearing share. That share differs by business model, and it moved sharply in 2022
and 2023. The interest-bearing base is reached by three routes, tried in order:

| Provenance | Route | Bank-quarters |
|---|---|---|
| `reported` | `InterestBearingDepositLiabilities` | 2,244 |
| `summed_components` | Domestic plus foreign, only when both are present | 445 |
| `derived_residual` | Total deposits less a complete non-interest-bearing figure | 377 |

These counts include the tier 2 rows. On those, `reported` means total deposits as
reported.

The residual route refuses a partial non-interest-bearing figure, such as a domestic
component with no foreign one. Subtracting too little would overstate the base without any
sign. The route also refuses a residual that is zero or negative. Total deposits is used
only when no interest-bearing route resolves.

### 4.3 Tiers

| Tier | Numerator | Denominator | Bank-quarters | Share |
|---|---|---|---|---|
| 1 | Reported | Interest-bearing deposits | 2,323 | 75.8% |
| 2 | Reported | Total deposits | 491 | 16.0% |
| 3 | Reconstructed | Best available base | 181 | 5.9% |
| X | Reconstruction failed the completeness check | — | 71 | 2.3% |

These are 3,066 bank-quarters across 51 filers. Tier 1 is the most precise route a filer
reaches for 43 filers, tier 2 for 5 and tier 3 for 3. Headline results run on tier 1 and
are repeated with tier 2 included as a robustness check (0004). Tiers 3 and X never enter a
headline figure.

A bank-quarter with no numerator or no base gets no row at all. That keeps it
distinguishable from one that was resolved and then excluded at tier X.

### 4.4 Completeness check on reconstructed numerators

A sum of the components a filer happened to tag can be badly short. At 2023Q3, M&T tagged
only time-deposit expense, $202m of roughly $696m. The resulting test-cycle beta of 0.095
was indistinguishable from a genuinely slow repricer (0013).

Every reconstruction is therefore checked against implied deposit expense: total interest
expense minus all identifiable non-deposit funding costs, from the twenty concepts in
`NON_DEPOSIT_FUNDING_TAGS`. If the reconstruction covers less than 80 percent of the implied
figure, the quarter is tier X and the ratio is kept on the row as `component_coverage`. If
the filer reports no total interest expense, no check is possible. The reconstruction is
then accepted with `component_coverage` null, which is visible on the row.

The implied figure is used only as a check. It was tested as a numerator and failed: it
matches reported deposit expense within 2 percent in only 48.8 percent of 2,524
bank-quarters, and its 90th percentile is 1.9 times the reported figure (0021). The
threshold was not lowered to rescue filers (0020, 0021). The non-deposit funding list and
the deposit component list were extended to the concepts the full universe uses instead.
That took tier X from 184 bank-quarters to 71.

Tier X by filer: Flagstar 32 quarters, M&T 31, First Horizon 3, E*TRADE 3, Zions 2.

### 4.5 Averaging

No filer tags an average deposit balance in any taxonomy, its own extension included
(0011). Average balances appear only in untagged MD&A tables. Every denominator is
therefore the mean of the opening and closing period-end balances, with
`avg_method = 'endpoint'`.

- The opening balance is the previous quarter end resolved through the same base as the
  closing balance. Averaging an interest-bearing close against a total-deposit open would
  produce a figure that is neither.
- Where the previous quarter cannot be resolved on that base, the closing balance is used
  alone and the row carries `avg_method = 'closing_only'`. There are 179 such rows.
- Endpoint averaging errs most when balances move sharply within a quarter, which is
  exactly the condition under study in 2023. The error is to be measured against
  regulatory true averages at Milestone 3 and has not been measured yet.

For a time this averaging was not actually happening. Until Milestone 2,
`previous_quarter_end` returned its own argument, so every "average" averaged the closing
balance with itself while the row claimed `endpoint`. The industry benchmark could not
catch this, because it never called the averaging path (0019). The fix moved every beta by
less than 0.015 and turned gate criterion G4 from a pass into a failure (section 7.2).

---

## 5. Cycle windows

Windows are derived from `FEDFUNDS` in `dim_rate_cycle`, never hardcoded (specification
section 2).

1. `int_rate_cycles` averages the monthly effective rate to quarters. A quarter is a trough
   or a peak if it is the minimum or maximum of a centred window of four quarters either
   side. The window is level-based because a rule based on quarterly changes splits the
   paused 2015–2019 cycle into three.
2. A peak qualifies if it is more than 1 percentage point above the series minimum.
3. The cycle starts at the **last** quarter within 0.15 points of the lowest rate since the
   previous peak. Taking the first would start the 2022 cycle in 2020 and spread the move
   over eight quarters in which the rate did not move. The 0.15 tolerance absorbs drift in
   a rate administered within a target range.
4. Cycles are named by recency: the latest is `test` and the one before is `calibration`.
   Earlier cycles stay in the table unnamed, as context.

| Cycle | Window | Quarters | Rate (quarterly average) |
|---|---|---|---|
| Calibration | 2015Q4 – 2019Q1 | 14 | 0.16% → 2.40% |
| Test | 2022Q1 – 2023Q4 | 8 | 0.12% → 5.33% |

The calibration cycle ends in 2019Q1, not the 2019Q2 the specification first pinned,
because the quarterly average peaks at 2.403 percent in 2019Q1. The test cycle ends at the
first quarter of a plateau that runs to 2024Q2.

Analysis scripts read the windows from the warehouse through `marketscope.cycles`, which
raises if either cycle is missing, duplicated or unknown. Only the Milestone 0 scripts keep
their own windows, because they are the record of what the gate measured (0023).

**Sensitivity.** Before the windows were adopted, each boundary was moved one quarter in
each direction and compared with the derived window by within-cycle Spearman rank
correlation (`analysis/milestone2/cycle_sensitivity.py`). The cross-cycle persistence
result was not computed under any alternative, so no window could be chosen by its effect
on the headline.

| Boundary moved | ρ, all filers | ρ, plausible betas |
|---|---|---|
| Calibration start ±1 | 0.976, 0.997 | 0.996, 0.997 |
| Calibration end −1, +1 | 0.892, 0.960 | 0.884, 0.957 |
| Test start ±1 | 0.992, 0.994 | 0.990, 0.993 |
| Test end −1, +1 | 0.876, 0.878 | 0.984, 0.979 |

The test-end drop across all filers comes from one filer, BNY Mellon, whose derived 2023Q4
cost of deposits is negative (section 8.4).

Two of the four cycle endpoints, the calibration start (2015Q4) and the test end (2023Q4),
are fourth quarters. Their flows are therefore derived. That follows from when the rate
turned rather than from any choice, but those endpoints carry whatever error the
derivation carries.

---

## 6. Deposit beta

```
deposit_beta = (cost at measured end − cost at cycle start)
             ÷ (policy rate at measured end − policy rate at cycle start)
```

The beta is cumulative over the cycle rather than built from quarterly differences, and it
is taken between two endpoints, not fitted across the quarters in between. Both rates are
quarterly averages from `int_rate_cycles` expressed as decimal fractions. The cycle windows
come from the same view, so a beta's policy move and its window cannot come from two
different treatments of the series.

`fct_deposit_beta` holds one row per universe member per study cycle: 102 rows. Members
with no beta keep their row, and a dbt test fails if any member is missing a row in either
cycle.

- **Tier.** Each endpoint's tier is recorded, and `metric_tier` is the less precise of the
  two. It is null if either endpoint is missing, so a filter on tier cannot admit a row
  that has no beta. `tier_changes_in_cycle` flags a filer whose quarters within the cycle carry more than
  one tier: CIT, M&T and Flagstar in the calibration cycle.
- **Tier X.** No beta is computed from a tier X endpoint. Its numerator is known to be
  understated, and the beta would read as a slow repricer.
- **Missing endpoint.** If either endpoint has no row in `int_deposit_cost`, the beta is
  null.
- **Headline eligibility** is left to the analysis, not filtered in the table. The 80
  percent coverage floor and the tier rules are applied where a result is computed, and
  the coverage counts are carried on the row.

| Cycle | Rows | Betas | Partial cycle | Filers at or above 80% coverage |
|---|---|---|---|---|
| Calibration | 51 | 45 | 0 | 44 |
| Test | 51 | 44 | 2 | 41 |

37 filers have headline-tier coverage in both cycles and can support the persistence test.
The cross-cycle persistence correlation itself is Milestone 3 work and has not been
computed.

---

## 7. Validation completed so far

### 7.1 Industry benchmark

The aggregate is built the way the published figure is: expense and balances are summed
across the twelve-bank sample before dividing. The resulting industry cumulative
interest-bearing beta was required to fall within 0.15 of the Federal Reserve's roughly 0.40
in both cycles (0014). It passed at 0.354 for calibration and 0.480 for the test cycle.

The benchmark tests units, annualisation and tag mapping together. It does **not** test
the averaging method, as 0014 originally claimed, because it divides by summed closing
balances (0019). It also says nothing about dispersion across banks.

### 7.2 Gate criterion G4: failed

G4 required Ally Financial's test-cycle beta to exceed Zions Bancorporation's by at least
0.10. Once the averaging defect was fixed the margin was +0.085, and G4 is recorded as
failed (0022). The difference has the right sign. The premise was wrong: Zions holds the
second-highest non-interest-bearing share of any filer with a headline-tier beta and still
reprices mid-pack. G4 has not been rerun with a different comparator or threshold.

### 7.3 Construct validity

G4 was replaced by a cross-sectional test of the same hypothesis, with the prediction
fixed before measurement. A bank funded by more non-interest-bearing deposits has less of
its base to reprice, so its share should correlate negatively with test-cycle beta. Across
the 30 filers with a headline-tier beta, a reported deposit split and a beta of at most 1.0,
the Spearman correlation is −0.358. Across all 32, it is −0.409. Reproduce with
`python analysis/milestone2/construct_validity.py`.

This is the weaker half of validation. It shows the metric orders banks in an economically
sensible direction. It does not show that any individual bank's figure is accurate. That
is the regulatory comparison in section 9.

---

## 8. Data problems

Specification section 4 names five problems. Each one's handling and current state are
below.

### 8.1 Survivorship bias

**Handled.** Ranking on peak assets keeps banks that shrank or stopped filing: SVB is seated
19th on $212bn although it filed nothing after 2022Q4. PacWest is pinned (section 2.2).
Every member keeps a row in `fct_deposit_beta`, which a dbt test enforces.

**Not yet built.** The headline full-sample versus survivors-only comparison has not been
computed, because there is no headline result yet. `last_filed_period` and exit reason
exist only on the twelve-bank Milestone 0 sample in `marketscope.banks`. The warehouse
carries `pinned_reason` but has no exit-reason column for the universe.

**Unresolved and material.** First Republic and Signature, the two institutions where the
effect under study was most acute, are not in EDGAR at all (section 2.3). Until they are
recovered from regulatory data at Milestone 3, any survivorship comparison covers SVB and
PacWest only, and it will understate the effect.

### 8.2 Partial-cycle coverage

**Handled.** A filer whose last resolved quarter falls inside a cycle is measured to that
quarter and carries `partial_cycle`, with the actual end in `measured_end_quarter`. The
policy move is taken over the same shortened window. Two rows qualify, both in the test
cycle: SVB, measured to 2022Q4 (beta 0.627), and PacWest, measured to 2023Q3 (beta 0.724).

A filer that resolves later quarters but is missing the peak quarter itself is **not**
treated as partial. That gap is a coverage defect, and the filer gets no beta rather than a
beta at an earlier date.

**Limitation.** A partial-cycle beta is not comparable with full-cycle betas. Deposit
costs lag the policy rate, so a beta measured over the first three quarters of a cycle
understates where it would have ended. These rows must be excluded from any calculation
that needs a complete cycle. That exclusion will be applied in the Milestone 3 analysis and
is not yet tested anywhere.

### 8.3 Entity continuity

**Not yet built.** The `bank_entity_events` table does not exist, and no bank-quarter is
flagged for a merger. The twelve-bank sample records the relevant events as text: Truist
formed from BB&T and SunTrust (2019), PNC acquiring BBVA USA (2021), M&T acquiring People's
United (2022), U.S. Bancorp acquiring MUFG Union Bank (2022), JPMorgan acquiring First
Republic (2023). None is applied to any result.

**Consequence.** An acquisition within a cycle changes the deposit base between endpoints.
If the acquired deposits cost more or less than the acquirer's, the beta moves for a reason
that has nothing to do with repricing. Until the table exists, a beta for a filer that made
a material acquisition inside a cycle cannot be told apart from behaviour. In the test
cycle that includes JPMorgan and U.S. Bancorp at least. This is a Milestone 2 deliverable
and it is still outstanding.

### 8.4 Fourth-quarter derivation

**Handled.** Section 3.4.

**Not yet built.** Specification 7.2 requires derived fourth quarters to be non-negative
and within a band of neighbouring quarters. That test does not exist yet, because
`int_deposit_cost` does not carry a `q4_derived` flag: `quarterly_panel` discards the
`derived` marker when it collapses facts into the panel. As a result, no row in the
warehouse records whether its numerator was derived.

**Known failure.** BNY Mellon's derived fourth quarters are negative in 2023, 2024 and
2025: −0.57, −1.58 and −0.74 percent, against neighbouring quarters of roughly 3.5 percent.
The 2023Q4 value is the endpoint of its test-cycle beta, which comes out at −0.097. The
likely cause is a mismatch between the annual figure and the nine-month figure being
subtracted from it. It has not been diagnosed.

### 8.5 Tag drift and restatements

**Handled: tag drift.** The concept lists cover the alternatives each filer has used
across the window, and resolution is per quarter. A filer that switches from reporting
deposit expense directly to reporting components changes provenance and possibly tier at
that quarter, and the change is visible on the row. `tier_changes_in_cycle` flags it at
cycle level.

**Handled: precedence.** The most recent filing wins (section 3.2).

**Not yet built.** The superseded values are not kept in any table. Specification 7.1
plans a dbt snapshot on the raw fact table to record restatements over time, and it does
not exist. Within one load, `marketscope.facts.superseded` can recover which values a later
filing replaced, but nothing calls it. Restatement magnitude, the input to the secondary
question, is therefore not yet measurable. Because the raw tables are fully replaced on
each load (section 1.1), a value revised between two loads leaves no trace until the
snapshot exists.

---

## 9. Validation not yet done

The specification's accuracy claim rests on a comparison with FFIEC Call Report and FDIC
data (specification 5). None of that has started. Until it has, the following are
unknown:

- the error rate of the tag mapping for any individual bank;
- the size of the endpoint-averaging error, especially in 2023;
- how much of the dispersion across banks reflects reporting differences rather than
  behaviour.

The entity mismatch is already known: FDIC data is per insured bank and SEC data is per
holding company. Validation will be restricted to single-bank holding companies, or CERTs
will be aggregated to the holding company with the residual mismatch stated.

---

## 10. Open data quality findings

These are carried rather than resolved. Each is caught by a warn-severity dbt test, and
the affected values stay on their rows so that excluding them is a visible decision in the
analysis.

**Cost of deposits outside 0 to 8 percent: 55 bank-quarters** (`assert_deposit_cost_is_plausible`).

| Filer | Quarters | Range | Assessment |
|---|---|---|---|
| Santander Holdings USA | 14 | above 8%, from 2023Q1, peak 17.8% | Fault, undiagnosed |
| Flagstar | 9 | above 8%, from 2024Q1, peak 13.0%, tier 3 | Fault, undiagnosed |
| Raymond James | 7 | above 8%, from 2023Q2, peak 10.2% | Fault, undiagnosed |
| BNY Mellon | 3 | negative derived Q4, 2023–2025 | Q4 derivation failure (8.4) |
| BNY Mellon | 5 | −0.03% to −0.08%, 2020Q4–2022Q1 | Probably genuine |
| State Street | 8 | down to −0.16%, 2020Q2–2022Q1 | Probably genuine |
| Northern Trust | 8 | down to −0.06%, 2020Q2–2022Q1 | Probably genuine |
| Citigroup | 1 | −0.02%, 2020Q4 | Probably genuine |

The small negatives fall in years of zero US rates. The filers involved are custody banks
and Citigroup, which hold large foreign deposits on which negative euro and yen rates were
passed through. That explanation is plausible but has not been confirmed against filings.
BNY Mellon's 2020–2022 negatives belong to this group, not to the fourth-quarter failure.
None of them is a fourth quarter.

**Betas outside 0 to 1: five rows** (`assert_deposit_beta_is_plausible`).

| Filer | Cycle | Tier | Beta | Cost at each end |
|---|---|---|---|---|
| Santander Holdings USA | Test | 1 | 2.941 | 0.46% → 15.78% |
| Santander Holdings USA | Calibration | 1 | 1.453 | 2.51% → 5.77% |
| Raymond James | Test | 1 | 1.695 | 0.06% → 8.89% |
| Flagstar | Test | 3 | 1.295 | 0.28% → 7.03% |
| BNY Mellon | Test | 1 | −0.097 | −0.06% → −0.57% |

A beta above 1 means deposit costs rose by more than the policy rate. A beta below 0 means
they fell across a tightening cycle. Either points to a faulty endpoint, not to a real
bank's behaviour. The construct validity test excludes betas above 1 and reports the
result both with and without them.

Of the three betas with a `closing_only` endpoint, two are on this list: Santander in the
calibration cycle (2015Q4) and Flagstar in the test cycle (2022Q1). The third is Discover
in the calibration cycle. Taking the closing balance alone may contribute to those two
values. It has not been checked whether it accounts for them.

---

## 11. Reproduction

From `marketscope/`, with the virtual environment active and `MARKETSCOPE_SEC_USER_AGENT`
set:

```
python -m marketscope.pipeline                     # load the seeded universe and FRED
cd transform/dbt && dbt build --profiles-dir . && cd ../..
python analysis/milestone2/tier_coverage.py        # tiers, provenance, cycle coverage
python analysis/milestone2/construct_validity.py   # section 7.3
python analysis/milestone2/cycle_sensitivity.py    # section 5
python analysis/universe/reference_audit.py        # section 2.3
```

`dbt build` currently reports two warnings: the two warn-severity tests in section 10.
Outputs are written to each script's `output/` directory. Every figure in this document was
read from those outputs or from the warehouse after the build above, on 1 October 2026.
Because EDGAR data is live, a later load can differ wherever a filer has restated.
