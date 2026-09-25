# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest first.

## [Unreleased]

### Changed

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
