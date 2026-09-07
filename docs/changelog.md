# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest first.

## [Unreleased]

### Changed

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
