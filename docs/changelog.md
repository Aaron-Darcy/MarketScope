# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest first.

## [Unreleased]

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
- Continuous integration running lint, format, type and test checks.
