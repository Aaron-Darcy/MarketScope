# Decision record

Numbered, dated, append-only. A decision is superseded by a later entry, never edited in
place. Each entry records what was decided, the alternatives considered, and what the
decision costs.

---

## 0001 — Narrow scope to US bank holding companies

**Date** 2026-09-02
**Status** Accepted

**Context.** The original concept covered all US-listed companies across every sector. XBRL
tagging conventions differ substantially by industry, so broad coverage means handling many
tagging dialects at once, with shallow understanding of each.

**Decision.** Restrict the initial release to the largest 50 US bank holding companies.

**Alternatives.** Full-market coverage with a shallower metric set; a sector rotation
approach covering three or four industries.

**Consequences.** One tagging dialect and largely calendar-aligned fiscal years, which
makes the harmonisation work tractable within the delivery window. Domain knowledge
concentrates in one industry rather than spreading thin. Broad coverage becomes a later
expansion on a working pipeline, which is a cheaper order of operations than the reverse.

---

## 0002 — Frame the question around cross-cycle persistence, not prediction

**Date** 2026-09-02
**Status** Accepted

**Context.** An earlier framing described predicting funding-cost stress. Deposit betas are
associated with institutions that later failed, which makes an unguarded framing read as a
bank-failure predictor.

**Decision.** The published question concerns whether repricing behaviour in one cycle
helps explain cross-bank funding-cost pressure in the next. No distress or failure
prediction is claimed anywhere in the project.

**Consequences.** Statistically defensible and honest about what the design supports. Less
dramatic than the alternative, which is the point — an overstated claim is a liability
under questioning.

---

## 0003 — Report rank persistence ahead of regression fit

**Date** 2026-09-02
**Status** Accepted

**Context.** The calibration cycle moved roughly 225bp over 36 months; the test cycle moved
roughly 525bp over 16 months. Deposit betas run higher in faster, larger cycles, so
absolute levels are not expected to transfer.

**Decision.** Spearman rank correlation between cycle betas is the headline result.
Quartile transitions follow. Pearson correlation and OLS are reported as secondary.

**Consequences.** The reported statistic matches what the data structure actually supports,
and avoids the failure mode of tuning for R² on a relationship that was never expected to
hold in levels. Rank persistence is also easier to explain to a non-technical reader.

---

## 0004 — Assign comparability tiers rather than force a single formula

**Date** 2026-09-02
**Status** Accepted

**Context.** Deposit interest expense and deposit balances are tagged inconsistently across
filers. Interest expense on interest-bearing deposits over total deposits is not the same
measure as the same numerator over average interest-bearing deposits, but both are
computable from what filers publish.

**Decision.** Compute cost of deposits at the most precise tier each filer-quarter
supports and record the tier on the row. Headline results run on tier 1 alone, then repeat
including tier 2 as a robustness check.

**Alternatives.** Force all filers to the lowest common denominator, which discards
precision; or exclude any filer not supporting tier 1, which biases the sample toward
larger filers with richer disclosure.

**Consequences.** Sample size becomes a reported quantity rather than an implicit one.
Coverage by tier is published. More work in the transformation layer, and results must
always be read alongside their tier.

---

## 0005 — Retain terminal filers

**Date** 2026-09-02
**Status** Accepted

**Context.** Institutions that failed in 2023 stop appearing in the SEC ticker file and in
any universe built from currently listed companies. They are also the institutions where
deposit repricing pressure was most acute.

**Decision.** Terminal filers are pinned by CIK, retained with an explicit
`last_filed_period` and exit reason, and included in the analytical panel. Every headline
result is reported for the full sample and for surviving banks only.

**Consequences.** Avoids a survivorship bias that would understate the measured effect.
Requires explicit handling of partial-cycle coverage, since terminal filers do not have
filings through the test-cycle peak. The difference between the two samples becomes a
reportable result in itself.

---

## 0006 — Serve from DuckDB; defer Snowflake

**Date** 2026-09-02
**Status** Accepted

**Context.** Snowflake is the warehouse named in the roles this project targets, but a
permanently available public site backed by Snowflake incurs a recurring cost with no end
date and adds an external dependency that can fail unattended.

**Decision.** Build and serve on DuckDB. Add Snowflake as a later parallel target, with
marts materialised down for serving.

**Alternatives.** Postgres, which is more conventional for serving but requires a hosted
instance; Snowflake throughout, which is the simplest architecture and the most expensive.

**Consequences.** Zero running cost and nothing to monitor. dbt models are written to run
on both engines, which constrains use of engine-specific SQL. The Snowflake claim is
deferred until the work actually exists rather than asserted early.

---

## 0007 — Validate derived metrics against regulatory filings

**Date** 2026-09-02
**Status** Accepted

**Context.** The accuracy of any XBRL-derived metric depends on the tag mapping behind it,
and that mapping is normally unverifiable by a reader. FFIEC and FDIC data carry the same
concepts in standardised form, including for institutions that later failed.

**Decision.** Use regulatory data as ground truth for a sample of bank-quarters and publish
the agreement as a measured error rate. Keep XBRL as the primary source.

**Alternatives.** Use regulatory data as the primary source, which removes the
harmonisation problem but also removes the substantive engineering work; or publish
derived metrics without independent validation.

**Consequences.** Converts an assertion about tag mapping into a stated error rate. Adds
an entity-mapping problem, since FDIC data is at insured-institution level and SEC filings
are at holding-company level. Validation is restricted to single-bank holding companies or
aggregated with the residual mismatch stated.

---

## 0008 — Gate infrastructure behind a feasibility study

**Date** 2026-09-02
**Status** Accepted

**Context.** The entire design assumes a comparable cost-of-deposits series can be
constructed from XBRL. Whether average balances are tagged at all is unknown and is the
single largest risk to the project.

**Decision.** Milestone 0 profiles concept availability across a twelve-bank sample against
five explicit gate criteria. No warehouse, dbt project or site is built until the gate
passes.

**Consequences.** Two weeks before infrastructure work begins. If the assumption is wrong,
it costs two weeks rather than six. The sample is deliberately constructed to include a
direct bank and a branch-funded regional, so that the absence of the expected repricing
contrast fails the gate rather than passing unnoticed.

---

## 0009 — Verify filer identity against submissions, not company facts

**Date** 2026-09-04
**Status** Accepted

**Context.** Identity verification initially compared the expected name against the
`entityName` field on the company facts payload. Two of twelve sample filers failed that
check while having entirely correct CIKs. CIK 70858 is Bank of America Corporation, but its
company facts payload reports `BofA Finance LLC`, a financing subsidiary filing under the
same CIK. CIK 72971 returns `WELLS        FARGO & COMPANY/MN`, padded with repeated
whitespace.

**Decision.** Resolve the registrant name from the submissions endpoint, which returns the
authoritative name, and normalise whitespace and casing before comparing.

**Consequences.** One additional request per filer, which the cache absorbs. The wider
lesson is recorded because it applies beyond identity: `entityName` on company facts
describes whichever entity published a given fact, not the registrant, so it must not be
used as a filer key anywhere in the pipeline.

---

## 0010 — Drop First Republic Bank; substitute PacWest Bancorp

**Date** 2026-09-04
**Status** Accepted

**Context.** First Republic Bank has no company facts in EDGAR. CIK 1132979 exists under
that name but carries only 40-6B/A and SC 13G filings, and a company search returns no
First Republic entity with 10-K filings other than an unrelated predecessor that stopped
filing in 2008 and Republic First Bancorp, a different institution. The cause is
structural: First Republic was a state-chartered bank with no holding company, and such
banks file periodic reports with their primary federal banking regulator rather than the
SEC. Signature Bank is absent for the same reason.

**Decision.** Remove First Republic from the EDGAR-sourced sample and record it, with
Signature and Silvergate, in `EXCLUDED_FROM_EDGAR` with the reason. Substitute PacWest
Bancorp as the second terminal filer.

**Alternatives.** Silvergate Capital Corporation is present in EDGAR with XBRL, but its
first 10-K covers fiscal 2019, so it has no calibration-window history and cannot
contribute to the persistence test. PacWest files from fiscal 2013 through 2023Q3, spans
both cycles, and exited by merger after sustained deposit outflow, which exercises the
terminal-filer and entity-event paths together.

**Consequences.** The sample stays at twelve and the gate arithmetic is unchanged.
Regulatory data moves from a validation source to a coverage source, because the two most
consequential institutions of 2023 are otherwise unreachable. Universe construction at
Milestone 1 must verify EDGAR presence per filer rather than assuming it from listing
status and SIC code.

---

## 0011 — Adopt endpoint averaging for all deposit balances

**Date** 2026-09-04
**Status** Accepted

**Context.** The tier definitions assumed average interest-bearing deposits would be
available for at least some filers. Milestone 0 scanned every taxonomy present for all
twelve filers, including each filer's own extension namespace, for any concept combining an
average marker with a deposit marker. None was found. Average balance sheets appear in the
rate and volume tables of the MD&A and are not tagged.

**Decision.** Compute every denominator as a two-point average of period-end balances.
Retain the `avg_method` field, always `endpoint` for now, so a filer that begins tagging
averages later is distinguishable without a schema change.

**Consequences.** The tier hierarchy survives but now distinguishes only the deposit base
used, not the averaging method: tier 1 uses interest-bearing deposits, available for 8 of
12 filers; tier 2 uses total deposits, available for all 12. Endpoint averaging introduces
error where deposit balances moved sharply within a quarter, which is precisely the
condition under study in 2022 and 2023. The size of that error is measurable against
regulatory data, which reports true averages, and quantifying it is now a required part of
the validation work rather than an optional extra.
