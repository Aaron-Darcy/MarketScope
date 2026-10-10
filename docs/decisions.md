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

---

## 0017 — Seat pinned filers alongside the ranked fifty rather than inside it

**Date** 2026-09-09
**Status** Accepted. Resolves a conflict between 0005 and 0015.

**Context.** 0005 retains terminal filers, pinned by CIK, so that a pipeline built on
currently listed companies cannot understate the effect under study. 0015 decides
membership by peak total assets across the study window and takes the largest fifty. The
two rules conflict for PacWest Bancorp: it peaked at $41bn and ranks 58th of the 621 filers
that pass the deposit screens, against a fiftieth-place cut of $50bn.

This is not the ranking failing to see a shrinking bank. Ranking on the peak of the window
already keeps an institution at the size it reached, which is why SVB is seated at 19th on
$212bn despite filing nothing after 2022Q4. PacWest was simply never a top-fifty bank by
assets. It is in the project because 0010 selected it as a terminal filer that spans both
cycles and exited by merger after sustained deposit outflow, which exercises the terminal
filer and entity event paths together — a reason the ranking has no way to express.

**Decision.** Pinned filers are additional to the fifty rather than seated within it. The
universe holds 51 members: the largest fifty by peak assets plus PacWest, carrying a
`pinned` flag and the reason on the row. A pinned filer that would have ranked inside the
fifty anyway is marked in place rather than added twice. A pinned CIK that does not survive
the membership screens raises rather than being seated silently.

**Alternatives.** Displace the fiftieth member, which keeps the count at fifty but drops a
bank that was genuinely larger in order to fit one that was not, and makes the published
ranking a worse description of the banking system than the data supports. Lower the cut
until PacWest qualifies, which would admit eight more banks nobody has argued for to solve
a problem with one. Drop PacWest and rely on SVB alone, which leaves the terminal-filer
path exercised only by a bank that failed outright, never by one that exited by merger.

**Consequences.** The universe size becomes a reported quantity rather than a constant,
which is consistent with 0004 already treating sample size that way. Every headline result
must state whether it runs on the ranked fifty or on all seated members, because including
a bank that was never top-fifty changes the composition of a cross-bank distribution.
Rankings and quartile transitions are computed on the ranked fifty; survivorship
comparisons use all seated members, which is the reason the pin exists.

Silvergate is not pinned. It ranks 116th on a $16bn peak and, as 0010 records, its first
10-K covers fiscal 2019, so it cannot contribute to the cross-cycle test at all.

---

## 0018 — Commit the resolved universe and rebuild it deliberately

**Date** 2026-09-09
**Status** Accepted

**Context.** Milestone 1 exits when the full universe ingests reproducibly. Universe
construction reads live XBRL frames, and the fiftieth place is decided by a $50bn cut with
banks a few hundred million apart around it. A filer restating total assets, or publishing
a fact that lands it in a frame it was previously absent from, reorders the cut. Ingestion
driven straight from a rebuild would then cover a different set of banks than the previous
run, silently, and every result downstream would shift with no record of why.

**Decision.** The resolved universe is committed to `data/seeds/universe.csv` and ingestion
reads that file. Rebuilding is a separate, deliberate act: `--write-seed` regenerates it and
`--check` fails when a fresh build departs from it. Membership changes and rank changes are
reported separately, because a bank entering or leaving changes what is ingested while a
bank moving one place changes only the order results are presented in.

**Alternatives.** Rebuild on every run, which is reproducible only in the sense that the
code is deterministic — the inputs are not. Pin the CIKs in Python beside `PINNED_FILERS`,
which makes the universe a code change rather than data and puts fifty-one rows of
generated content into a module. Freeze the frames themselves, which fixes the inputs but
also freezes the restatement history the secondary question depends on.

**Consequences.** Ingestion, and every result built on it, covers a fixed set of filers
until someone changes the seed and says why in the commit. The seed can go stale: a bank
crossing into the top fifty will not appear until the universe is rebuilt, so `--check`
belongs in the scheduled refresh at Milestone 6 as a warning rather than a failure. The
diff is the review artefact — a rebuild that adds one bank and removes another is a
one-line change to read, which is the point of committing the resolved list rather than the
rule that produced it.

---

## 0019 — G4 fails once endpoint averaging is actually applied

**Date** 2026-09-11
**Status** Open. Supersedes the G4 outcome recorded on 2026-09-08.

**Context.** Lifting the bank-quarter panel into the library for Milestone 2 surfaced a
defect in `previous_quarter_end`. It stepped back one day from the first of the *month*
rather than the first of the *quarter*. A quarter end falls in the last month of its
quarter, so 2023-03-31 became 2023-03-01, then 2023-02-28, which resolves to 2023-03-31
again. The function returned its own argument for every quarter end it was given.

The opening balance was therefore always the closing balance, `average_balance` averaged a
figure with itself, and every denominator was a period-end balance while the row recorded
`avg_method = 'endpoint'`. The two-point average 0011 specifies was never computed.

The industry benchmark did not catch it. `aggregate_series` divides summed expense by
summed closing balances and never calls the averaging path, so it could not test the
averaging method that 0014 credits it with testing. That claim in 0014 is wrong and is
corrected here: the benchmark tests units, annualisation and tag mapping, not averaging.

**Effect.** With the defect fixed, G4 fails.

| | Before | After |
|---|---|---|
| Ally Financial, test cycle | 0.681 | 0.677 |
| Zions Bancorporation, test cycle | 0.574 | 0.593 |
| Margin | +0.108 (pass) | +0.085 (fail, threshold 0.10) |

The industry benchmark is unchanged at 0.354 calibration and 0.480 test, because it never
used averaging. Every bank's beta moves by less than 0.015; the ranking is undisturbed.

**Open question.** The contrast G4 exists to detect is present and correctly signed — a
direct bank still reprices faster than the branch-funded regional — but by less than the
threshold set in advance. Three courses, none yet taken:

1. Accept the failure and invoke a fallback from specification 9.2.
2. Judge that the 0.10 threshold was arbitrary and that the benchmark, which 0014 already
   calls the stronger check, carries the validation. This must be argued on its merits and
   not because the number came in low, which is precisely the reasoning the gate exists to
   prevent.
3. Question the comparator rather than the metric. G4 assumes a branch-funded regional is a
   low-beta bank, and in the test cycle that premise is doubtful: Zions at 0.593 sits
   mid-pack, while the genuinely low-beta filers are the branch-funded megabanks, Wells
   Fargo at 0.368 and Bank of America at 0.428. Ally against Wells Fargo is +0.309. Changing
   the comparator after seeing the result is a re-specification and has to be recorded as
   one.

No course is chosen here. AGENTS section 5 requires a failed gate criterion and its chosen
fallback to be recorded before work changes direction, and the choice is not the
implementer's to make alone. Milestone 2 work continues on the panel and tier coverage,
which do not depend on the outcome; nothing that rests on G4 proceeds until this is closed.

---

## 0020 — The completeness check excludes four filers outright; proposal to scale rather than reject

**Date** 2026-09-12
**Status** Proposed. Extends 0013.

**Context.** 0013 introduced a completeness check on reconstructed numerators after M&T
Bank's summed components captured 29 percent of its true deposit expense and produced a
test-cycle beta four times below the next lowest bank. Below 80 percent coverage the
bank-quarter is marked tier X and excluded. That was calibrated on one filer.

Across the fifty-one-filer universe the check fires on 184 bank-quarters and five filers,
and it separates into two clearly different populations:

| Filer | Tier X quarters | Median coverage | Range |
|---|---|---|---|
| M&T Bank | 31 | 0.26 | 0.02 – 0.47 |
| E*TRADE | 3 | 0.07 | 0.00 – 0.34 |
| Valley National | 57 | 0.55 | 0.16 – 0.75 |
| Flagstar | 53 | 0.73 | 0.45 – 0.80 |
| First Horizon | 40 | 0.75 | 0.65 – 0.79 |

M&T and E*TRADE are decisively incomplete and the check is doing exactly what 0013 built it
for. First Horizon is a different case: every one of its forty quarters lands between 0.65
and 0.79, never once clearing the line. Its non-deposit funding is fully tagged — long-term
debt, short-term borrowings and trading liabilities are all present — so the implied figure
the check tests against is sound. It tags time and savings deposit expense but not the
demand, NOW and money-market components, and the missing quarter is real rather than an
artefact of the comparison.

The consequence is that M&T, Flagstar and Valley National carry no headline coverage in
either cycle and First Horizon none in the calibration cycle. Four of fifty-one filers are
lost to this check alone.

**Proposal.** Do not lower the threshold. A reconstruction capturing 75 percent of deposit
expense understates a bank's beta by roughly a quarter, which is the distortion 0013 exists
to prevent, and moving the line to rescue a filer is the same error in the other direction.

Instead add a route that uses implied deposit expense — total interest expense less
identifiable non-deposit funding — as the numerator directly, where the non-deposit funding
list is demonstrably complete for that filer-quarter. This is less precise than a reported
figure and would carry its own provenance and a tier below reported reconstruction, but it
is a measured quantity rather than a truncated sum, and it recovers filers whose only defect
is that they decompose deposit expense incompletely.

**Alternatives.** Lower the threshold to 0.60, which admits First Horizon and most of
Flagstar while knowingly accepting a quarter of the numerator missing, and which was chosen
by looking at the answer. Scale the reconstructed sum up by the inverse of its coverage
ratio, which assumes the untagged components cost the same average rate as the tagged ones —
false, since time deposits reprice fastest and are the component most often tagged. Exclude
the four filers and state the loss, which is the status quo.

**Open.** Not decided. The proposal changes the tier hierarchy and the published sample, so
it belongs with the metric definition in specification 3.1 rather than in an implementer's
judgement. Nothing downstream is built on it yet.

---

## 0021 — Complete the concept lists rather than add an implied-expense route

**Date** 2026-09-13
**Status** Accepted. Supersedes the proposal in 0020.

**Context.** 0020 proposed using implied deposit expense — total interest expense less
identifiable non-deposit funding — as a numerator where component reconstruction fell below
the completeness floor. That proposal was tested before being built and it fails.

Across 2,524 bank-quarters where a reported deposit expense exists to check against, the
implied figure matches it within two percent only 48.8 percent of the time, and the upper
tail is severe: the ninetieth percentile of implied over reported is 1.914. The bias is not
confined to broker-dealers, though those are worst — E*TRADE at 14.0, Raymond James at 5.25,
Morgan Stanley at 4.32. Ordinary commercial banks are affected too: Zions at 1.71, Northern
Trust at 1.96, Huntington at 1.63. Implied deposit expense is unusable as a numerator.

The same measurement explains why. The non-deposit funding list, drawn from a twelve-bank
sample, omitted the funding sources the wider universe actually uses. Federal Home Loan Bank
advances appear for eleven filers across 1,212 facts and were never subtracted. So do
repurchase agreements, other short-term borrowings, junior subordinated debentures,
commercial paper and federal funds purchased. Subtracting too little leaves implied deposit
expense too high, which makes a complete reconstruction look short.

The deposit component list was incomplete in the same way, and that is the direct cause of
the exclusions 0020 was trying to rescue. First Horizon tags `InterestExpenseOtherDomesticDeposits`
across 139 facts and it was never summed: at 2019Q4 its time and savings components total
$49.6m against a reported $67.2m, and the missing $17.6m is exactly that concept. Valley
National publishes one combined `InterestExpenseNOWAccountsMoneyMarketAccountsAndSavingsDeposits`
concept across 216 facts, also never summed, leaving only time deposits captured.

**Decision.** Extend both lists to the concepts the universe uses, and resolve deposit
expense by mutually exclusive category rather than by summing every concept present. Within
a category the filer's own total is preferred where it publishes one, and otherwise the leaf
concepts present are summed. Totals and leaves are never added together, because several
filers tag both and summing everything would double count — the opposite of the
understatement the completeness check guards against.

**Alternatives.** The implied-expense route, refuted above. Lowering the floor to 0.60,
which would have admitted understated numerators while leaving the real cause untouched.

**Consequences.** Tier X falls from 184 bank-quarters to 71 and from five filers to five
with far smaller counts. Valley National is fully recovered, 57 excluded quarters to none.
First Horizon falls from 40 to 3. Flagstar falls from 53 to 32. M&T is unchanged at 31,
which is the right outcome: 0013 established its reconstruction genuinely captures as little
as 2 percent, and the completeness check was never wrong about it.

The headline sample does not change. Recovered quarters are tier 3, and specification 3.1
runs headline results on tiers 1 and 2 only, so the persistence sample stays at 37 filers.
The gain is to the robustness analysis and to the honesty of the data health page, not to
the headline.

Gate criterion G4 is unaffected: Ally and Zions both resolve at tier 1 from reported
concepts, and their betas are unchanged to three decimal places. Whatever is decided about
G4 cannot be an artefact of this change.

---

## 0022 — Record G4 as failed and replace it with a cross-sectional test

**Date** 2026-09-13
**Status** Accepted. Closes 0019.

**Context.** 0019 recorded G4 failing at +0.085 against a threshold of 0.10 once endpoint
averaging was actually applied. The margin is robust: completing the concept lists under
0021 left both betas unchanged, so the failure is not a data-completeness artefact.

G4 asks whether the metric measures repricing behaviour or reporting differences, by
comparing a direct bank against a branch-funded regional. Its premise is that a
branch-funded regional is a slow repricer. Measured across the universe that premise fails
on its own terms for the test cycle. Zions carries the second-highest non-interest-bearing
deposit share of any filer with a headline-tier beta, 44.6 percent, and still reprices at
0.612, mid-pack. The genuinely slow repricers are Wells Fargo at 0.409 and Regions at 0.401.
G4 selected as its low-beta exemplar a bank that is an outlier against the relationship it
was standing in for.

**Decision.** G4 is recorded as **failed** and is not revised, rethresholded or
recomparatored. The pass recorded on 2026-09-08 is withdrawn.

It is replaced, for construct validity going forward, by a cross-sectional test of the same
economic hypothesis across the whole universe, using a reported characteristic rather than a
hand-assigned funding label. Non-interest-bearing deposits pay nothing by construction and
are stickier than rate-seeking money, so a bank funded by more of them has less of its base
to reprice. The prediction, fixed before measurement, is a negative rank correlation against
cumulative deposit beta.

**Result.** Spearman −0.358 across the 30 filers carrying a headline-tier test-cycle beta, a
reported deposit split and a beta at or below 1.0; −0.409 across all 32 before excluding
implausible betas. Negative as predicted.

**Why this is not moving the goalposts.** The failure is recorded permanently rather than
erased, and the replacement is not a rerun of the same comparison with friendlier inputs. It
was specified with a directional prediction before being computed and could have come back
flat or positive, which would have corroborated the failure rather than dissolved it. It
rests on 30 filers instead of 2, and on a reported balance-sheet split rather than a
judgement about which bank typifies which funding model — the judgement that G4 got wrong.
The industry benchmark, which 0014 already calls the stronger check, continues to pass at
0.354 and 0.480.

This reasoning is recorded because the move is legitimately suspicious and a reader is
entitled to test it. The honest summary is that G4 was a weak test, it failed, and the
project now has a better one.

**Consequences.** Specification 9.1 records G4 as failed with the replacement criterion and
its result alongside. No fallback from 9.2 is invoked: fallbacks exist for a metric that
cannot be constructed, and the evidence is that it can be. Two filers, Santander Holdings
USA at 2.941 and Raymond James at 1.695, return betas above 1.0 and are carried as an open
data quality finding for Milestone 2 rather than silently dropped.

---

## 0023 — Adopt the derived cycle windows as they fall

**Date** 2026-09-25
**Status** Accepted

**Context.** Specification section 2 requires the cycle windows to be derived from the
federal funds series rather than hardcoded, and `dim_rate_cycle` now does so. Until now the
analysis scripts each pinned their own windows, and they did not agree with one another:
the test cycle ended at 2023Q3 in the gate script and at 2023Q4 in the tier coverage and
construct validity scripts.

The derivation does not reproduce the pinned windows exactly. It places the test cycle at
2022Q1 to 2023Q4, matching two of the three scripts. It ends the calibration cycle at
2019Q1, a quarter before the 2019Q2 the specification pinned, because the quarterly average
of the monthly effective rate is 2.403 percent in 2019Q1 and 2.397 percent in 2019Q2. The
last hike of that cycle was in December 2018, so 2019Q1 is the first full quarter at the
peak, and the rule is right by its own definition. It also means the specification's
window was a judgement that happened to include one more quarter.

The test cycle peaks on a plateau, 2023Q4 to 2024Q2 at 5.33 percent. The rule ends the
cycle at the first quarter of the plateau, consistent with specification 3.2, which
measures a beta from cycle start to cycle peak.

**Test.** Before adopting the windows, `analysis/milestone2/cycle_sensitivity.py` shifts
each derived boundary one quarter either way and compares the resulting headline-tier
betas with the derived ones by Spearman rank correlation across the filers both windows
can measure. The shifts cover both of the old pinned ends without choosing them by hand.

| Cycle | Shift | Filers | ρ, all | ρ, plausible betas |
|---|---|---|---|---|
| Calibration | start 2015Q3 | 43 | 0.976 | 0.996 |
| Calibration | start 2016Q1 | 43 | 0.997 | 0.997 |
| Calibration | end 2018Q4 | 43 | 0.892 | 0.884 |
| Calibration | end 2019Q2, the old pinned end | 43 | 0.960 | 0.957 |
| Test | start 2021Q4 | 40 | 0.992 | 0.990 |
| Test | start 2022Q2 | 40 | 0.994 | 0.993 |
| Test | end 2023Q3, the gate script's end | 40 | 0.876 | 0.984 |
| Test | end 2024Q1 | 40 | 0.878 | 0.979 |

A plausible beta lies between 0 and 1: above 1 is the ceiling the construct validity check
already applies, and below 0 means deposit cost fell across a tightening cycle.

Only within-cycle ordering was compared. The cross-cycle persistence correlation, which
these windows exist to feed, was not computed under any alternative, so no window could be
chosen by how the headline comes out.

**Decision.** Adopt the derived windows as they fall: calibration 2015Q4 to 2019Q1, test
2022Q1 to 2023Q4. Analysis from Milestone 2 onward reads both from `dim_rate_cycle` through
`marketscope.cycles` and pins no window of its own. The Milestone 0 scripts keep their
pinned windows unchanged, since they are the record of what the gate measured.

**Alternatives.** Keep 2019Q2 as a hand override. The ordering barely differs, at 0.960,
and an override would reintroduce exactly the per-script judgement section 2 exists to
remove. End the test cycle at 2023Q3 to keep a fourth quarter out of the endpoint. Its
disagreement with the derived end comes from one filer, below, and moving a boundary to
avoid one bad value is fixing data by moving the window. End at the last quarter of the
plateau. Deposit costs keep rising after the policy peak, so a later end lifts the median
beta, from 0.575 to 0.587 a quarter on, but section 3.2 defines the beta to the peak and the
ordering holds at 0.979.

**Consequences.** The calibration cycle loses a quarter, fifteen to fourteen, which moves
the tier coverage floor every filer is tested against. Tier coverage is rerun against the
derived windows. The construct validity window was already 2022Q1 to 2023Q4 and does not
change.

The one fragile comparison is ending the calibration cycle a quarter before the peak, at
0.884. That is an argument for the rule rather than against it: 2018Q4 is not a turning
point, and cutting a cycle before the rate has finished moving is the kind of choice that
changes the answer.

The test-cycle end comparisons fall to 0.876 and 0.878 across all filers because Bank of
New York Mellon's derived 2023Q4 cost of deposits is −0.57 percent, between 3.46 percent in
2023Q3 and 3.71 percent in 2024Q1. Its 2024Q4 and 2025Q4 values are negative too, so the
fourth-quarter derivation fails for this filer and the fault is not in the window.
Specification 7.2 already requires derived Q4 values to be non-negative and within band of
neighbouring quarters. That check is not yet built and has now found its first case. It is
carried as an open Milestone 2 data quality finding alongside the Santander and Raymond
James betas above 1.0 recorded in 0022.

Two endpoints in the design, the calibration start and the test end, are fourth quarters
and therefore derived as fiscal year less nine months. This follows from where the rate
turned and is not chosen, but it means those endpoints carry whatever error the
derivation carries.

---

## 0024 — Resolve the deposit panel in a dbt Python model, not in SQL

**Date** 2026-09-30
**Status** Accepted. Amends the model layout in specification 7.1.

**Context.** Milestone 2 exits when `fct_deposit_beta` is populated with tiers. Specification
7.1 lays the path to it out as SQL models — `int_fact_precedence`,
`int_deposit_expense_harmonised`, `int_deposit_balance_harmonised`, `int_bank_quarter_panel`
and `int_deposit_cost` — which implies reimplementing the metric in SQL. The metric already
exists in Python: restatement precedence and fourth-quarter derivation in
`marketscope.facts`, the quarterly panel in `marketscope.panel`, and the tiers, resolution
routes, category-wise reconstruction and completeness check in `marketscope.metrics`. Every
Milestone 0 and Milestone 2 result was produced by that code and it carries the project's
unit tests.

**Decision.** `int_deposit_cost` is a dbt Python model. It reads the panel concepts from
`stg_sec__company_facts` and hands them to `marketscope.deposit_cost`, which builds each
filer's panel and resolves every bank-quarter through the same functions the analysis
scripts call. The four intermediate SQL models that would have reimplemented those steps are
not built. `fct_deposit_beta` and everything downstream of the resolved bank-quarter stay in
SQL, where cycle windows and cross-bank joins belong.

**Evidence.** Built against the current warehouse, the model reproduces the tier coverage
script's output exactly: 3,066 bank-quarters across 51 filers, every tier, provenance and
averaging method identical, and costs equal to within 1e-16. The model runs in about five
seconds.

**Alternatives.** Reimplement the metric in SQL as the layout specifies. That produces two
implementations of a definition that changed three times during Milestone 0 and once during
Milestone 2 (0011, 0012, 0013, 0021), and each change would then have to be made twice and
kept in step by nothing stronger than a parity test. The category-wise reconstruction, the
refusal of a partial non-interest-bearing residual and the tiled-quarter Q4 derivation are
all awkward in SQL and are exactly where a silent divergence would land. Alternatively, a
standalone Python step writing the panel into the raw schema for dbt to read as a source.
That keeps one implementation too, but puts derived data in a schema whose contract is that
it holds endpoint payloads and nothing else, and moves the step outside the DAG, so a
`dbt build` could run on a panel resolved from an older load.

**Consequences.** The metric has one implementation and one set of unit tests, and dbt
tests its output: tier values, provenance values, one row per bank-quarter, and the 0 to 8
percent range from specification 7.2 at warn severity. The price is that the intermediate
steps are not separately materialised, so a harmonised expense or balance cannot be queried
in the warehouse on its own; the tier coverage script remains the place to inspect them.
dbt Python models require the `marketscope` package in the environment dbt runs from, which
the project's own install already provides. `mypy` now covers `transform/dbt/models` so the
model is checked like the rest of the code.

The range test fires on its first run, on 55 bank-quarters. It catches both open findings
already carried — Santander Holdings USA and Raymond James above 8 percent from 2023, and
Bank of New York Mellon's negative derived fourth quarters — plus Flagstar's tier 3 costs
above 8 percent from 2024, and small negative costs of at most 0.16 percent at State
Street, Northern Trust and Citigroup between 2020 and 2022. The last group is probably
genuine rather than a fault: custody banks passed negative euro and yen rates on to foreign
depositors in those years. None is resolved here.

---

## 0025 — Band derived fourth quarters against the range of their neighbours

**Date** 2026-10-02
**Status** Accepted

**Context.** Specification 7.2 requires a derived fourth quarter to be non-negative and
"within band of neighbouring quarters" without saying what the band is. With `q4_derived`
now on `int_deposit_cost`, the test can be written, and the band has to be chosen.

A threshold calibrated on every reported quarter is contaminated. A first and a third
quarter each have a derived fourth quarter as one neighbour, so a faulty Q4 makes its
reported neighbours look like outliers too: BNY Mellon's 2023Q3 and 2024Q1 sit more than
two points from the midpoint of their neighbours only because 2023Q4 is −0.57 percent.
Only a second quarter has two reported neighbours.

**Decision.** Measure how far a quarter lies outside the range of its two neighbours,
which is zero for any quarter lying between them, so a quarter on a steady trend is never
flagged however fast rates move. Across the 693 second quarters with two reported
neighbours the largest such distance is 0.33 percentage points. The band is set at one
percentage point, three times that. A derived fourth quarter is flagged if it is negative,
or if it lies more than one point outside its neighbours' range. The test warns rather
than fails, like the other plausibility tests.

**Alternatives.** Distance from the neighbours' midpoint, which flags a quarter on a
steep trend and, calibrated on all reported quarters, sets a threshold inflated by the
faults it exists to catch. A ratio band on the neighbours, which is unstable where costs
are near zero, as they were in 2020 and 2021. A percentile of the clean distribution
rather than a multiple of its maximum. The 99.9th percentile of 693 observations sets the
line at 0.18 points and is tighter than the data supports.

**Consequences.** Fourteen derived quarters are flagged. Three are BNY Mellon's negative
fourth quarters of 2023 to 2025, the case recorded in 0023. Five are new: Santander
Holdings USA at 2.61, 2.67, 1.90 and 3.20 percent in the fourth quarters of 2011 to 2014,
against neighbours near 0.5 percent, and CIT Group at 3.58 percent in 2014Q4 against
neighbours of 1.67 and 1.69. All five fall before the calibration cycle and feed no beta.
The remaining six are negative fourth quarters in 2020 and 2021 at State Street, Northern
Trust, BNY Mellon and Citigroup, caught by the non-negativity rule rather than the band.

That last group corrects the methodology as first written, which stated that none of the
small negative costs of 2020 to 2022 fell in a fourth quarter. Six do. At State Street,
Northern Trust and BNY Mellon the neighbouring quarters are negative or near zero too, so
the derivation is not the likely cause and the negative-rate explanation stands. Citigroup
is less clear: its 2020Q4 is −0.02 percent between neighbours of 0.50 and 0.27, inside the
band but not consistent with them, and is left open.

---

## 0026 — Use a reported fourth quarter wherever one exists

**Date** 2026-10-03
**Status** Accepted. Refines the derivation in specification 4.

**Context.** 0023 and 0025 carried BNY Mellon's negative derived fourth quarters, among them
−0.57 percent at 2023Q4, the endpoint of its test-cycle beta, as a derivation failure with
an undiagnosed cause. The cause is a difference of scope between two forms that use the
same concept. BNY Mellon's 10-Qs tag total deposit interest expense as
`InterestExpenseDeposits`. Its 10-K tags deposits in domestic offices under that concept and
deposits in foreign offices under `InterestExpenseForeignDeposits`. From 2019 to 2022 the
two annual figures sum exactly to the four reported quarters: $958m and $636m against
$1,594m in 2019, $980m and $607m against $1,587m in 2022. Fiscal year less nine months
therefore returns the fourth quarter's domestic expense less nine months of foreign
expense.

The fourth quarter was never missing. BNY Mellon reports it as a comparative in the next
first-quarter 10-Q, so a reported 2023Q4 of $2,108m was in the warehouse throughout.
`build_panel` applied derived quarters after reported ones, and the derived value
overwrote it.

**Decision.** Where any filing reports a fourth quarter directly, that value is used.
Derivation runs only where none does. It exists to supply an absent figure, not to compete
with a published one.

**Alternatives.** Refuse a derived quarter that comes out negative. Negative deposit
interest expense is genuine at the custody banks in 2020 and 2021 — BNY Mellon itself
reports −$45m for 2021Q4 — so the rule would discard real values while leaving a
mis-scoped positive derivation in place. Read the annual figure as domestic plus foreign
wherever both are tagged. That rebuilds one filer's 10-K presentation inside the
derivation and needs a rule for every other split a filer might use, where a reported
quarter settles the question outright wherever one exists.

**Consequences.** Twenty-five derived quarter values across four filers have a reported
counterpart. BNY Mellon's eleven disagree with it in every year, by between 45 and 500
percent. The other fourteen, ten at PacWest, three at Flagstar and one at CIT, agree
exactly. Seventeen bank-quarters in `int_deposit_cost` change from derived to reported,
leaving 743 of 3,066 derived. Five costs change, all BNY Mellon's from 2020Q4 to 2024Q4:
2023Q4 moves from −0.57 to 3.81 percent and the test-cycle beta from −0.097 to 0.744. The
three warn-severity tests fall from 55, 14 and 5 rows to 54, 11 and 4.

BNY Mellon's 2025Q4 has no reported counterpart yet and is still derived, at −0.74
percent, and the derived-quarter test still flags it. It feeds no beta. Any year in which
no 10-Q reports the fourth quarter will derive wrongly for this filer, because the scope
difference is in its 10-K. That is recorded rather than special-cased.

The analysis outputs that read the affected quarters, among them the cycle sensitivity in
0023, are rerun after this change rather than restated here.

---

## 0027 — Refuse an interest-bearing base that does not reconcile to total deposits

**Date** 2026-10-03
**Status** Accepted. Refines 0012. Resolves the betas above 1.0 carried by 0022 and the
costs above 8 percent carried by 0024.

**Context.** Three filers' costs of deposits rose steadily past 8 percent from 2023 and
stayed there, and Santander Holdings USA and Raymond James returned test-cycle betas of
2.941 and 1.695. The cause is the same in each case. The filer tags one line of its
deposit table under `InterestBearingDepositLiabilities`, the concept 0012 reads as the
whole interest-bearing base. At 2023Q4 Santander tags $11.6bn against $77.1bn of deposits,
of which $15.5bn pay no interest, so its cost of deposits was measured on about a fifth of
the $61.6bn base and came out at 15.78 percent. Flagstar tags $30.7bn, exactly its
money-market line, against an interest-bearing base of $61.0bn. Raymond James's tagged
figure covers between 10 and 40 percent of its base in every quarter it appears. US
Bancorp, until 2015Q3, tagged interest-bearing deposits excluding time deposits of
$100,000 or more, which it tagged separately: at 2015Q3, $185.9bn interest-bearing, $83.5bn
non-interest-bearing and $25.9bn of large time deposits sum exactly to $295.3bn of
deposits.

Interest-bearing and non-interest-bearing deposits partition total deposits. A base that
leaves part of the total unaccounted for is therefore not the base, and the filer's own
figures say so wherever all three are tagged.

**Decision.** Wherever a filer tags total deposits and a complete non-interest-bearing
figure, a reported or summed interest-bearing base must reconcile with them to within 2
percent of total deposits. A base that does not is passed over for the next route in
0012's order, which for every case found is the residual, total deposits less
non-interest-bearing deposits. A base that cannot be checked is used as reported.

**Evidence for the tolerance.** A reported base can be checked in 1,576 period ends across
the universe. 1,482 reconcile to within 0.1 percent and the other 94 miss by more than 8
percent. Nothing falls between, so any tolerance from 0.1 to 8 percent selects the same
quarters and the 2 percent figure carries no weight. The 94 are Santander's 47, US
Bancorp's 17, Raymond James's 15, Flagstar's 14 and one Synovus quarter in 2011. Summed
domestic and foreign components can be checked in 375 period ends. HSBC USA's four
quarters from 2011Q3 to 2012Q2 miss by 3 to 11 percent and are refused. Its 2017Q3 and
2017Q4 miss by under 1 percent and pass.

**Alternatives.** Mark the affected quarters tier X. The filer's own total and
non-interest-bearing figures already give the right base, and excluding a measurable
quarter discards it for no gain. Treat any cost above 8 percent as missing. That fixes a
symptom by moving a threshold, and a mis-scoped line covering 90 percent of the base would
pass under it unnoticed. Use the residual wherever it is available and ignore the reported
concept. Where the reported base reconciles the two agree to within 0.1 percent anyway, so
this changes no value, but it would record a derived figure where the filer published one.

**Consequences.** 98 bank-quarters change route, 94 from a reported base and HSBC's four
from summed components, and 104 costs change, the other six through the opening balance
of the following quarter. No tier changes, because every refused base resolves to the
residual at the same tier. Every beta outside 0 to 1 is resolved.

| Filer | Cycle | Before | After |
|---|---|---|---|
| Santander Holdings USA | Calibration | 1.453 | 0.240 |
| Santander Holdings USA | Test | 2.941 | 0.548 |
| Raymond James | Test | 1.695 | 0.601 |
| Flagstar, tier 3 | Test | 1.295 | 0.647 |
| US Bancorp | Calibration | 0.361 | 0.367 |

US Bancorp moves through its opening balance: its calibration cycle starts at 2015Q4, and
2015Q3 was the last quarter its reported base excluded large time deposits.

The cost range test falls from 54 bank-quarters to 24, all of them negative, and the beta
range test from 4 rows to none. The derived fourth-quarter test falls from 11 to 7, which
corrects 0025: Santander's fourth quarters of 2011 to 2014 were not a derivation failure.
Its 10-K year-end balances tagged the single line while its 10-Qs did not until 2016, so
only the fourth quarters were inflated.

The check cannot be made on 167 bank-quarters, because the filer tags no total or no
complete non-interest-bearing figure: Regions 45, KeyCorp 28, BNY Mellon 25, SunTrust 25,
HSBC USA 22, Truist 20 and CIT 2. Regions and SunTrust tag interest-bearing shares of 62
to 80 percent of total deposits, which is plausible. CIT's two are not. At 2014Q4 and
2015Q3 its tagged figure is 45 and 26 percent of deposits at a lender funded almost
entirely by interest-bearing deposits, and at 2015Q3 it is below CIT's own time deposits,
which cannot be true of the whole base. They are very likely the same fault, and this rule
cannot refuse them. 2014Q4 is CIT's derived fourth quarter flagged under 0025. Neither
quarter is a beta endpoint.

---

## 0028 — Record revisions as changes of value within a load, and defer the raw snapshot

**Date** 2026-10-05
**Status** Accepted. Amends the model layout in specification 7.1.

**Context.** Specification 4 requires the values restatement precedence discards to be
kept in a separate table so restatement magnitude can be measured, and 7.1 plans a dbt
snapshot on the raw fact table to capture restatements over time. Neither existed.
`marketscope.facts.superseded` could list the discarded values, but nothing called it, and
it returned every value other than the current one. That includes every comparative
column, which republishes a value unchanged. Of 946,834 us-gaap periods in the warehouse,
506,522 are reported more than once and 44,829 change value. A table of everything not
current would be dominated by repeats and would make every period look restated.

**Decision.** `int_fact_revisions` holds one row per change of value: the value in force
and the filing that first published it, and the replacing value and the filing that first
published that. It is a dbt Python model calling `marketscope.restatements`, and
`marketscope.facts.revisions` replaces `superseded`. Revisions are ordered by the same
precedence `latest_filed` applies, so the last revision of a period ends on the value the
panel uses, and a dbt test requires exactly one such row per revised period.

The table covers us-gaap, where the financial statements are tagged. Outside it, 18,978 of
19,022 changes were filing-fee facts from prospectus supplements, where every note offered
on a date reports its own amount against the same instant and separate offerings read as
revisions of one fact.

The raw snapshot is not built. The company facts endpoint keeps the value from every filing
that reported a period, comparatives and amendments included, so one load already holds the
revision history of everything EDGAR publishes. A snapshot would add only changes to the
endpoint's own content between loads, such as a fact withdrawn, and nothing yet needs that.
It is deferred, not dropped: if the scheduled refresh at Milestone 6 shows the endpoint
changing past values, it becomes necessary.

**Alternatives.** Window functions in SQL. That is a second implementation of precedence
that could disagree with the panel's without anything noticing; sharing the ordering
function makes disagreement impossible. Keeping every non-current value, as `superseded`
did, which buries 48,206 changes under half a million repeats. Building the snapshot now as
7.1 specifies, which costs a stateful table in a project whose raw layer is otherwise
replaced on every load, to capture something not yet observed.

**Consequences.** 48,206 revisions across 44,829 periods at all 51 filers. 2,883 periods
are revised more than once, at most nine times. The metric's own concepts account for
1,167 revisions across 1,124 periods at 47 filers.

A revision is a change of published value, not necessarily a correction. Most are first
carried by an ordinary filing — 27,400 by a 10-Q and 17,870 by a 10-K — against 553 by a
10-K/A and 903 by a 10-Q/A. They include reclassifications, recasts after an acquisition or
a change of segments, and the adoption of new accounting standards, and the table alone
cannot tell those from error corrections. Classifying them is the first task of the
secondary question, and nothing is claimed here about how often filers restate.

---

## 0029 — Extension namespaces were never searched; narrow the averaging finding

**Date** 2026-10-05
**Status** Accepted. Corrects the evidence recorded in 0011, whose decision stands.

**Context.** 0011 records that Milestone 0 scanned every taxonomy present for the twelve
sample filers, "including each filer's own extension namespace", and found no average
deposit balance. The methodology, specification 3.1 and comments in the pipeline, the
fact extraction and the panel say the same thing, and the pipeline's docstring justified
loading every taxonomy by the extension concepts it would capture.

The company facts endpoint publishes no extension namespace. The 1,809,702 facts loaded
for 51 filers come from six taxonomies — us-gaap, ffd, invest, dei, srt and ecd — and none
is a filer's own, although the pipeline loads every taxonomy a payload carries. The
Milestone 0 scan read the same payloads, so it could not have found an extension concept
had one existed. The statement was a belief about what the endpoint returns, written up as
a finding, and nobody checked it until the restatement work listed the taxonomies in the
warehouse.

**Decision.** The finding is narrowed to what was searched: no filer tags an average
deposit balance in any taxonomy the endpoint publishes. Whether filers tag averages under
their own concepts is unknown. Every document and comment that says otherwise is
corrected.

Endpoint averaging stands. A filer's own average concept, if it exists, is reachable only
through each filing's XBRL instance or the SEC's Financial Statement and Notes data sets,
which carry custom tags, and would have to be identified filer by filer. Until then no
reported average can reach the pipeline whatever the answer.

**Alternatives.** Search the extension namespaces now, through the Financial Statement and
Notes data sets. Worth doing, but the question it answers is narrower than the one that
matters, which is how far endpoint averaging misses the true average. Specification 5
already measures that against the true averages in regulatory filings at Milestone 3, and
that measurement holds whether or not any filer tags an average.

**Consequences.** No figure changes. The taxonomy pin in the panel keeps its place for a
different reason than the one recorded: eight concept names in the warehouse, among them
`NetCapital` and `DerivativeNotionalAmount`, are tagged under both us-gaap and srt or
invest, and one name in two taxonomies is two concepts. Tests that used a hypothetical
filer namespace now use srt, which is a case the data contains.

---

## 0030 — Keep the most recently filed value: the precedence rule does not carry the result

**Date** 2026-10-06
**Status** Accepted. Confirms the precedence rule in specification 4.

**Context.** Specification 4 resolves a period reported with different values by taking the
most recently filed one. The revision audit shows the rule accepting more than corrections.
Columbia Banking's filings since its 2023 reverse merger report Umpqua's history as its own,
so the rule replaces Columbia's 2022 figures with Umpqua's, and because a 10-Q restates the
comparative quarter's expense but not that quarter's balance sheet, a 2022 quarter can
divide Umpqua's expense by Columbia's balances. A 2025 Raymond James 10-Q reports 2024Q1's
deposit expense, $441m, against 2023Q1 as well, replacing the $206m that had stood since
2023. A rule that accepts these could be shaping results, and that had not been measured.

**Test.** `analysis/milestone2/precedence_sensitivity.py` resolves every bank-quarter twice,
on the most recently filed value of each period and on the value as first published, and
compares headline-tier betas within each cycle. The cross-cycle persistence result is not
computed under either rule.

| | Calibration | Test |
|---|---|---|
| Filers with a beta under both rules | 43 | 40 |
| Spearman, latest against original | 1.000 | 0.999 |
| Median beta, either rule | 0.319 | 0.575 |
| Betas moving by more than 0.01 | 0 | 1 |

51 of 2,814 headline bank-quarters differ by more than a basis point between the rules, and
none resolves under one rule but not the other. The one beta that moves is Columbia's
test-cycle beta: 0.459 on the latest figures, 0.476 on the originals.

**Decision.** The most recently filed value continues to win. The rule does not carry the
result, and it is the only one that admits a genuine correction.

**Alternatives.** The value as first published, which is immune to a later filing's
mistakes but discards every correction and recast with them, and measures the same ordering.
A rule that refuses a revision whose replacing value the same filing also reports for
another period, which is the signature of Raymond James's mis-dated quarter. Among
substantive revisions to the metric's concepts it fires seventeen times, and most are small
figures rounding to the same whole million in two periods, so it cannot tell a mis-dated
context from a coincidence and would be built for one case.

**Consequences.** Raymond James's 2023Q1 cost of deposits stays at 3.36 percent where the
original figure gives 1.57, between neighbours of 1.35 and 2.34 percent. It is not a beta
endpoint and is recorded rather than corrected. Columbia's test-cycle beta is unreliable
under either rule, because the entity changed inside the cycle. That is an entity
continuity problem and is handled as one, by the entity events table specification 4
already requires, rather than by the precedence rule.

---

## 0031 — Curate entity events by hand and cite the filing behind each

**Date** 2026-10-07
**Status** Accepted

**Context.** Specification 4 requires a table of mergers, acquisitions, CIK changes and
failures, so that bank-quarters an event touches can be flagged and a bank with a material
acquisition inside a cycle shown separately. XBRL records none of these. The revision audit
has already shown what an unrecorded event does: Columbia Banking's filings since its 2023
reverse merger report Umpqua's history as Columbia's own, and nothing in the warehouse said
so.

**Decision.** Events are curated by hand in a dbt seed, `entity_events`, and every row cites
the filing that reports it. `analysis/milestone2/entity_event_audit.py` checks each citation
against the filer's EDGAR history: the accession must belong to the filer, carry the form
and 8-K item cited, and have been filed between two days before the event and six days
after it, which covers the four business days an 8-K is due within.

The scope is events from 2015 that change a member's deposit base or end its reporting:
acquisitions of deposit-taking institutions or their deposits, including three purchased
from the FDIC as receiver; one reverse acquisition; seven exits by merger; one
deregistration; and one failure. Forty-four events, thirty-six evidenced by an 8-K Item 2.01
completion report, four by an Item 8.01 press release announcing completion, two by a Form
15, one by an Item 1.03 receivership report, and one, Citizens' acquisition of Investors
Bancorp, by an 8-K announcing the expected closing date because no completion report was
filed. That last is the weakest evidence in the table and is noted on the row.

Out of scope: acquisitions that brought no deposits, such as Morgan Stanley's of Eaton
Vance; branch purchases and sales; and changes of name or structure under an unchanged CIK,
such as BB&T becoming Truist or Zions merging its holding company into its bank in 2018,
where the filer and its reported history continue unbroken. No member changed CIK. Goldman
Sachs' 2016 purchase of GE Capital Bank's online deposits was considered and left out,
because no Goldman filing reporting it could be found.

**Alternatives.** Infer events from steps in reported deposits. That detects that something
happened but neither names nor dates it, and the deposit surge of 2020 produces steps no
acquisition caused. Take the history of each institution from the FFIEC's National
Information Center, which is the regulatory record of mergers. It is keyed on RSSD rather
than CIK and, as 0016 found, the FFIEC's bulk data sits behind a CAPTCHA. It remains the
natural check when regulatory data is ingested at Milestone 3.

**Consequences.** A dbt test requires every member whose last 10-K or 10-Q is more than a
year older than the newest in the load to carry an exit or failure event, so a filer leaving
the data cannot pass for a coverage gap. Nine qualify and all nine have one. A second test
refuses an exit dated before the period of the filer's last periodic report.

The table is maintained by hand, so an event after the last edit is missing until someone
adds it. The terminal-filer test catches an unrecorded exit at the next load; an unrecorded
acquisition by a member that keeps filing is caught by nothing yet. The deposit step each
event produced is measured in the next change, which also gives an acquisition that was
never recorded a way to show up.

MUFG Americas Holdings left EDGAR by deregistering in October 2021, after its 2021Q2 10-Q,
and not when its bank was sold to U.S. Bancorp in December 2022. Its exit is recorded at the
deregistration.

---

## 0032 — Measure each event by the deposit step it produced; a tenth is material

**Date** 2026-10-07
**Status** Accepted. Extends 0031.

**Context.** Specification 4 requires a bank with a material acquisition inside a cycle to
be shown separately, and 0031 recorded the events without measuring any of them. Deal
announcements quote the target's assets, which are not in the warehouse, would be one more
hand-entered figure, and are not the quantity that matters. What moves a beta is the share
of the acquirer's deposit base the acquisition brought in.

**Decision.** Each acquisition is measured by the step in the member's total deposits from
the quarter end before it completed to the quarter end it completed in. Balances come from
`int_deposit_balances`, a new Python model holding the deposit base at every quarter end a
filer reports it, resolved by the same library functions as the cost of deposits. It exists
because `int_deposit_cost` holds only quarters where a cost resolves: Schwab reports
deposits throughout 2020, but no cost resolves before 2021, and its TD Ameritrade
acquisition closed in that gap.

An acquisition is material if the step is a tenth or more. A step that cannot be measured
counts as material, because a size that cannot be read is not evidence of a small one.
`fct_deposit_beta.material_event_in_cycle` flags a beta when a material acquisition
completed in any quarter from the cycle's start to its measured end, the start quarter
included because its average balance straddles the completion.

**Evidence for the threshold.** Of 42 acquisitions, four moved the base by less than 9
percent: First Republic at JPMorgan by 0.9 percent, Suffolk at People's United by 4.3,
National Penn at BB&T by 5.8 and First Connecticut at People's United by 8.9. The other 38
moved it by 11.4 percent or more. Any line between 9 and 11 percent selects the same events.
The scale is right for the purpose: acquired deposits that are a tenth of the base and cost
one percentage point more than the acquirer's move the end-point cost by a tenth of a point,
about 0.02 of a test-cycle beta.

**What the measurement exposed.** Every quarter since 2015 in which deposits stepped by more
than 15 percent with no recorded event to explain it was checked for a completion filing.
Nine events had one and were missing from the seed: CIT's acquisition of OneWest and Western
Alliance's of Bridge Capital in 2015; PacWest's of Square 1, which closed in PacWest's
calibration start quarter; Columbia Banking's of Pacific Continental in 2017 and of Pacific
Premier in 2025; Fifth Third's of Comerica and Huntington's of Cadence Bank in February
2026; and the exits of Comerica and Synovus, both universe members, on 1 February and 1
January 2026. All nine were verified against the filing text and added. The seed holds 53
events, and the audit supports all 53.

Comerica and Synovus last filed a 10-Q for 2025Q3. The terminal-filer test of 0031 waited
until a filer's last periodic report was a year older than the newest, so it would not have
caught either until late 2026. It now waits six months, two missed quarterly reports, and
eleven members are terminal.

Large steps remain with no completion filing to explain them: the deposit surge of 2020 at
many filers; Santander Holdings USA in 2015Q4 and 2016Q3; Goldman Sachs in 2016Q2, the
quarter it bought GE Capital Bank's online deposits, which no Goldman filing reports;
E*TRADE in 2017Q1; Ameriprise in 2022Q3; and BNY Mellon in 2026Q1. None is recorded as an
event, because a recorded event has to cite its evidence.

**Alternatives.** Size each acquisition from its announcement, rejected above. A lower line,
such as 5 percent, which flags National Penn and Suffolk without any gap in the data to
justify it. Flagging every acquisition inside a cycle regardless of size, which would set
JPMorgan's test-cycle beta apart for an acquisition that moved its base by 0.9 percent.

**Consequences.** 38 acquisitions are material. In the calibration cycle the flag falls on
ten filers, nine of which have a beta; in the test cycle on nine, eight of which have one.
Columbia Banking's test-cycle beta is flagged through Umpqua, the reverse acquisition behind
the mixing recorded in 0030. The step includes any organic change in the same quarter, so it
overstates an acquisition completing during a surge, which errs towards flagging.

---

## 0033 — Close Milestone 2 and move bank-quarter event flags to Milestone 4

**Date** 2026-10-09
**Status** Accepted

**Context.** Milestone 2 exits when `fct_deposit_beta` is populated with tiers. It is: 102
rows, one per member per study cycle, 89 with a beta, each carrying both endpoint tiers, the
less precise as its own, and a flag where a material acquisition changed the deposit base
inside the cycle. The milestone also lists restatement precedence and entity events, and
both are built: 48,206 revisions recorded and their effect on betas measured (0028, 0030),
and 53 entity events verified against the filings that report them and sized by the deposit
step each produced (0031, 0032).

One part of specification 4 is not built. It asks for affected bank-quarters to be flagged
as well as betas, and no bank-quarter table carries the flag. The event quarter is on every
row of `bank_entity_events`, so the flag is a join, but the table it belongs on is
`fct_bank_quarter`, which the site's bank explorer reads and which does not exist yet.

**Decision.** Milestone 2 is closed. Flagging individual bank-quarters moves to Milestone 4
with `fct_bank_quarter`, where it will be read.

**Alternatives.** Build `fct_bank_quarter` now. It would be designed without its only
consumer and redesigned once the bank explorer exists. Add the flag to `int_deposit_cost`,
which would put a hand-curated seed inside the Python model that resolves the metric and
make the metric's one implementation depend on the event record.

**Consequences.** Nothing at Milestone 3 needs a bank-quarter flag: the persistence test
works on betas, and those are flagged. The open data quality findings carry forward
unresolved and are listed in methodology section 10: BNY Mellon's derived 2025Q4, CIT's
2014Q4 on an unreconcilable base, Citigroup's 2020Q4, the unconfirmed negative-rate
explanation for the custody banks, Raymond James's mis-dated 2023Q1 and the 167
bank-quarters whose interest-bearing base cannot be reconciled. Only the last reaches a
beta: five rest on an unreconcilable base at one endpoint or both, Regions and SunTrust in
the calibration cycle and BNY Mellon, HSBC USA and Truist in the test cycle.

---

## 0034 — Pre-register the persistence analysis before computing it

**Date** 2026-10-10
**Status** Accepted. Fixes specification 6 before any cross-cycle result exists.

**Context.** The headline result is the rank correlation between each bank's
calibration-cycle and test-cycle betas, and it has never been computed. The cycle windows
were adopted (0023) and the precedence rule confirmed (0030) by comparing orderings within
a cycle only, so that no choice could be steered by its effect on the headline. The same
discipline has to hold for the choices left: which filers enter, how the correlation is
judged, and which variants are reported. Made after seeing the answer, each of them is a
dial. Made now, each is a commitment.

The sample sizes below depend only on tiers, coverage and entity events, none of which
reveals how the two cycles' betas relate. They were counted before this entry was written;
the correlation was not.

**Decision.** The headline sample is every filer that meets all of:

1. A member of the ranked fifty, since rankings are computed on it (0017).
2. A beta in both cycles at tier 1, both endpoints included (specification 3.1).
3. Tier 1 cost of deposits in at least 80 percent of each cycle's quarters (specification
   7.2).
4. No partial cycle (specification 4).
5. No material acquisition inside either cycle (0032), since specification 4 shows those
   banks separately: a deposit base that grew by a tenth or more by acquisition between a
   beta's two endpoints measures the acquired franchise as well as the bank.

Twenty-two filers qualify. No filer is excluded for the value of its beta. Every beta is
currently between 0 and 1; if a later load produces one outside that range it is reported,
and the headline is repeated without it as an extra line rather than replaced.

The headline statistic is the Spearman correlation between calibration and test betas
across that sample, ties sharing the mean of their ranks. It is judged by a one-sided
permutation test of a positive correlation, 100,000 permutations of the test-cycle betas,
and given a 95 percent percentile bootstrap interval from 10,000 resamples of filers. Both
use the fixed seed 20261010 so the figures reproduce exactly. Persistence is supported if
the correlation is positive and the permutation p-value is below 0.05. With 22 filers the
smallest correlation that can clear that bar is about 0.36, so a weaker persistence would
probably not be detected: a result that does not clear it is reported as not shown, not as
absent.

Then, in the order specification 6 sets:

- Quartile transitions over the same sample, each filer placed in quartile ceil(4r/n) of
  its own cycle by rank r, with the share remaining in the same quartile reported against
  the quarter expected by chance.
- Pearson correlation and the OLS fit of test beta on calibration beta, with R²,
  explicitly secondary: absolute levels are not expected to transfer (0003).
- Material deviators: filers two or more quartiles apart between the cycles. Each is given
  a hypothesis in the write-up, and every such hypothesis is labelled as formed after the
  result.

Robustness variants, all reported beside the headline and none replacing it:

| Variant | Change to the sample | Filers |
|---|---|---|
| R1 | Tiers 1 and 2, coverage at either tier | 24 |
| R2 | Filers with a material acquisition inside a cycle included | 30 |
| R3 | Filers with a material acquisition between the cycles also excluded | 20 |
| R4 | Survivorship: terminal filers whose test beta ends early added, other rules applied over the quarters they filed | 23 |

R4 adds one filer, SVB, measured to 2022Q4. PacWest, the other partial-cycle filer, is
seated by pin rather than rank and made two material acquisitions in the calibration cycle,
so it fails rule 5 in every variant but R2, where it fails rule 1. First Republic and
Signature are added to R4 if they are recovered from regulatory data at Milestone 3, and
their absence until then is stated beside the result.

**Alternatives.** Include filers with a material acquisition in the headline, which gives
thirty filers and more power but measures, for eight of them, a bank and an acquisition
together; it is reported as R2. Tiers 1 and 2 in the headline, which specification 3.1
rules out. A two-sided test, which would treat a negative correlation as support for
something; the hypothesis is directional and was fixed as such in 0002. Fisher-transformed
intervals, which lean on a normality that a sample of 22 ranks does not earn; the bootstrap
does not. More robustness variants, such as shifted cycle windows: 0023 already shows the
within-cycle ordering survives them, and each further variant is one more chance to find a
favourable one.

**Consequences.** The analysis is mechanical from here. The script implementing it reads
these rules and nothing else, and any departure from them has to be recorded as a new entry
before its result is reported.
