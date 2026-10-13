"""Milestone 1: size the institutions EDGAR cannot reach at all.

The universe built from EDGAR cannot answer how much of the banking system it misses. A
bank that files nothing with the SEC reports no assets in XBRL, so it cannot be ranked,
and every filer in an EDGAR-derived top fifty has XBRL by construction. Sizing the gap
therefore needs a ranking that does not come from EDGAR.

FDIC insured-institution financials are rolled up to each institution's regulatory high
holder to give that ranking, and each of the largest fifty groups is mapped to an SEC
registrant by a pinned, hand-verified table. Name matching is not used: it maps First
Republic Bank onto Republic First Bancorp, a different institution, which is the exact
confusion the decision record already warns about.

The rollup measures insured-bank assets, not consolidated holding-company assets, so it
understates groups with large non-bank balance sheets. It is used to decide membership of
the largest fifty, not to restate anyone's size.

Usage:
    python analysis/universe/reference_audit.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from marketscope.ingestion.fdic import FdicClient
from marketscope.regulatory import REFERENCE_MAP, Mapping, Reachability

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

# The test cycle opens here and every institution of interest was still reporting, which
# is why the reference is taken at this date rather than at the latest available one.
REFERENCE_DATE = "20221231"

REFERENCE_SIZE = 50


class UnmappedGroupError(Exception):
    """Raised when the regulatory ranking contains a group the pinned table does not cover."""


@dataclass(frozen=True)
class Group:
    key: str
    fdic_name: str
    assets: float
    deposits: float
    certs: tuple[int, ...]


def roll_up(financials: list[dict[str, Any]], institutions: list[dict[str, Any]]) -> list[Group]:
    """Aggregate insured institutions to their regulatory high holder.

    An institution the FDIC records no holder for is its own group. That is what makes the
    banks operating without a holding company visible in the ranking at all, which is the
    whole point of building it outside EDGAR.
    """
    by_cert = {int(row["CERT"]): row for row in institutions if row.get("CERT") is not None}
    totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"assets": 0.0, "deposits": 0.0, "certs": [], "name": ""}
    )

    for row in financials:
        cert = int(row["CERT"])
        institution = by_cert.get(cert)
        if institution is None:
            continue

        holder = institution.get("RSSDHCR")
        key = f"HC:{holder}" if holder not in (None, "", "0", 0) else f"BANK:{cert}"
        group = totals[key]
        # FDIC financials are reported in thousands.
        group["assets"] += float(row.get("ASSET") or 0) * 1000
        group["deposits"] += float(row.get("DEP") or 0) * 1000
        group["certs"].append(cert)
        if not group["name"]:
            group["name"] = institution.get("NAMEHCR") or institution.get("NAME") or ""

    groups = [
        Group(
            key=key,
            fdic_name=str(value["name"]),
            assets=float(value["assets"]),
            deposits=float(value["deposits"]),
            certs=tuple(sorted(value["certs"])),
        )
        for key, value in totals.items()
    ]
    groups.sort(key=lambda group: -group.assets)
    return groups


def resolve(groups: list[Group]) -> list[tuple[Group, Mapping]]:
    """Attach the pinned mapping to each group, refusing to guess at an unknown one."""
    unmapped = [group for group in groups if group.key not in REFERENCE_MAP]
    if unmapped:
        detail = ", ".join(f"{group.key} ({group.fdic_name})" for group in unmapped)
        raise UnmappedGroupError(
            f"The regulatory ranking contains {len(unmapped)} group(s) the pinned table "
            f"does not cover: {detail}. Verify each against EDGAR and add it rather than "
            f"letting it fall through as covered."
        )
    return [(group, REFERENCE_MAP[group.key]) for group in groups]


def run(output_dir: Path) -> list[tuple[Group, Mapping]]:
    with FdicClient() as client:
        logger.info("Fetching FDIC financials at %s", REFERENCE_DATE)
        financials = client.fetch_all(
            "financials", "CERT,ASSET,DEP,REPDTE", f"REPDTE:{REFERENCE_DATE}"
        )
        logger.info("Fetching FDIC institutions")
        institutions = client.fetch_all("institutions", "CERT,NAME,RSSDHCR,NAMEHCR,BKCLASS")

    logger.info("Rolling %d institutions up to high holder", len(financials))
    groups = roll_up(financials, institutions)[:REFERENCE_SIZE]
    resolved = resolve(groups)

    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "rank": position,
                "fdic_key": group.key,
                "fdic_name": group.fdic_name,
                "mapped_name": mapping.name,
                "insured_assets": group.assets,
                "insured_deposits": group.deposits,
                "certs": len(group.certs),
                "reachability": mapping.reachability.value,
                "cik": mapping.cik,
                "note": mapping.note,
            }
            for position, (group, mapping) in enumerate(resolved, start=1)
        ]
    ).to_csv(output_dir / "reference_audit.csv", index=False)

    return resolved


def summarise(resolved: list[tuple[Group, Mapping]]) -> str:
    lines = [
        f"Largest {len(resolved)} US depository groups by insured-bank assets at "
        f"{REFERENCE_DATE}, rolled to regulatory high holder",
        "",
    ]
    for position, (group, mapping) in enumerate(resolved, start=1):
        marker = "" if mapping.reachability.value.startswith("covered") else "  <- not in EDGAR"
        lines.append(
            f"{position:>3}. {group.assets / 1e9:>9,.0f}bn  {mapping.name[:40]:<40} "
            f"{mapping.reachability.value}{marker}"
        )

    lines += ["", "Reachability through EDGAR:"]
    for grade in Reachability:
        members = [mapping for _, mapping in resolved if mapping.reachability is grade]
        lines.append(f"  {grade.value:<24} {len(members):>2}")

    covered = sum(1 for _, mapping in resolved if mapping.reachability.value.startswith("covered"))
    lines += [
        "",
        f"Reachable in EDGAR:   {covered} of {len(resolved)}",
        f"Unreachable:          {len(resolved) - covered} of {len(resolved)}",
        "",
        "Unreachable institutions, by cause:",
    ]
    for grade in (Reachability.ABSENT_NO_REGISTRATION, Reachability.ABSENT_FOREIGN_PARENT):
        lines.append(f"  [{grade.value}]")
        for group, mapping in resolved:
            if mapping.reachability is grade:
                lines.append(f"    {group.assets / 1e9:>7,.0f}bn  {mapping.name}")
                lines.append(f"              {mapping.note}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    resolved = run(args.output_dir)
    report = summarise(resolved)
    print(report)
    (args.output_dir / "reference_audit.txt").write_text(report, encoding="utf-8")
    return 0 if resolved else 1


if __name__ == "__main__":
    sys.exit(main())
