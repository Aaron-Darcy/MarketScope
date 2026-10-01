# MarketScope

Deposit repricing analytics for US bank holding companies, built from primary SEC EDGAR
filings and Federal Reserve data.

**Research question**

> Does deposit repricing behaviour observed during one monetary-tightening cycle help
> explain cross-bank funding-cost pressure during the next?

Banks do not pass policy rate changes through to depositors at the same speed. The rate at
which a bank's funding cost follows the federal funds rate — its deposit beta — is a
central determinant of net interest margin, and it varies widely with funding mix. This
project measures deposit beta for US bank holding companies directly from XBRL filing
data, calibrates it over the 2015–2019 tightening cycle, and tests whether the resulting
cross-bank ordering holds during the far faster 2022–2023 cycle.

**Status: Milestone 2 in progress — harmonisation and beta.** The universe of the largest
fifty deposit-taking US filers plus one pinned terminal filer loads into DuckDB behind dbt
staging models. Cost of deposits is resolved for 3,066 bank-quarters, each with a
comparability tier, and `fct_deposit_beta` carries a tiered beta for every member in both
study cycles. The restatement table and entity events remain. See
[docs/specification.md](docs/specification.md).

---

## Why the measurement is non-trivial

The two cycles differ in both size and pace — roughly 225bp over 36 months against
roughly 525bp over 16 months — so absolute beta levels are not expected to transfer
between them. The testable claim concerns relative ordering, which is why rank persistence
rather than regression fit is the primary reported result.

Constructing a comparable cost-of-deposits series from XBRL is itself the substantive
work:

- **Concept availability varies by filer.** Deposit interest expense may be tagged as a
  single concept, decomposed into time, savings, money-market and NOW components, or
  bundled with short-term borrowings.
- **Numerator and denominator must correspond.** Interest expense on interest-bearing
  deposits divided by total deposits is not the same measure as one divided by average
  interest-bearing deposits. Metrics are therefore assigned a comparability tier and never
  silently mixed.
- **Average balances are frequently untagged.** Where they are unavailable, endpoint
  averaging is used and the row is marked accordingly.
- **Fourth-quarter flows usually have to be derived** as the fiscal year less the first
  three quarters, since most filers do not file a fourth 10-Q.
- **Failed banks stop filing.** Silicon Valley Bank leaves the data after 2022 and PacWest
  after 2023Q3. A pipeline that quietly drops them produces a survivorship-biased answer
  that understates the effect being measured, so terminal filers are retained and every
  headline result is reported both with and without them.
- **Some banks never file at all.** First Republic and Signature registered no securities,
  so they have no 10-K and no XBRL in EDGAR — measured at 3 of the largest 50 US depository
  groups, alongside 7 more that are US arms of foreign banking organisations. The gap is
  sized against FDIC data rather than assumed.
- **Industry codes do not identify banks.** Screening EDGAR on bank SIC codes loses Goldman
  Sachs, Morgan Stanley and Charles Schwab, which carry broker-dealer codes. Membership is
  decided by what a filer reports instead.

Derived figures are cross-checked against FFIEC and FDIC regulatory filings, which carry
the same concepts in standardised form, so the accuracy of the tag mapping can be stated
as a measured error rate rather than asserted.

---

## Data sources

| Source | Use | Licence |
|---|---|---|
| SEC EDGAR XBRL company facts | Deposit balances, interest expense, fundamentals | Public domain |
| SEC EDGAR submissions | Filing history, form type, filing dates | Public domain |
| FRED | Federal funds rate, Treasury yields | Free, key required |
| FFIEC / FDIC | Independent validation of derived metrics | Public domain |

No paid or redistribution-restricted market data is used.

---

## Repository layout

```
src/marketscope/       ingestion clients, universe construction, DuckDB load
analysis/feasibility/  Milestone 0 profiling and validation
analysis/universe/     universe construction and EDGAR coverage audit
data/seeds/            the committed universe
transform/dbt/         warehouse models
site/                  Evidence.dev application (from Milestone 4)
docs/                  specification, methodology, decision record
tests/
```

---

## Running locally

Requires Python 3.11 or later.

```
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Set `MARKETSCOPE_SEC_USER_AGENT` in `.env` to a string containing real contact details.
The SEC rejects requests without one and limits callers to ten requests per second; both
constraints are enforced in `marketscope.ingestion.http`.

Load the committed universe, its filings and the rate series into DuckDB:

```
python -m marketscope.pipeline
cd transform/dbt && dbt build
```

The universe itself is committed to `data/seeds/universe.csv` and ingestion reads it, so a
load covers a fixed set of filers. Rebuilding it is a separate, deliberate act:

```
python analysis/universe/build_universe.py --check       # fail if the build has drifted
python analysis/universe/build_universe.py --write-seed  # adopt the new membership
```

Size what EDGAR cannot reach, against FDIC data:

```
python analysis/universe/reference_audit.py
```

Responses are cached under `data/cache`, so repeated runs during development do not
re-request from the SEC.

Checks:

```
ruff check .
mypy
pytest
```

---

## Documentation

- [docs/specification.md](docs/specification.md) — scope, metric definition, milestones,
  gate criteria
- [docs/decisions.md](docs/decisions.md) — decision record
- [docs/changelog.md](docs/changelog.md) — change history
- [docs/methodology.md](docs/methodology.md) — how each figure is produced, the data
  problems behind it, and what is not yet handled
