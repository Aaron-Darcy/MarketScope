# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest first.

## [Unreleased]

### Changed

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
