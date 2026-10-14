# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest first.

## [Unreleased]

### Fixed

- The terminal-filer test now requires an exit event once a member's last periodic report
  is six months older than the newest, rather than a year. Comerica and Synovus last filed a
  10-Q for 2025Q3 and merged out in early 2026, and the one-year rule had not yet noticed.
- The record that Milestone 0 searched each filer's own extension namespace for average
  deposit balances is withdrawn (decision 0029). The company facts endpoint publishes no
  extension namespace: the warehouse holds six standard taxonomies and nothing else, and
  the search read the same payloads. The averaging finding is narrowed to the taxonomies
  the endpoint publishes, and comments and documents claiming extension concepts are
  loaded are corrected. No figure changes.
- An interest-bearing deposit base that does not reconcile to total deposits less
  non-interest-bearing deposits is passed over for the next route (decision 0027).
  Santander, Raymond James and Flagstar tag a single deposit line under the aggregate
  concept, and US Bancorp's excluded large time deposits until 2015Q3, which inflated their
  costs of deposits by the inverse of the line's share. Every beta outside 0 to 1 is
  resolved: Santander's fall from 1.453 and 2.941 to 0.240 and 0.548, Raymond James's from
  1.695 to 0.601 and Flagstar's from 1.295 to 0.647. 104 costs change and no tier does. The
  cost, derived-quarter and beta plausibility tests fall to 24, 7 and 0 rows, and
  Santander's 2011 to 2014 fourth-quarter spikes turn out to be the same fault rather than a
  derivation failure.
- A fourth quarter that a later filing reports directly is used rather than overwritten by
  one derived from the fiscal year (decision 0026). BNY Mellon's 10-K tags only domestic
  deposit expense under the concept its 10-Qs use for the total, so its derived fourth
  quarters were wrong in all eleven years a reported one exists to check against, and its
  2023Q4 cost of deposits read −0.57 percent where 3.81 percent is reported. Its test-cycle
  beta moves from −0.097 to 0.744. Seventeen bank-quarters stop being marked derived and
  only BNY Mellon's costs change. The cost, derived-quarter and beta plausibility tests
  fall from 55, 14 and 5 rows to 54, 11 and 4.
- `fct_deposit_beta.metric_tier` is null where either endpoint is unresolved, as its
  column description states. DuckDB's `greatest` skips nulls, so Popular's calibration row,
  which has no start endpoint and no beta, carried tier 1. A test now requires the tier
  and both endpoint tiers to be present or absent together.

### Changed

- Milestone 2 closed (decision 0033). Flagging individual bank-quarters for entity events
  moves to Milestone 4 with `fct_bank_quarter`; betas are already flagged.
- Milestone 2 analysis outputs rerun on the reconciled deposit base. Construct validity now
  covers 32 filers with no beta excluded as implausible, at -0.356, against -0.358 on the
  30 plausible betas and -0.409 on all 32 when the test was adopted. Every one-quarter
  boundary shift in the cycle sensitivity holds at 0.887 or above on plausible betas.
- Milestone 2 analysis outputs rerun on reported fourth quarters. In the cycle sensitivity,
  moving the test cycle's end a quarter either way now holds at 0.987 and 0.983 across all
  filers, where BNY Mellon's derived 2023Q4 had pulled both to about 0.88; the derived
  test-cycle median beta is 0.583. Construct validity is unchanged at -0.358, because BNY
  Mellon tags no non-interest-bearing deposit split and was never in its sample.
- Construct validity reads the test cycle, and the policy rate at each of its ends, from
  `dim_rate_cycle` rather than pinning the window and averaging the raw FRED table itself.
  No analysis script from Milestone 2 onward now pins a cycle window. The result is
  unchanged at -0.358; betas differ only in the sixteenth significant figure, from the
  order in which averaging and the percentage conversion are applied.
- Tier coverage measures each filer against the windows in `dim_rate_cycle` rather than its
  own pinned copy. The calibration cycle is now fourteen quarters rather than fifteen; 44
  filers still clear the 80 percent floor in it and 37 in both cycles, so the persistence
  sample is unchanged.
- Cycle windows are the ones `dim_rate_cycle` derives, adopted as they fall: calibration
  2015Q4 to 2019Q1 and test 2022Q1 to 2023Q4. The calibration cycle ends a quarter earlier
  than the 2019Q2 originally pinned, because the quarterly average rate peaks in 2019Q1, so
  the derivation reproduces the test window but not the calibration window as an earlier
  entry stated. Milestone 0 scripts keep the windows the gate was measured on.
- Spearman rank correlation lifted out of the construct validity script into
  `marketscope.ranking`. Tied values now share the mean of their positions rather than
  being ranked in input order, and an undefined correlation raises instead of returning
  zero, which would have read as a finding of no relationship. The construct validity
  result is unchanged at -0.358, since no betas or shares tie.
- Deposit expense and non-deposit funding concept lists completed against the full universe
  and resolved by mutually exclusive category, preferring a filer's own category total over
  its parts so a filer tagging both is not double counted. Federal Home Loan Bank advances,
  repurchase agreements and six other funding lines were never subtracted, which inflated
  implied deposit expense and made complete reconstructions look short. Tier X falls from
  184 bank-quarters to 71; Valley National is fully recovered and First Horizon goes from 40
  excluded quarters to 3.
- Gate criterion G4 is recorded as failed at +0.085 and replaced by a cross-sectional
  construct-validity test across the universe. Non-interest-bearing deposit share correlates
  with cumulative beta at Spearman -0.358 over 30 filers, negative as predicted.
- Deposit balance denominators are genuinely two-point averages. `previous_quarter_end`
  stepped back from the first of the month rather than the first of the quarter and
  returned its own argument, so every denominator had been a closing balance while the row
  recorded `avg_method` as endpoint. G4 falls from +0.108 to +0.085 and no longer passes;
  the industry benchmark is unchanged because it never used averaging.
- Universe membership is decided by what a filer reports — total assets, deposits reaching
  5 percent of assets, interest paid on deposits, and a 10-K rather than a 20-F or 40-F —
  rather than by SIC code. Screening on the specification's SIC codes lost 8 of the largest
  50 deposit-taking filers, including Goldman Sachs, Morgan Stanley and Charles Schwab. SIC
  is retained as a descriptive attribute. SIC 6020 holds no EDGAR entities at all.
- Filers are ranked on the highest total assets reported across 2015Q4-2023Q4 rather than
  on a current snapshot, so an institution that stopped filing inside the window is ranked
  on what it was rather than dropped.

- Cost of deposits is denominated on interest-bearing deposits rather than total deposits,
  resolved by reported concept, summed domestic and foreign components, or total less a
  complete non-interest-bearing figure. Tier 1 coverage rises from 8 filers to 11.
- Numerators reconstructed from component concepts are checked against deposit expense
  implied by total interest expense less non-deposit funding, and excluded below 80 percent
  coverage rather than used understated.
- Filer identity is verified against the submissions endpoint rather than the `entityName`
  field on company facts, which reports the entity that published a fact rather than the
  registrant and is unusable as a filer key.
- Deposit balance denominators are two-point averages of period-end balances throughout.
  No filer in the sample tags an average deposit balance in any taxonomy, so reported
  averages are unavailable and the tier hierarchy now distinguishes only the deposit base.
- Regulatory filings are a coverage source as well as a validation source, since banks
  operating without a holding company file with their banking regulator and are absent
  from EDGAR entirely.

### Removed

- First Republic Bank, which has no company facts in EDGAR. Recorded with Signature Bank
  and Silvergate in `EXCLUDED_FROM_EDGAR` with the reason for each. PacWest Bancorp
  replaces it as the second terminal filer, covering both cycles.

### Added

- Regulatory validation of the XBRL cost of deposits (specification 5). At tier 1 it agrees
  with the Call Report figure to a median of 1.1 basis points and within 10 in 87 percent
  of 1,948 bank-quarters; 93 percent where the group is a single insured institution.
  Tier X quarters miss by a median of 36 basis points, which confirms the completeness check
  separates understated numerators from sound ones. Citigroup, Capital One, American
  Express and Morgan Stanley disagree by more than 10 basis points at the median.
- `int_regulatory_deposit_cost`, the cost of deposits per regulatory group and quarter from
  Call Reports, by the library arithmetic the XBRL metric uses so the two differ only where
  their figures do (decision 0035). 2,863 group-quarters across 43 groups, First Republic,
  Signature and USAA among them. `stg_fdic__financials` converts the FDIC's thousands to
  dollars and sums domestic and foreign deposit expense.
- Call Report deposit figures in `raw.fdic_financials`, loaded by the pipeline for the 43
  groups of the pinned regulatory table that are not foreign banking organisations: total,
  interest-bearing and non-interest-bearing deposits and quarterly deposit interest expense
  per insured institution from 2009. 6,778 institution-quarters across 186 institutions.
  `--skip-sec` and `--skip-fdic` join `--skip-fred`, so one source can be reloaded without
  refetching the others.
- FDIC BankFind client in `marketscope.ingestion.fdic`, paging collections through the
  shared rate limiter, cache and retries. The pinned table mapping FDIC groups to SEC
  registrants moves from the reference audit to `marketscope.regulatory` unchanged, with a
  filter selecting a group by regulatory high holder or, for a bank with no holding
  company, by certificate. The reference audit uses both and reproduces its output exactly.
- The four robustness variants pre-registered beside the headline. All agree with it:
  Spearman +0.590 with tiers 1 and 2 (24 filers), +0.534 with in-cycle acquirers included
  (30), +0.629 with between-cycle acquirers excluded (20), and +0.603 with SVB's shortened
  test cycle added (23), every p at or below 0.002. The survivorship comparison adds only
  SVB, because PacWest fails the acquisition rule and First Republic and Signature are not
  in EDGAR, and the methodology says so.
- The pre-registered headline result (specification 6.1). Across 22 filers, the Spearman
  correlation between calibration-cycle and test-cycle deposit betas is +0.590, one-sided
  permutation p 0.002, 95 percent bootstrap interval +0.154 to +0.836; persistence is
  supported by the rule fixed in advance. Half the filers keep their quartile, against a
  quarter by chance. State Street, Zions and Wells Fargo move two quartiles or more, and the
  hypotheses offered for them are labelled as formed after the result.
- Statistics for the pre-registered persistence analysis in `marketscope.ranking`:
  quartiles by rank, the quartile transition matrix, Pearson correlation, an OLS fit, a
  one-sided permutation test for a positive Spearman correlation and a percentile bootstrap
  interval, both seeded so results reproduce exactly. Spearman is now the Pearson
  correlation of average ranks, which changes no result. A bootstrap resample with no
  defined correlation is counted and left out rather than scored as zero.
- Pre-registered plan for the cross-cycle persistence analysis (specification 6.1, decision
  0034), fixed before the correlation was computed: a headline sample of 22 filers, a
  one-sided permutation test and bootstrap interval with a fixed seed, an interpretation
  rule, and four robustness variants.
- `dim_bank`, one row per universe member with its rank, pin, SIC as a descriptive
  attribute, the span of its periodic reports, its exit type, date and counterparty where it
  has one, and counts of its acquisitions. Carries the last filed period and exit reason
  specification 4 requires of every terminal filer, for all eleven.
- Materiality for entity events, measured as the step each acquisition produced in the
  member's total deposits, with a tenth or more counting as material (decision 0032). 38 of
  42 acquisitions qualify, and nothing falls between 9 and 11 percent.
  `fct_deposit_beta.material_event_in_cycle` flags ten calibration-cycle and nine test-cycle
  filers. `int_deposit_balances` holds the deposit base at every quarter end, including
  quarters where no cost resolves.
- Nine entity events the deposit steps exposed, each verified against its completion
  filing, among them PacWest's acquisition of Square 1 in its calibration start quarter and
  the 2026 exits of Comerica and Synovus. The seed holds 53 events.
- `entity_events`, a seed of the 44 acquisitions, mergers, exits and failures affecting a
  universe member from 2015, curated by hand because XBRL records none of them (decision
  0031). Each row cites the filing that reports the event, and an audit script checks every
  citation against the filer's EDGAR history; all 44 pass. dbt tests require an exit or
  failure event for every member that stopped filing periodic reports, which all nine do,
  and refuse an exit dated before a filer's last periodic report.
- Precedence sensitivity, resolving every bank-quarter on each period's first published
  value as well as its most recently filed one. 51 of 2,814 headline bank-quarters move by
  more than a basis point and the ordering of betas does not: Spearman 1.000 and 0.999 in
  the two cycles. The most recently filed value continues to win (decision 0030).
  `marketscope.facts.earliest_filed` keeps each period's original value for the
  comparison.
- Revision audit, classifying each change of published value by its mechanical
  signature: a coarser rounding of the same figure, a sign reversal, a factor of a
  thousand, an amendment, or a substantive change. Two thirds of the 48,206 revisions are
  substantive. On the concepts a headline cost is computed from, it finds Columbia
  Banking's history replaced by Umpqua's after their reverse merger, and a Raymond James
  2025 10-Q reporting 2024Q1's deposit expense against 2023Q1, which the precedence rule
  accepts.
- `int_fact_revisions`, every change of value for a us-gaap period across the filings
  that reported it, as specification 4 requires of the values restatement precedence
  discards (decision 0028). A comparative repeating the published value is not a change,
  so 48,206 revisions are recorded across 44,829 of 946,834 periods rather than every
  repeat. Ordered by the precedence the panel applies, and tested to end each revised
  period on exactly one current value. `marketscope.facts.revisions` replaces
  `superseded`, which nothing called and which counted every comparative as superseded.
- Derived fourth-quarter plausibility test from specification 7.2, at warn severity: a
  derived quarter is flagged if negative or more than one percentage point outside its
  neighbours' range (decision 0025). It flags 14 quarters, including newly found Q4
  spikes at Santander in 2011 to 2014 and CIT in 2014, and corrects the methodology's
  statement that none of the 2020 to 2022 negative costs fell in a fourth quarter.
- `q4_derived` on `int_deposit_cost`, true where the deposit expense numerator or any
  component of a reconstructed one was derived as fiscal year less nine months. Set on 760
  of 3,066 bank-quarters; every other value in the table is unchanged. `build_panel`
  returns the panel with the derived concepts per quarter, and `quarterly_panel` is now a
  view over it.
- `docs/methodology.md`, covering every step from ingestion to `fct_deposit_beta` and each
  data problem in specification section 4 with its current state. Entity events, the
  restatement table, the derived-Q4 test and the survivorship comparison are recorded as not
  yet built, and the open data quality findings are listed with figures.
- `fct_deposit_beta`, the cumulative deposit beta for every universe member in every study
  cycle, measured between the endpoint costs of deposits against the policy move over the
  same quarters. Each row carries both endpoint tiers, the less precise of the two as the
  beta's `metric_tier`, a `tier_changes_in_cycle` flag and quarter counts at tier 1 and at
  tiers 1 or 2, leaving headline eligibility to the analysis. A filer whose series ends
  inside a cycle is measured to its last resolved quarter and marked `partial_cycle`,
  which applies to SVB and PacWest in the test cycle. Members with no beta keep their
  row, and a test requires every member once per cycle. Reproduces all 32 test-cycle
  betas in the construct validity output. A warn-severity test flags the five betas
  outside 0 to 1: Santander in both cycles, and Raymond James, Flagstar at tier 3 and
  Bank of New York Mellon at -0.097 in the test cycle.
- `int_deposit_cost`, the cost of deposits per bank-quarter in the warehouse, as a dbt
  Python model calling `marketscope.deposit_cost` rather than a SQL reimplementation of the
  metric (decision 0024). Reproduces the tier coverage script's 3,066 bank-quarters exactly.
  Tested for one row per bank-quarter, the defined tier, provenance and averaging values,
  and the specification's 0 to 8 percent range at warn severity, which flags 55
  bank-quarters on its first run: the Santander, Raymond James and Bank of New York Mellon
  findings already carried, Flagstar's tier 3 costs from 2024, and small negative costs at
  three custody banks between 2020 and 2022.
- Cycle boundary sensitivity, shifting each derived boundary one quarter either way and
  comparing the resulting cross-bank ordering by rank correlation. Within-cycle ordering
  only; the cross-cycle persistence figure is deliberately not computed, so no window can
  be chosen by its effect on the headline. Every shift holds at 0.957 or above on plausible
  betas except ending the calibration cycle a quarter before the rate peak, at 0.884.
  Shifting the test cycle's end falls to 0.876 across all filers, driven by a negative
  derived fourth-quarter cost of deposits at Bank of New York Mellon, -0.57 percent.
- `marketscope.cycles` reads the calibration and test windows from `dim_rate_cycle` and the
  quarterly policy rate from the view they are derived from, and raises if either study
  cycle is missing, duplicated or joined by an unknown name, so analysis no longer needs a
  window pinned in its own source.
- `dim_rate_cycle` is tested to name the calibration and test cycles exactly once each.
  A plateau at the peak marks every quarter on it as a peak, and the model collapses them
  to one cycle only because no quarter lies strictly between adjacent peaks, so the
  outcome is pinned by a test rather than left to that property of the join.
- Monetary cycle windows derived from the federal funds series into `dim_rate_cycle` rather
  than hardcoded, as specification section 2 requires. Turning points come from a centred
  four-quarter window on the level series; the derivation reproduces both study windows and
  carries twelve earlier tightening cycles back to 1954 as context.
- Construct validity check relating funding mix to deposit beta across the universe,
  replacing the two-bank comparison in G4.
- Tier coverage measurement across the full universe, read from the warehouse rather than
  the SEC. Tier 1 covers 75.8 percent of 3,064 bank-quarters and 43 of 51 filers reach it;
  37 filers carry headline coverage in both cycles and can support the persistence test.
- Bank-quarter panel lifted out of the feasibility script into `marketscope.panel`, taking
  facts rather than an API payload so it works from the warehouse, and pinning the taxonomy
  so an extension concept sharing a standard name is not read as the standard one.
- DuckDB load covering the committed universe: 1,809,702 USD facts across every taxonomy,
  709,163 filings, 51 registrants and 30,854 FRED observations, with no filer failing.
  Rows stream in per filer through Arrow batches, and facts, filings and registrants share
  one transaction so a partial run cannot leave them describing different sets of filers.
- dbt project on DuckDB with four staging models — company facts, submissions, tickers and
  the FRED series — and 21 tests.
- Committed universe seed at `data/seeds/universe.csv`, which ingestion reads so a load
  covers a fixed set of filers. `--check` fails when a rebuild drifts from it and
  `--write-seed` adopts a new membership deliberately.
- Pinned universe members, seated alongside the ranked fifty rather than displacing the
  smallest. PacWest peaked at 41bn and ranks 58th, so the assets ranking alone would have
  dropped a terminal filer the project selected on purpose.
- Top-50 universe construction from EDGAR, with each member graded on how far it can be
  followed: XBRL present, 10-K covering fiscal 2015 or later, or neither.
- Reference audit sizing the institutions EDGAR cannot reach, against a ranking of the
  largest 50 US depository groups rolled up from FDIC insured-institution financials to
  regulatory high holder. 40 of 50 are reachable; 3 are absent for want of registered
  securities and 7 are US operations of foreign banking organisations. The mapping is
  pinned on FDIC identifiers and raises on an unrecognised group rather than assuming
  coverage, because name matching maps First Republic Bank onto Republic First Bancorp.
- SEC client support for the XBRL frames endpoint, SIC company enumeration through the
  Atom company browser, and a company-facts presence check that distinguishes a registrant
  with no XBRL from one absent from EDGAR entirely.
- Deposit cost and cumulative deposit beta, annualised by simple multiplication and scaled
  by average interest-bearing deposits, following the convention used in Federal Reserve
  work on FR Y-9C filings.
- Gate criterion G4 check comparing a direct bank against a branch-funded regional, and an
  industry aggregate benchmarked against the published Federal Reserve figure.
- Project specification covering scope, cycle definitions, metric comparability tiers,
  known data problems, validation approach, model layout and milestone gates.
- Decision record seeded with the eight decisions taken during scoping.
- SEC EDGAR client with mandatory contact-bearing User-Agent, rate limiting below the
  ten-requests-per-second ceiling, disk response caching, bounded retries on transient
  status codes, and pagination through supplementary submission pages for filers whose
  history exceeds the inline window.
- FRED client resolving the missing-value marker to null rather than leaving it as a
  string.
- Feasibility sample of twelve bank holding companies, spanning large diversified,
  super-regional, regional and direct funding profiles, including two terminal filers and
  four institutions with mid-window acquisitions.
- Candidate concept lists for deposit interest expense and deposit balances, to be
  profiled rather than assumed.
- Milestone 0 profiling script reporting concept availability, period coverage and
  fact periodicity per filer, with identity verification against the returned entity name.
- XBRL fact extraction flattening the company facts payload into typed rows, classifying
  each observation as instant, quarterly, semiannual, nine-month or annual.
- Restatement precedence keeping the most recently filed value for each period, with the
  superseded values retained separately as the input to the filing-behaviour question.
- Fourth-quarter derivation for filers that publish no fourth 10-Q, taking the residual of
  the fiscal year against the nine-month figure where available and against the summed
  first three quarters otherwise.
- Milestone 0 script answering whether average deposit balances are tagged in any
  taxonomy, how often the fourth quarter resolves, and what quarterly coverage each
  candidate concept achieves across the calibration and test windows.
- Continuous integration running lint, format, type and test checks.
