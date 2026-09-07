"""Milestone 0, question 1 and 2: which deposit concepts are actually tagged, and how often.

Profiles the candidate deposit interest-expense and deposit-balance concepts across the
feasibility sample, and verifies that each hardcoded CIK resolves to the expected filer.
Results are written to analysis/feasibility/output/ for inspection.

Usage:
    python analysis/feasibility/tag_coverage.py
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
    CONTEXT_TAGS,
    DEPOSIT_BALANCE_TAGS,
    DEPOSIT_INTEREST_EXPENSE_TAGS,
    FEASIBILITY_SAMPLE,
    Bank,
)
from marketscope.ingestion.sec import SecClient, normalise_entity_name

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
QUARTER_DAYS = range(80, 101)
ANNUAL_DAYS = range(350, 381)

CANDIDATE_TAGS: dict[str, tuple[str, ...]] = {
    "deposit_interest_expense": DEPOSIT_INTEREST_EXPENSE_TAGS,
    "deposit_balance": DEPOSIT_BALANCE_TAGS,
    "context": CONTEXT_TAGS,
}


class IdentityMismatchError(Exception):
    """Raised when a CIK does not resolve to the filer the sample expects."""


def verify_identity(bank: Bank, client: SecClient) -> None:
    entity_name = client.entity_name(bank.cik)
    if normalise_entity_name(bank.name_fragment) not in entity_name:
        raise IdentityMismatchError(
            f"CIK {bank.cik} resolved to {entity_name!r}, expected a name containing "
            f"{bank.name_fragment!r}"
        )


def profile_tag(units: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    observations = units.get("USD", [])
    if not observations:
        return {"present": False}

    quarterly = 0
    annual = 0
    instant = 0
    periods: list[date] = []

    for observation in observations:
        end = date.fromisoformat(observation["end"])
        periods.append(end)

        start_value = observation.get("start")
        if start_value is None:
            instant += 1
            continue

        span = (end - date.fromisoformat(start_value)).days
        if span in QUARTER_DAYS:
            quarterly += 1
        elif span in ANNUAL_DAYS:
            annual += 1

    return {
        "present": True,
        "facts": len(observations),
        "instant_facts": instant,
        "quarterly_facts": quarterly,
        "annual_facts": annual,
        "first_period": min(periods),
        "last_period": max(periods),
    }


def profile_bank(bank: Bank, facts: dict[str, Any]) -> list[dict[str, Any]]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    rows: list[dict[str, Any]] = []

    for category, tags in CANDIDATE_TAGS.items():
        for tag in tags:
            profile = profile_tag(us_gaap.get(tag, {}).get("units", {}))
            rows.append(
                {
                    "cik": bank.cik,
                    "bank": bank.name,
                    "profile": bank.profile.value,
                    "terminal_filer": bank.is_terminal_filer,
                    "category": category,
                    "tag": tag,
                    **profile,
                }
            )
    return rows


def run(output_dir: Path) -> pd.DataFrame:
    client = SecClient()
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    try:
        for bank in FEASIBILITY_SAMPLE:
            logger.info("Fetching company facts for %s (CIK %d)", bank.name, bank.cik)
            try:
                verify_identity(bank, client)
                facts = client.company_facts(bank.cik)
            except Exception as error:
                failures.append(f"{bank.name} (CIK {bank.cik}): {error}")
                logger.error("Failed for %s: %s", bank.name, error)
                continue
            rows.extend(profile_bank(bank, facts))
    finally:
        client.close()

    frame = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "tag_coverage.csv", index=False)

    if failures:
        Path(output_dir / "failures.txt").write_text("\n".join(failures), encoding="utf-8")

    return frame


def summarise(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No facts retrieved."

    present = frame[frame["present"]]
    lines = ["Tag availability by bank", ""]

    for category in CANDIDATE_TAGS:
        subset = present[present["category"] == category]
        lines.append(f"[{category}]")
        counts = subset.groupby("tag")["cik"].nunique().sort_values(ascending=False)
        for tag, banks in counts.items():
            lines.append(f"  {banks:>2}/{frame['cik'].nunique()}  {tag}")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    frame = run(args.output_dir)
    print(summarise(frame))
    return 0 if not frame.empty else 1


if __name__ == "__main__":
    sys.exit(main())
