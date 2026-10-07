# Methodology

How MarketScope turns SEC filings and the federal funds rate into a cumulative deposit beta
for each bank and cycle, what each step assumes, and where the result is known to be weak.

The specification says what is measured and the decision record says why each choice was
made. This document says how, in enough detail to reproduce every figure from a clean
checkout. Decisions are cited by number, for example (0021), and specification sections as
"specification 3.1".

**State at writing, 5 October 2026: Milestone 2 in progress.** Everything up to
`fct_deposit_beta` is built and tested, and so is the table of revisions. The entity events
table, the survivorship comparison and the regulatory validation are not. Each section says
which parts are in force and which are still to be built. A planned control is never
written up as a working one.

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
- **Taxonomies.** Facts are loaded from every taxonomy the endpoint publishes: us-gaap,
  dei, srt, invest, ecd and the filing-fee taxonomy ffd. The endpoint publishes no filer's
  own extension namespace, so concepts a filer defines for itself never reach the warehouse
  (0029). Section 3.3 explains why the metric then reads `us-gaap` alone.
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
question, so they are dropped in one place, inside the panel, and recorded as changes in
`int_fact_revisions` (section 8.5).

The rule does not carry the result (0030). Resolved on each period's value as first
published instead, 51 of 2,814 headline-tier bank-quarters move by more than a basis point,
and the cross-bank ordering of betas is unchanged: Spearman 1.000 in the calibration cycle
and 0.999 in the test cycle. One beta moves by more than 0.01, Columbia Banking's in the
test cycle, from 0.459 to 0.476 on the originals, and its problem is the reverse merger
behind it rather than the rule (section 8.3). Reproduce with
`python analysis/milestone2/precedence_sensitivity.py`.

### 3.3 Taxonomy pin

The panel reads `us-gaap` only. One concept name in two taxonomies is two concepts, and
eight names in the warehouse, `NetCapital` and `DerivativeNotionalAmount` among them, are
tagged under both us-gaap and srt or invest. Reading every taxonomy is only for profiling,
and the Milestone 0 search for tagged average balances is the one place it was used (0011).

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

Derivation is a fallback. Where any filing reports the fourth quarter directly, usually as
a comparative in the next first-quarter 10-Q, the reported value is used and nothing is
derived (0026). The annual figure a derivation starts from can differ in scope from the
quarterly concept it is subtracted against, and a reported quarter does not carry that
risk.

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
| `reported` | `InterestBearingDepositLiabilities` | 2,150 |
| `summed_components` | Domestic plus foreign, only when both are present | 441 |
| `derived_residual` | Total deposits less a complete non-interest-bearing figure | 475 |

These counts include the tier 2 rows. On those, `reported` means total deposits as
reported.

The residual route refuses a partial non-interest-bearing figure, such as a domestic
component with no foreign one. Subtracting too little would overstate the base without any
sign. The route also refuses a residual that is zero or negative. Total deposits is used
only when no interest-bearing route resolves.

**Reconciliation.** A reported or summed base is checked against the filer's own total and
non-interest-bearing figures, which together partition deposits, and is passed over for the
next route if it misses by more than 2 percent of total deposits (0027). Santander, Raymond
James and Flagstar tag a single deposit line under `InterestBearingDepositLiabilities`:
Flagstar's is exactly its money-market line. US Bancorp's figure excluded time deposits of
$100,000 or more until 2015Q3. Dividing by one line inflates the cost of deposits by the
inverse of that line's share, which put Santander's at 15.78 percent at the end of the test
cycle.

Where a reported base can be checked, it either reconciles to within 0.1 percent (1,482
period ends) or misses by more than 8 percent (94). The tolerance therefore separates two
populations and does not decide any case. Of the 2,452 bank-quarters on an interest-bearing
base, 1,810 are checked and reconcile, 475 are the residual and reconcile by construction,
and 167 cannot be checked because the filer tags no total or no complete
non-interest-bearing figure. Those 167 belong to Regions, KeyCorp, BNY Mellon, SunTrust, HSBC
USA, Truist and CIT. CIT's two are almost certainly the same fault (section 10).

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

No filer tags an average deposit balance in any taxonomy the company facts endpoint
publishes (0011). Average balances appear in the rate and volume tables of the MD&A. The
endpoint publishes no extension namespace, so whether a filer tags them under its own
concepts has not been tested (0029). Either way, no reported average reaches the pipeline.
Every denominator is therefore the mean of the opening and closing period-end balances,
with `avg_method = 'endpoint'`.

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
| Calibration start ±1 | 0.972, 0.997 | 0.995, 0.997 |
| Calibration end −1, +1 | 0.887, 0.957 | 0.887, 0.957 |
| Test start ±1 | 0.991, 0.992 | 0.991, 0.992 |
| Test end −1, +1 | 0.986, 0.979 | 0.986, 0.979 |

When the windows were adopted the test-end comparisons across all filers stood at 0.876 and
0.878, and 0023 records them at those values. The whole drop came from BNY Mellon's derived
2023Q4, which was negative. With its reported fourth quarter used instead (section 8.4),
the drop disappears. Since every beta is now plausible except where a shifted endpoint
reaches CIT's unreconcilable 2015Q3 (section 10), the two columns agree everywhere but the
calibration start.

Two of the four cycle endpoints, the calibration start (2015Q4) and the test end (2023Q4),
are fourth quarters. For most filers their flows are therefore derived. That follows from
when the rate turned rather than from any choice, but those endpoints carry whatever error
the derivation carries.

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
the 32 filers with a headline-tier beta and a reported deposit split, the Spearman
correlation is −0.356. Reproduce with `python analysis/milestone2/construct_validity.py`.

When the test was adopted (0022), two of the 32 carried betas above 1.0 and were excluded,
giving −0.358 across 30 and −0.409 across all 32. Both betas came from a single deposit
line tagged as the interest-bearing base, and on the reconciled base of 0027 every beta in
the sample is plausible. The result did not depend on the exclusion: it is negative, and of
much the same size, on every version of the sample.

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

**Built: exits.** Eleven members stopped filing periodic reports, and each carries an
exit or failure event in `entity_events`, which a dbt test enforces (section 8.3): SVB's
failure, MUFG Americas' deregistration and nine exits by merger.

**Not yet built.** The headline full-sample versus survivors-only comparison has not been
computed, because there is no headline result yet. No table yet carries each member's last
filed period and exit reason beside its other attributes.

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

**Built: the event record.** XBRL records no mergers, failures or deregistrations, so the
`entity_events` seed is curated by hand (0031). It holds 53 events from 2015 that change a
member's deposit base or end its reporting:

| Type | Events | Members |
|---|---|---|
| `acquisition` of a deposit-taking institution or its deposits | 41 | 26 |
| `reverse_acquisition`, the counterparty being the accounting acquirer | 1 | 1 |
| `exit_merger` | 9 | 9 |
| `exit_deregistration` | 1 | 1 |
| `failure` | 1 | 1 |

Every row cites the filing that reports the event: an 8-K Item 2.01 completion report for
44, an Item 8.01 press release or completion report for 6, a Form 15 for 2 and an Item 1.03
receivership report for SVB. `python analysis/milestone2/entity_event_audit.py` checks each
citation against the filer's EDGAR history — the accession belongs to the filer, carries the
form and item cited, and was filed between two days before the event and six days after it
— and all 53 pass. One of the 8.01 filings, for Citizens' acquisition of Investors Bancorp,
announces the expected closing date rather than the closing, because Citizens filed no
completion report.

Two dbt tests guard the exits. Every member whose last 10-K or 10-Q is more than six months
older than the newest in the load must carry an exit or failure event; eleven do, which is
every terminal filer in the universe. No exit may be dated before the period of the filer's
last periodic report. Comerica and Synovus, both members, merged out in early 2026 after
their 2025Q3 10-Qs, and a one-year rule had let them through (0032).

Left out: acquisitions that brought no deposits, branch purchases and sales, and changes of
name or structure under an unchanged CIK. No member changed CIK.

**Built: materiality.** `bank_entity_events` measures each acquisition by the step in the
member's total deposits from the quarter end before it completed to the quarter end it
completed in, read from `int_deposit_balances`, which holds the deposit base at every quarter
end whether or not a cost resolves there (0032). An acquisition moving the base by a tenth or
more is material; one whose step cannot be measured counts as material.

| | Acquisitions | Smallest step |
|---|---|---|
| Material | 38 | 11.4%, MUFG Union Bank at U.S. Bancorp |
| Not material | 4 | largest 8.9%, First Connecticut at People's United |

Nothing falls between 9 and 11 percent. The four below are First Republic at JPMorgan (0.9
percent), Suffolk and First Connecticut at People's United, and National Penn at BB&T. The
step includes any organic change in the same quarter, so it errs towards flagging an
acquisition that completed during a deposit surge.

The measurement also tested the seed. Every quarter since 2015 with a deposit step above 15
percent and no recorded event was checked for a completion filing, and nine missing events
were found and added, among them PacWest's acquisition of Square 1 in its calibration start
quarter. Large steps with no completion filing are left unrecorded: the 2020 deposit surge,
Santander Holdings USA in 2015Q4 and 2016Q3, Goldman Sachs in 2016Q2, E*TRADE in 2017Q1,
Ameriprise in 2022Q3 and BNY Mellon in 2026Q1.

**Built: the flag on betas.** `fct_deposit_beta.material_event_in_cycle` is true where a
material acquisition completed in any quarter from the cycle's start to its measured end.

| Cycle | Filers flagged | of which with a beta |
|---|---|---|
| Calibration | 10 | 9 |
| Test | 9 | 8 |

Specification 4 requires these to be shown separately in rankings. The flag is carried on the
row and the separation is applied in the analysis.

**The reverse acquisition.** Columbia Banking's 2023 merger with Umpqua made Umpqua the
accounting acquirer, so Columbia's later filings report Umpqua's history as Columbia's own
(section 8.5), and the precedence rule then mixes the two entities: a 10-Q restates the
comparative quarter's expense but not that quarter's balance sheet. Its test-cycle beta is
flagged. Its calibration-cycle beta measures Columbia before the merger, so any comparison of
Columbia across the two cycles compares two different banks.

**Not yet built.** Individual bank-quarters are not flagged. The event quarter is on every
row of `bank_entity_events`, but no bank-quarter table carries it.

### 8.4 Fourth-quarter derivation

**Handled.** Section 3.4. `build_panel` records which concepts were derived in each
quarter, and `int_deposit_cost` carries `q4_derived` on every row. The flag is true where
the reported numerator was derived, or where any component of a reconstructed numerator
was. A derived concept that does not feed the numerator, such as total interest expense
used only for the completeness check, does not set it. 743 of 3,066 bank-quarters are
derived. Of those, 725 are December quarters; the other 18 belong to Raymond James, whose
fiscal year ends in September, and to Discover, whose fiscal year ended in November until
2012.

**Tested.** Specification 7.2 requires a derived fourth quarter to be non-negative and
within band of its neighbouring quarters. `assert_derived_fourth_quarter_is_plausible`
flags a derived quarter that is negative, or that lies more than one percentage point
outside the range of its two neighbours, at warn severity. The band is three times the
largest distance seen among second quarters, the only quarters whose neighbours are both
reported (0025). It flags 11 quarters, listed in section 10.

**Diagnosed failure: BNY Mellon.** BNY Mellon's 10-K tags only deposits in domestic offices
under `InterestExpenseDeposits`, the concept its 10-Qs use for total deposit expense, and
tags foreign offices separately. Fiscal year less nine months therefore subtracted a total
from a domestic figure, and its derived fourth quarters were negative in 2023 and 2024, at
−0.57 and −1.58 percent, where it reports 3.81 and 3.32 percent. BNY Mellon reports each
fourth quarter as a comparative in the next first-quarter 10-Q, and every one of the
eleven it has reported disagrees with the derived value. Reported fourth quarters are now
used wherever they exist (0026), which moves its test-cycle beta from −0.097 to 0.744.

Its 2025Q4 has not been reported in any later filing yet, so it is still derived and still
wrong, at −0.74 percent. It feeds no beta and is flagged.

### 8.5 Tag drift and restatements

**Handled: tag drift.** The concept lists cover the alternatives each filer has used
across the window, and resolution is per quarter. A filer that switches from reporting
deposit expense directly to reporting components changes provenance and possibly tier at
that quarter, and the change is visible on the row. `tier_changes_in_cycle` flags it at
cycle level.

**Handled: precedence.** The most recent filing wins (section 3.2).

**Handled: revisions.** `int_fact_revisions` records every change of value for a us-gaap
period, one row per change, built by `marketscope.restatements` with the ordering the
panel's precedence uses (0028). A filing that repeats the published value, as a comparative
column does, is not a change: of 946,834 us-gaap periods, 506,522 are reported more than
once and 44,829 change value. Each row carries the replaced value with the filing that
first published it and the replacing value with the filing that first published that.
Revision 1 of a period therefore starts from the value as originally published, and the
row marked `is_current` ends on the value the panel uses; a dbt test requires exactly one
such row per revised period.

There are 48,206 revisions at all 51 filers. 2,883 periods are revised more than once, up
to nine times, and 1,167 revisions fall on the metric's own concepts. Other taxonomies are
left out: in the filing-fee taxonomy every note offered on a date reports its own amount
against the same instant, so separate offerings read as revisions of one fact.

**Partly established: what the revisions are.** `marketscope.restatements.classify_revision`
separates changes with a mechanical signature from the rest, judging only the two values
and the form of the revising filing (`analysis/milestone2/revision_audit.py`).

| Kind | Rule, applied in this order | Revisions | Share |
|---|---|---|---|
| Precision | Within half the coarser rounding unit of the two values, from $1,000 up | 9,592 | 19.9% |
| Sign | Same magnitude, opposite sign | 4,669 | 9.7% |
| Scale | Off by a factor of a thousand | 108 | 0.2% |
| Amendment | Any other change first carried by a 10-K/A or 10-Q/A | 1,286 | 2.7% |
| Substantive | Any other change | 32,551 | 67.5% |

A precision revision is the same figure republished at a coarser rounding, typically when
a filer moves from thousands to millions: $53,263,000 republished as $53,000,000. Zero is
treated as unrounded, because it is a multiple of every unit and says nothing about how a
figure was rounded.

Substantive revisions are not all corrections. 19,365 are first carried by a 10-Q, 11,831
by a 10-K and 1,355 by an 8-K, which is where a recast after an acquisition or a change of
segments is usually published. Their median moves the replaced value by 6.5 percent, and a
quarter of them move it by more than 37.5 percent. The two values cannot separate a
correction from a reclassification, so no restatement rate is stated.

The four concepts a tier 1 or tier 2 cost is computed from directly — deposit interest
expense, total, interest-bearing and non-interest-bearing deposits — carry 142 substantive
revisions, and 134 of them supply the value the panel now uses. At most filers they are
small. Three cases are not:

- **Columbia Banking System.** Its 2023 merger with Umpqua was a reverse acquisition, with
  Umpqua the accounting acquirer, so Columbia's later filings report Umpqua's history as
  its own. Year-end 2022 deposits were first published at $16.7bn and are now $27.1bn;
  deposit expense for 2022 went from $16.5m to $48.2m. A 10-Q restates the comparative
  quarter's expense but carries only the prior year-end balance sheet, so a 2022 quarter
  can pair Umpqua's expense with Columbia's own balances. That is an entity continuity
  problem as much as a restatement (section 8.3).
- **Raymond James.** A 2025 10-Q reports deposit expense of $441m against 2023Q1, the
  figure it also reports, correctly, against 2024Q1. $206m had stood for 2023Q1 since
  2023. The most recent filing wins, so the panel uses $441m for a quarter that is not a
  beta endpoint.
- **US Bancorp.** Its 2015 10-K restated the year-end 2014 interest-bearing base from
  $177.5bn to $205.4bn, the change decision 0027 inferred from the balances: the earlier
  figure left out large time deposits.

**Not built: snapshot.** The raw tables are fully replaced on each load (section 1.1). The
company facts endpoint keeps every filing's value, so this loses nothing EDGAR still
publishes, but a value the endpoint itself withdraws between loads leaves no trace.
Specification 7.1's snapshot on the raw fact table would catch that, and is deferred until
a scheduled refresh shows it happening (0028).

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

**Cost of deposits outside 0 to 8 percent: 24 bank-quarters** (`assert_deposit_cost_is_plausible`).

| Filer | Quarters | Range | Assessment |
|---|---|---|---|
| BNY Mellon | 1 | −0.74%, derived 2025Q4 | Q4 derivation failure (8.4) |
| BNY Mellon | 6 | −0.05% to −0.08%, 2020Q4–2022Q1 | Probably genuine |
| State Street | 8 | down to −0.16%, 2020Q2–2022Q1 | Probably genuine |
| Northern Trust | 8 | down to −0.06%, 2020Q2–2022Q1 | Probably genuine |
| Citigroup | 1 | −0.02%, 2020Q4 | Probably genuine |

The small negatives fall in years of zero US rates. The filers involved are custody banks
and Citigroup, which hold large foreign deposits on which negative euro and yen rates were
passed through. That explanation is plausible but has not been confirmed against filings.
BNY Mellon's 2020–2022 negatives belong to this group, not to the fourth-quarter failure.

Five of these small negatives are derived fourth quarters, which the methodology first
stated none were: State Street and Northern Trust in 2020Q4 and 2021Q4, and Citigroup in
2020Q4. BNY Mellon's 2020Q4 and 2021Q4 are reported, not derived, and are negative as
reported (0026). Where the neighbouring quarters are negative or near zero too, the
derivation is not the likely cause. Citigroup's −0.02 percent lies between neighbours of
0.50 and 0.27 percent and is not consistent with them, so it is left open (0025).

Until decision 0027 the test also caught 30 bank-quarters above 8 percent at Santander,
Raymond James and Flagstar. Each tagged one deposit line as its whole interest-bearing
base, and each is now measured on the reconciled base (section 4.2).

**Derived fourth quarters outside their neighbours: 7 quarters**
(`assert_derived_fourth_quarter_is_plausible`).

| Filer | Quarters | Value against neighbours | Assessment |
|---|---|---|---|
| BNY Mellon | 2025Q4 | −0.74% against 2.72% and 2.22% | Q4 derivation failure (8.4) |
| CIT Group | 2014Q4 | 3.58% against 1.67% and 1.69% | Unreconcilable base, below |
| State Street, Northern Trust, Citigroup | 5, in 2020Q4 and 2021Q4 | small negatives | Above |

Neither BNY Mellon's 2025Q4 nor CIT's 2014Q4 feeds a beta.

CIT's 2014Q4 is tier 1, on a reported interest-bearing base of $7.1bn against $15.8bn of
deposits, while its neighbouring quarters are tier 2 on total deposits. CIT tags the
interest-bearing concept in only two quarters and never tags non-interest-bearing
deposits, so the base cannot be reconciled. At 2015Q3 the same concept is below CIT's own
time deposits, which cannot be true of the whole interest-bearing base. The spike is
almost certainly a single deposit line, as at Santander, but the rule in 0027 cannot
refuse it.

Santander's fourth quarters of 2011 to 2014, flagged here until 0027 and recorded in 0025
as derivation failures, were not. Its 10-K year-end balances tagged a single deposit line
as the interest-bearing base while its 10-Qs did not until 2016, so only the fourth
quarters were inflated.

**Betas outside 0 to 1: none** (`assert_deposit_beta_is_plausible`).

The test caught four rows before 0027: Santander in both cycles, Raymond James and
Flagstar in the test cycle, all with costs measured on a single deposit line. Before 0026
it also caught BNY Mellon's test-cycle beta of −0.097. A beta above 1 means deposit costs
rose by more than the policy rate and a beta below 0 means they fell across a tightening
cycle. Either points to a faulty endpoint rather than to a real bank's behaviour, and every
case so far has been one.

Three betas have a `closing_only` endpoint: Santander and Discover in the calibration cycle
(2015Q4) and Flagstar in the test cycle (2022Q1). Taking the closing balance alone errs
where the balance moved within the quarter. Its size has not been measured for these three.

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
python analysis/milestone2/revision_audit.py       # section 8.5
python analysis/milestone2/precedence_sensitivity.py  # section 3.2
python analysis/milestone2/entity_event_audit.py   # section 8.3, needs the SEC
python analysis/universe/reference_audit.py        # section 2.3
```

`dbt build` currently reports two warnings, from the cost and derived-quarter tests in
section 10. The beta range test is also warn-severity and currently passes.
Outputs are written to each script's `output/` directory. Every figure in this document was
read from those outputs or from the warehouse after the build above, on 4 October 2026.
Because EDGAR data is live, a later load can differ wherever a filer has restated.
