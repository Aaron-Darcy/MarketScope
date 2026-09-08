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

---

## 0012 — Denominate cost of deposits on interest-bearing deposits

**Date** 2026-09-08
**Status** Accepted. Refines 0004 and 0011.

**Context.** Tier 2, dividing by total deposits, was available for every filer and tier 1 for
only eight of twelve, which made tier 2 the tempting default. Non-interest-bearing deposits
have a deposit beta of zero by construction, so a total-deposit denominator scales a bank's
measured beta by its interest-bearing share. That share is a function of business model —
near total for a direct bank, far lower for a commercial bank funded by business operating
accounts — and it moved sharply during 2022 and 2023 as balances migrated into
interest-bearing accounts. Applied to gate criterion G4, which compares a direct bank against
a branch-funded regional, tier 2 would have widened the gap for reasons unrelated to
repricing and produced a pass the evidence did not support.

**Decision.** Denominate on interest-bearing deposits wherever resolvable, by three routes
recorded on the row: the reported concept; domestic plus foreign components summed; or total
deposits less a complete non-interest-bearing figure. Total deposits is used only where no
interest-bearing base exists at all.

**Alternatives.** Tier 2 throughout, rejected above. Restricting to filers reporting the
concept directly, which would have dropped JPMorgan, Citigroup and Zions and biased the
sample toward filers with richer disclosure.

**Consequences.** Tier 1 rises from 8 filers to 11, covering 708 bank-quarters. Federal
Reserve work on FR Y-9C filings uses the same denominator, which makes the published industry
figure a usable benchmark. The residual route requires a complete non-interest-bearing
figure and refuses a partial one rather than approximating.

---

## 0013 — Check reconstructed numerators for completeness before use

**Date** 2026-09-08
**Status** Accepted

**Context.** Summing whatever component concepts a filer happens to tag produced a badly
understated numerator for M&T Bank. At 2023Q3 its total interest expense was $866m, of which
$101m was long-term debt and $69m short-term borrowings, implying roughly $696m on deposits.
Only `InterestExpenseTimeDeposits` was tagged that quarter, at $202m. The reconstruction
captured 29 percent of the true numerator and produced a test-cycle beta of 0.095, four times
below the next lowest bank. A silently understated numerator is indistinguishable from a
genuinely low-beta bank, which is the most dangerous failure mode available to this metric.

**Decision.** Where the numerator is reconstructed from components, test the sum against
deposit expense implied by total interest expense less identifiable non-deposit funding. Below
80 percent coverage the bank-quarter is marked tier X and excluded from results, with the
coverage ratio retained on the row.

**Alternatives.** Extending the component list, which does not help because the concepts exist
in M&T's taxonomy but are untagged in the affected quarters. Excluding M&T outright, which
would discard the quarters where reconstruction is sound.

**Consequences.** 31 M&T bank-quarters excluded, coverage as low as 2 percent. M&T has no
test-cycle beta and drops from the cross-bank ranking. Tier X moves from a defined but unused
category to one the pipeline actually assigns. The check depends on the non-deposit funding
list being reasonably complete; where total interest expense is absent no check is possible and
the reconstruction is accepted with `component_coverage` null, which is visible rather than
assumed correct.

---

## 0014 — Validate the metric against the published industry beta

**Date** 2026-09-08
**Status** Accepted

**Context.** G4 compares two banks. A pass on a single pair is weak evidence that the metric
measures deposit behaviour rather than reporting artefacts, and the observed margin was thin.
Federal Reserve work on FR Y-9C filings reports the industry cumulative interest-bearing
deposit beta at roughly 0.4 in both the 2015-2019 and 2022-2023 cycles.

**Decision.** Compute an industry aggregate by summing expense and balances across the sample
before dividing, matching how the published figure is constructed, and require it to land
within 0.15 of 0.4 in both cycles.

**Consequences.** Passed at 0.354 for calibration and 0.480 for the test cycle. This is a
stronger check than G4 because units, averaging method, annualisation and tag mapping all have
to be right simultaneously to reproduce an external number. It also provides the first
independent evidence for the specification's assumption that betas run higher in faster
cycles. The check does not validate cross-bank dispersion, which remains the job of the
regulatory comparison in section 5 of the specification.

---

## 0015 — Decide universe membership by reported deposit behaviour, not SIC code

**Date** 2026-09-09
**Status** Accepted. Refines 0001.

**Context.** Section 1 identified the universe by SIC codes 6020, 6021, 6022, 6035 and
6036. Measured against EDGAR that screen loses eight of the fifty largest deposit-taking
filers. Goldman Sachs, Morgan Stanley, Charles Schwab and Raymond James carry SIC 6211,
security brokers and dealers. American Express and Synchrony carry 6199, Discover carries
6141 and Ameriprise carries 6282. Every one of them files a 10-K with full XBRL, is a
regulated depository holding company, and appears in the FDIC ranking of the largest fifty
US depository groups. Schwab is also the clearest cash-sorting case of 2023, which is the
behaviour the study exists to measure. SIC is a self-reported administrative attribute on
the EDGAR entity record, not a regulatory classification, and nothing keeps it current.
SIC 6020 turns out to be a group heading: EDGAR returns no entities for it at all.

**Decision.** Membership is decided by what a filer reports, under four rules answerable
from EDGAR alone. It reports total assets, so it can be ranked. Deposits reach five percent
of assets in some period of the study window. It reports interest paid on deposits under
any concept in the candidate list. It files a 10-K rather than a 20-F or 40-F. SIC is
retained on the row as a descriptive attribute and as the basis for reporting how far the
old screen would have diverged.

**Alternatives.** Keep the SIC screen and add the eight by explicit inclusion, which works
but leaves a hand-maintained list that has to be re-audited whenever the universe is
rebuilt, and which needs an external source to discover the omissions in the first place.
Make the FDIC rollup the membership authority, which is regulatory truth but makes
Milestone 1 depend on a source the specification places at Milestone 3, and requires a
name-to-CIK mapping layer that has no reliable key.

**Consequences.** The universe is reproducible from EDGAR alone and self-maintaining: an
institution that begins taking deposits enters without anyone editing a list. Two screens
are needed rather than one, because deposit funding alone does not identify a
deposit-taking institution — an insurer tags annuity and other deposit-type contracts under
the same `Deposits` concept a bank uses for its funding base, which is how Fidelity
National Financial reached the ranking before the interest test was added. The interest
test sweeps the whole concept list rather than the aggregate alone, because M&T Bank,
Flagstar and Valley National tag only leaf categories, the pattern recorded in 0013.

The deposit-funding threshold carries no weight. Above twenty billion dollars of assets the
largest non-depository ratio is 0.024, Nelnet, and the smallest depository ratio is 0.210,
Ameriprise. Any cut inside that gap selects the same filers.

Foreign private issuers are excluded by scope rather than by coverage. National Bank of
Greece passes both deposit tests and would otherwise rank inside the fifty; it files 20-F
and is not a US bank holding company. The two are counted separately so that a genuine
coverage failure is never recorded as a scope judgement.

The universe now includes institutions whose deposit franchise is a minor part of the
balance sheet — Goldman at a 0.26 deposit share, Morgan Stanley at 0.30, Ameriprise at
0.22. Their betas are computed on the deposit base like everyone else's, but their funding
mix differs enough from a branch-funded regional that the descriptive work in section 6 of
the specification has to show funding mix alongside beta rather than ranking on beta alone.

---

## 0016 — Size the EDGAR coverage gap against a regulatory ranking, and leave FDIC ingestion at Milestone 3

**Date** 2026-09-09
**Status** Accepted. Extends 0010.

**Context.** 0010 established that a bank operating without a holding company files with
its primary federal banking regulator rather than the SEC, and that First Republic and
Signature are both absent from EDGAR for that reason. Nobody had sized how far that extends
across the largest fifty. If it were a large share, the FFIEC and FDIC work the
specification places at Milestone 3 would have to move into Milestone 1, because everything
built on an EDGAR-only universe would inherit the gap.

A universe built from EDGAR cannot answer this. A bank that files nothing with the SEC
reports no assets in XBRL, so it cannot be ranked, and every filer in a top fifty derived
from EDGAR has XBRL by construction. The measurement needs a ranking from outside EDGAR.

**Decision.** Rank US depository groups by rolling FDIC insured-institution financials at
2022-12-31 up to each institution's regulatory high holder, which puts a bank with no
holding company into the ranking as its own group, and map the largest fifty to SEC
registrants through a pinned, hand-verified table keyed on FDIC identifiers. The reference
date is the opening of the test cycle, when every institution of interest was still
reporting.

**Alternatives.** FFIEC NPW, which publishes holding-company data directly and would avoid
the insured-institution rollup, is CAPTCHA-gated and cannot be fetched programmatically.
Matching names rather than pinning identifiers, which is what the first attempt did: it
mapped First Republic Bank onto Republic First Bancorp, a different institution, and
Signature Bank onto National Bank Holdings. That is the exact confusion 0010 records, and
it would have reported a coverage gap of zero.

**Consequences.** Forty of the largest fifty groups are reachable in EDGAR: thirty-eight
through a top-tier registrant and two, HSBC and Santander, through a US intermediate
holding company that files a 10-K against registered debt. Ten are not.

The pattern 0010 describes accounts for two of them, First Republic at 213bn and Signature
at 110bn. A third, USAA at 113bn, is absent for a related but distinct reason: it is a
member-owned reciprocal inter-insurance exchange with no registered securities. The
remaining seven are US operations of foreign banking organisations — Toronto-Dominion at
423bn, Bank of Montreal, UBS, Royal Bank of Canada, BNP Paribas, Bank of China and Standard
Chartered — which file FR Y-9C and have no SEC-registered US entity.

The mechanism is registered securities, not corporate structure. Zions Bancorporation
dissolved its holding company in 2018 and files as the bank itself, and is fully covered.
A bank with no holding company is invisible to EDGAR only when it also has no registered
securities.

Two institutions of fifty is a footnote, so FFIEC and FDIC ingestion stays at Milestone 3
and Milestone 1 proceeds on EDGAR alone. All three institutions absent for want of
registered securities — the two above and USAA — are recorded in `EXCLUDED_FROM_EDGAR` and
recovered from regulatory data at Milestone 3, as 0010 already provides for the first two. The seven foreign
banking organisations are a scope boundary rather than a coverage failure and are not
recovered at all: they are not US bank holding companies and never had EDGAR coverage to
lose. Both counts are published on the data health page, because a reader entitled to ask
what "largest fifty" excludes should not have to reconstruct it.

The audit refuses to guess. A group the pinned table does not cover raises rather than
falling through as covered, so a shift in FDIC data surfaces as a failure rather than as a
quietly improved coverage rate.
