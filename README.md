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

**Status: Milestone 0 — feasibility.** The metric construction is being validated against
a twelve-bank sample before any warehouse or presentation layer is built. See
[docs/specification.md](docs/specification.md) for the gate criteria.

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
- **Failed banks stop filing.** Silicon Valley Bank, Signature and First Republic leave
  the data after 2023. A pipeline that quietly drops them produces a survivorship-biased
  answer that understates the effect being measured, so terminal filers are retained and
  every headline result is reported both with and without them.

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
src/marketscope/       ingestion clients, universe definition
analysis/feasibility/  Milestone 0 profiling and validation
transform/dbt/         warehouse models (from Milestone 1)
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

Profile deposit concept availability across the feasibility sample:

```
python analysis/feasibility/tag_coverage.py
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
- `docs/methodology.md` — written from Milestone 2, once the harmonisation rules are
  settled against real data
