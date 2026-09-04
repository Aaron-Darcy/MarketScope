"""Milestone 0, questions 3 to 5: average balances, fourth-quarter derivation, window coverage.

Answers the three feasibility questions that can invalidate the metric definition:

  3. Are average deposit balances tagged anywhere, in any taxonomy, or must the metric
     fall back to endpoint averaging of period-end balances?
  4. Can the fourth quarter be derived for enough fiscal years to be usable?
  5. Is quarterly coverage across the calibration and test windows sufficient?

Cycle windows are pinned here rather than derived from FRED. Milestone 0 predates the
warehouse, and dim_rate_cycle owns this logic from Milestone 2 onward.

Usage:
    python analysis/feasibility/period_coverage.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from marketscope.banks import (
    DEPOSIT_BALANCE_TAGS,
    DEPOSIT_INTEREST_EXPENSE_TAGS,
    FEASIBILITY_SAMPLE,
)
from marketscope.facts import (
    Fact,
    Periodicity,
    derive_fourth_quarter,
    extract_facts,
    latest_filed,
)
from marketscope.ingestion.sec import SecClient

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

CALIBRATION_WINDOW = (date(2015, 10, 1), date(2019, 6, 30))
TEST_WINDOW = (date(2022, 1, 1), date(2023, 12, 31))
WINDOWS = {"calibration": CALIBRATION_WINDOW, "test": TEST_WINDOW}

QUARTER_END_DAYS = {(3, 31), (6, 30), (9, 30), (12, 31)}
AVERAGE_MARKERS = ("average", "averages")
DEPOSIT_MARKERS = ("deposit", "interestbearing")


def quarter_ends(start: date, end: date) -> list[date]:
    ends = [
        date(year, month, day)
        for year in range(start.year, end.year + 1)
        for month, day in sorted(QUARTER_END_DAYS)
    ]
    return [quarter for quarter in ends if start <= quarter <= end]


def is_quarter_end(day: date) -> bool:
    return (day.month, day.day) in QUARTER_END_DAYS


def average_balance_concepts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Find concepts that look like average deposit balances, in any taxonomy.

    Average balance sheets are normally presented in the rate and volume tables of the
    MD&A rather than the face financial statements, and are frequently not tagged at all.
    Where a filer does tag them it is often in its own extension namespace, so this scans
    every taxonomy rather than us-gaap alone.
    """
    found: list[dict[str, Any]] = []

    for taxonomy, concepts in payload.get("facts", {}).items():
        for tag, concept in concepts.items():
            lowered = tag.lower()
            if not any(marker in lowered for marker in AVERAGE_MARKERS):
                continue
            if not any(marker in lowered for marker in DEPOSIT_MARKERS):
                continue
            observations = concept.get("units", {}).get("USD", [])
            if not observations:
                continue
            found.append(
                {
                    "taxonomy": taxonomy,
                    "tag": tag,
                    "label": concept.get("label"),
                    "facts": len(observations),
                    "first_period": min(row["end"] for row in observations),
                    "last_period": max(row["end"] for row in observations),
                }
            )

    return found


def window_coverage(facts: list[Fact], window: tuple[date, date]) -> dict[str, Any]:
    start, end = window
    expected = quarter_ends(start, end)
    observed = {
        fact.period_end
        for fact in facts
        if start <= fact.period_end <= end and is_quarter_end(fact.period_end)
    }
    present = observed & set(expected)

    return {
        "quarters_expected": len(expected),
        "quarters_present": len(present),
        "coverage": len(present) / len(expected) if expected else 0.0,
    }


def expense_facts_with_derived_q4(payload: dict[str, Any]) -> dict[str, list[Fact]]:
    by_tag: dict[str, list[Fact]] = {}

    for tag in DEPOSIT_INTEREST_EXPENSE_TAGS:
        current = latest_filed(extract_facts(payload, tags=[tag]))
        quarterly = [fact for fact in current if fact.periodicity is Periodicity.QUARTERLY]
        by_tag[tag] = quarterly + derive_fourth_quarter(current)

    return by_tag


def q4_derivability(payload: dict[str, Any], tag: str) -> dict[str, Any]:
    current = latest_filed(extract_facts(payload, tags=[tag]))
    annuals = [fact for fact in current if fact.periodicity is Periodicity.ANNUAL]
    reported_q4 = {
        fact.period_end
        for fact in current
        if fact.periodicity is Periodicity.QUARTERLY and fact.period_end.month == 12
    }
    derived_q4 = {fact.period_end for fact in derive_fourth_quarter(current)}

    fiscal_year_ends = {fact.period_end for fact in annuals}
    resolved = fiscal_year_ends & (reported_q4 | derived_q4)

    return {
        "fiscal_years": len(fiscal_year_ends),
        "reported_directly": len(fiscal_year_ends & reported_q4),
        "derived": len((fiscal_year_ends & derived_q4) - reported_q4),
        "resolved": len(resolved),
        "resolved_share": len(resolved) / len(fiscal_year_ends) if fiscal_year_ends else 0.0,
    }


def profile_bank(
    bank_name: str, cik: int, payload: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    averages = [
        {"cik": cik, "bank": bank_name, **concept} for concept in average_balance_concepts(payload)
    ]

    coverage: list[dict[str, Any]] = []
    for tag, facts in expense_facts_with_derived_q4(payload).items():
        if not facts:
            continue
        for window_name, window in WINDOWS.items():
            coverage.append(
                {
                    "cik": cik,
                    "bank": bank_name,
                    "category": "deposit_interest_expense",
                    "tag": tag,
                    "window": window_name,
                    **window_coverage(facts, window),
                }
            )

    for tag in DEPOSIT_BALANCE_TAGS:
        balances = latest_filed(extract_facts(payload, tags=[tag]))
        if not balances:
            continue
        for window_name, window in WINDOWS.items():
            coverage.append(
                {
                    "cik": cik,
                    "bank": bank_name,
                    "category": "deposit_balance",
                    "tag": tag,
                    "window": window_name,
                    **window_coverage(balances, window),
                }
            )

    derivation = [
        {"cik": cik, "bank": bank_name, "tag": tag, **q4_derivability(payload, tag)}
        for tag in DEPOSIT_INTEREST_EXPENSE_TAGS
        if q4_derivability(payload, tag)["fiscal_years"]
    ]

    return {"averages": averages, "coverage": coverage, "derivation": derivation}


def run(output_dir: Path) -> dict[str, pd.DataFrame]:
    client = SecClient()
    collected: dict[str, list[dict[str, Any]]] = {"averages": [], "coverage": [], "derivation": []}

    try:
        for bank in FEASIBILITY_SAMPLE:
            logger.info("Profiling %s (CIK %d)", bank.name, bank.cik)
            try:
                payload = client.company_facts(bank.cik)
            except Exception as error:
                logger.error("Failed for %s: %s", bank.name, error)
                continue
            for key, rows in profile_bank(bank.name, bank.cik, payload).items():
                collected[key].extend(rows)
    finally:
        client.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {name: pd.DataFrame(rows) for name, rows in collected.items()}
    for name, frame in frames.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)

    return frames


def summarise(frames: dict[str, pd.DataFrame]) -> str:
    lines: list[str] = []
    averages, coverage, derivation = frames["averages"], frames["coverage"], frames["derivation"]

    lines.append("Question 3: average deposit balance concepts")
    if averages.empty:
        lines.append("  None tagged in any taxonomy. Endpoint averaging is required.")
    else:
        lines.append(f"  {averages['cik'].nunique()} banks tag at least one average concept.")
        for taxonomy, group in averages.groupby("taxonomy"):
            lines.append(f"  [{taxonomy}] {group['tag'].nunique()} concepts")
    lines.append("")

    lines.append("Question 4: fourth-quarter resolution by concept")
    if derivation.empty:
        lines.append("  No annual expense facts found.")
    else:
        by_tag = derivation.groupby("tag")[["fiscal_years", "resolved"]].sum()
        by_tag["share"] = by_tag["resolved"] / by_tag["fiscal_years"]
        for tag, row in by_tag.sort_values("share", ascending=False).iterrows():
            lines.append(
                f"  {row['share']:>6.1%}  {int(row['resolved'])}/{int(row['fiscal_years'])}  {tag}"
            )
    lines.append("")

    lines.append("Question 5: quarterly coverage by window")
    if coverage.empty:
        lines.append("  No coverage rows produced.")
    else:
        for (category, window), group in coverage.groupby(["category", "window"]):
            best = group.groupby("cik")["coverage"].max()
            lines.append(
                f"  [{category} / {window}] median {best.median():.1%}, "
                f"{int((best >= 0.8).sum())}/{len(best)} banks at or above 80%"
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    frames = run(args.output_dir)
    print(summarise(frames))
    return 0 if not frames["coverage"].empty else 1


if __name__ == "__main__":
    sys.exit(main())
