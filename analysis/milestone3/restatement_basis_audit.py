"""Milestone 3: do derived fourth quarters mix a restated year with unrestated quarters?

A fourth quarter is derived as the current annual figure less the current nine months
(methodology 3.4), and precedence picks each period's most recently filed value separately
(3.2). Where a later filing restates the year but nothing restates the nine months, the
derived quarter absorbs the whole restatement. Citigroup's 2019Q4 and 2020Q4 did (0036).

An annual figure is flagged when its current value differs from the value it had when the
nine-month figure was last filed, and the nine months has not changed since that earlier
annual value was filed. The second condition matters: Santander's 2016 reorganisation was
restated into its 2015 nine months and its 2015 year, in that order, and the two current
values agree in basis though they were filed months apart.

Each flagged year is then taken back to the annual value consistent with its nine months,
and the deposit cost panel is rebuilt through the library with nothing else changed, so the
effect on every bank-quarter and every beta endpoint is the metric's own.

The second section records the evidence behind Santander's two unexplained deposit steps
(0032), which are the same restatement seen in balances.

Usage:
    python analysis/milestone3/restatement_basis_audit.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from marketscope import store
from marketscope.deposit_cost import deposit_cost_frame
from marketscope.facts import FACT_FIELDS, Fact, Periodicity, facts_from_rows, latest_filed
from marketscope.metrics import EXPENSE_COMPONENT_TAGS, EXPENSE_REPORTED_TAG
from marketscope.panel import DEFAULT_TAXONOMY, PANEL_TAGS
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

BASIS_POINTS = 10_000.0
MILLIONS = 1e6

# A change below a basis point is rounding between filings that publish in thousands and
# in millions, not a restatement anyone would notice in a cost of deposits.
REPORTED_BP = 1.0

NUMERATOR_TAGS = frozenset({EXPENSE_REPORTED_TAG, *EXPENSE_COMPONENT_TAGS})

SANTANDER = 811830
# The 2016Q3 10-Q, the first filing after Santander Holdings USA became an intermediate
# holding company on 1 July 2016 and combined the transferred entities retrospectively.
SANTANDER_RECAST_ACCESSION = "0000811830-16-000088"


@dataclass(frozen=True)
class MixedYear:
    cik: int
    tag: str
    year_end: date
    current: Fact
    consistent: Fact

    @property
    def change(self) -> float:
        return self.current.value - self.consistent.value


def as_filed_on(versions: list[Fact], day: date) -> Fact | None:
    """The version of a figure that was current on a given filing date."""
    filed = [fact for fact in versions if fact.filed <= day]
    return max(filed, key=lambda fact: (fact.filed, fact.accession or ""), default=None)


def mixed_years(cik: int, facts: list[Fact]) -> list[MixedYear]:
    """Derived fourth quarters whose annual figure was restated and nine months was not."""
    by_concept: dict[tuple[str, str], list[Fact]] = defaultdict(list)
    for fact in facts:
        if fact.tag in NUMERATOR_TAGS and fact.taxonomy == DEFAULT_TAXONOMY:
            by_concept[(fact.tag, fact.unit)].append(fact)

    found: list[MixedYear] = []
    for (tag, _), versions in by_concept.items():
        current = latest_filed(versions)
        reported = {
            fact.period_end for fact in current if fact.periodicity is Periodicity.QUARTERLY
        }
        for annual in (fact for fact in current if fact.periodicity is Periodicity.ANNUAL):
            if annual.period_end in reported:
                continue
            nine_months = max(
                (
                    fact
                    for fact in current
                    if fact.periodicity is Periodicity.NINE_MONTH
                    and fact.period_start == annual.period_start
                    and fact.period_end < annual.period_end
                ),
                key=lambda fact: fact.period_end,
                default=None,
            )
            if nine_months is None:
                continue
            annual_versions = [fact for fact in versions if fact.period_key == annual.period_key]
            consistent = as_filed_on(annual_versions, nine_months.filed)
            if consistent is None or consistent.value == annual.value:
                continue
            nine_month_then = as_filed_on(
                [fact for fact in versions if fact.period_key == nine_months.period_key],
                consistent.filed,
            )
            if nine_month_then is not None and nine_month_then.value != nine_months.value:
                continue
            found.append(MixedYear(cik, tag, annual.period_end, annual, consistent))
    return found


def consistent_rows(rows: list[tuple[Any, ...]], mixed: list[MixedYear]) -> list[tuple[Any, ...]]:
    """The fact rows with each mixed year's later annual versions removed."""
    field = {name: index for index, name in enumerate(FACT_FIELDS)}
    later = {
        (year.cik, year.tag, year.current.period_start, year.current.period_end) for year in mixed
    }
    cutoff = {
        (year.cik, year.tag, year.current.period_start, year.current.period_end): (
            year.consistent.filed
        )
        for year in mixed
    }
    kept: list[tuple[Any, ...]] = []
    for row in rows:
        key = (
            row[field["cik"]],
            row[field["tag"]],
            row[field["period_start"]],
            row[field["period_end"]],
        )
        if key in later and row[field["filed"]] > cutoff[key]:
            continue
        kept.append(row)
    return kept


def audit(connection: duckdb.DuckDBPyConnection) -> list[str]:
    concepts = ", ".join(f"'{tag}'" for tag in sorted(PANEL_TAGS))
    rows = connection.execute(
        f"select {', '.join(FACT_FIELDS)} from main_staging.stg_sec__company_facts "
        f"where tag in ({concepts})"
    ).fetchall()
    mixed = [
        year for cik, facts in facts_from_rows(rows).items() for year in mixed_years(cik, facts)
    ]

    rebuilt = deposit_cost_frame(consistent_rows(rows, mixed))
    rebuilt["quarter_end"] = pd.to_datetime(rebuilt["quarter_end"]).dt.date
    current = connection.execute(
        "select cik, quarter_end, cost_of_deposits, metric_tier from int_deposit_cost"
    ).df()
    current["quarter_end"] = pd.to_datetime(current["quarter_end"]).dt.date
    compared = current.merge(
        rebuilt[["cik", "quarter_end", "cost_of_deposits", "metric_tier"]],
        on=["cik", "quarter_end"],
        how="outer",
        suffixes=("", "_consistent"),
    )
    if (
        compared["cost_of_deposits"].isna().any()
        or compared["cost_of_deposits_consistent"].isna().any()
    ):
        raise ValueError("Rebuilding the panel added or lost a bank-quarter")
    compared["change_bp"] = (
        compared["cost_of_deposits_consistent"] - compared["cost_of_deposits"]
    ) * BASIS_POINTS

    names = dict(connection.execute("select cik, registrant_name from dim_bank").fetchall())
    endpoints = connection.execute(
        """
        select cik, cycle_name, start_quarter, measured_end_quarter, metric_tier
        from fct_deposit_beta
        where deposit_beta is not null
        order by cik, cycle_name
        """
    ).fetchall()
    touched = [
        (names[cik], cycle, quarter, tier, change)
        for cik, cycle, start, end, tier in endpoints
        for quarter in (start, end)
        for change in compared.loc[
            (compared["cik"] == cik) & (compared["quarter_end"] == quarter), "change_bp"
        ]
        if change != 0
    ]

    material = compared[compared["change_bp"].abs() >= REPORTED_BP].sort_values("change_bp")
    lines = [
        f"Annual numerator figures restated after their nine months was last filed: {len(mixed)}, "
        f"at {len({year.cik for year in mixed})} filers",
        f"Bank-quarters whose cost moves when each is taken back to its consistent value: "
        f"{int((compared['change_bp'] != 0).sum())}; by {REPORTED_BP:g}bp or more: {len(material)}",
        f"Tier changes: {int((compared['metric_tier'] != compared['metric_tier_consistent']).sum())}",
        "",
        f"  {'filer':<34}{'quarter':<12}{'tier':>5}{'as derived':>12}{'consistent':>12}{'bp':>8}",
    ]
    for _, row in material.iterrows():
        lines.append(
            f"  {names[row['cik']][:32]:<34}{row['quarter_end']!s:<12}{row['metric_tier']:>5}"
            f"{row['cost_of_deposits']:>12.2%}{row['cost_of_deposits_consistent']:>12.2%}"
            f"{row['change_bp']:>+8.1f}"
        )
    lines += ["", "Beta endpoints whose cost moves at all:"]
    lines += [
        f"  {name[:32]:<34}{cycle:<12}{quarter!s:<12}tier {tier}  {change:+.2f}bp"
        for name, cycle, quarter, tier, change in touched
    ] or ["  none"]
    return lines


def santander(connection: duckdb.DuckDBPyConnection) -> list[str]:
    """Santander's year-end 2015 deposits before and after the retrospective combination."""
    versions = connection.execute(
        """
        select period_end, value, filed, accession
        from raw.sec_facts
        where cik = ? and tag = 'Deposits' and period_start is null
          and period_end in ('2015-09-30', '2015-12-31', '2016-06-30', '2016-09-30')
        order by period_end, filed
        """,
        [SANTANDER],
    ).fetchall()
    lines = [
        "Santander Holdings USA, total deposits by the filing that reports them "
        f"(* the combined basis, from {SANTANDER_RECAST_ACCESSION} on):"
    ]
    recast_from = next(
        filed for _, _, filed, accession in versions if accession == SANTANDER_RECAST_ACCESSION
    )
    shown: set[tuple[date, float]] = set()
    for period, value, filed, _ in versions:
        if (period, round(value, -6)) in shown:
            continue
        shown.add((period, round(value, -6)))
        lines.append(
            f"  {period}  ${value / 1e9:>5.1f}bn  first filed {filed}{' *' if filed >= recast_from else ''}"
        )
    lines.append(
        "  Each quarter end keeps its most recent value. 2015-12-31 is restated to the combined "
        "basis;\n  2015-09-30 and 2016-06-30 never are, so the steps into 2015Q4 and 2016Q3 are "
        "the basis\n  changing, not the deposit base."
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    connection = store.connect(args.database, read_only=True)
    try:
        report = "\n".join([*audit(connection), "", *santander(connection)])
    finally:
        connection.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "restatement_basis_audit.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
