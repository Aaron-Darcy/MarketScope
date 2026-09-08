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
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd

from marketscope.config import get_settings
from marketscope.ingestion.http import JsonApiClient, RateLimiter, ResponseCache

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

FDIC_HOST = "https://api.fdic.gov/banks"
FDIC_PAGE_SIZE = 10000

# The test cycle opens here and every institution of interest was still reporting, which
# is why the reference is taken at this date rather than at the latest available one.
REFERENCE_DATE = "20221231"

REFERENCE_SIZE = 50


class Reachability(StrEnum):
    """How an institution in the regulatory ranking is reachable through EDGAR."""

    COVERED_TOP_TIER = "covered_top_tier"
    COVERED_US_SUBSIDIARY = "covered_us_subsidiary"
    ABSENT_NO_REGISTRATION = "absent_no_registration"
    ABSENT_FOREIGN_PARENT = "absent_foreign_parent"


@dataclass(frozen=True)
class Mapping:
    name: str
    reachability: Reachability
    cik: int | None
    note: str = ""


# Keyed on the FDIC identifier of the group: the RSSD of the regulatory high holder, or
# the institution's own certificate number where the FDIC records no holder. Identifiers
# are used rather than names because names do not survive matching.
REFERENCE_MAP: dict[str, Mapping] = {
    "HC:1039502": Mapping("JPMorgan Chase & Co", Reachability.COVERED_TOP_TIER, 19617),
    "HC:1073757": Mapping("Bank of America Corporation", Reachability.COVERED_TOP_TIER, 70858),
    "HC:1951350": Mapping("Citigroup Inc", Reachability.COVERED_TOP_TIER, 831001),
    "HC:1120754": Mapping("Wells Fargo & Company", Reachability.COVERED_TOP_TIER, 72971),
    "HC:1119794": Mapping("U.S. Bancorp", Reachability.COVERED_TOP_TIER, 36104),
    "HC:1069778": Mapping("PNC Financial Services Group", Reachability.COVERED_TOP_TIER, 713676),
    "HC:1074156": Mapping("Truist Financial Corporation", Reachability.COVERED_TOP_TIER, 92230),
    "HC:2380443": Mapping("The Goldman Sachs Group, Inc.", Reachability.COVERED_TOP_TIER, 886982),
    "HC:2277860": Mapping("Capital One Financial Corp", Reachability.COVERED_TOP_TIER, 927628),
    "HC:1238565": Mapping(
        "The Toronto-Dominion Bank",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "TD Group US Holdings files FR Y-9C; no US entity is an SEC registrant",
    ),
    "HC:2162966": Mapping("Morgan Stanley", Reachability.COVERED_TOP_TIER, 895421),
    "HC:1026632": Mapping("The Charles Schwab Corporation", Reachability.COVERED_TOP_TIER, 316709),
    "HC:3587146": Mapping(
        "The Bank of New York Mellon Corporation", Reachability.COVERED_TOP_TIER, 1390777
    ),
    "HC:1111435": Mapping("State Street Corporation", Reachability.COVERED_TOP_TIER, 93751),
    "HC:1132449": Mapping("Citizens Financial Group Inc", Reachability.COVERED_TOP_TIER, 759944),
    "BANK:59017": Mapping(
        "First Republic Bank",
        Reachability.ABSENT_NO_REGISTRATION,
        None,
        "State-chartered bank with no holding company and no registered securities. "
        "CIK 1132979 carries only ownership forms and returns 404 from company facts",
    ),
    "HC:1031449": Mapping("SVB Financial Group", Reachability.COVERED_TOP_TIER, 719739),
    "HC:1070345": Mapping("Fifth Third Bancorp", Reachability.COVERED_TOP_TIER, 35527),
    "HC:1037003": Mapping("M&T Bank Corporation", Reachability.COVERED_TOP_TIER, 36270),
    "HC:1068025": Mapping("KeyCorp", Reachability.COVERED_TOP_TIER, 91576),
    "HC:1068191": Mapping("Huntington Bancshares Inc", Reachability.COVERED_TOP_TIER, 49196),
    "HC:1562859": Mapping("Ally Financial Inc.", Reachability.COVERED_TOP_TIER, 40729),
    "HC:1231333": Mapping(
        "Bank of Montreal",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "BMO Financial Corp files FR Y-9C; no US entity is an SEC registrant",
    ),
    "HC:1857108": Mapping(
        "HSBC Holdings plc",
        Reachability.COVERED_US_SUBSIDIARY,
        83246,
        "HSBC USA Inc. files 10-K with XBRL against its registered debt",
    ),
    "HC:1275216": Mapping("American Express Company", Reachability.COVERED_TOP_TIER, 4962),
    "HC:1199611": Mapping("Northern Trust Corporation", Reachability.COVERED_TOP_TIER, 73124),
    "HC:3242838": Mapping("Regions Financial Corporation", Reachability.COVERED_TOP_TIER, 1281761),
    "HC:3846375": Mapping("Discover Financial Services", Reachability.COVERED_TOP_TIER, 1393612),
    "HC:4795461": Mapping(
        "UBS Group AG",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "UBS Americas Holding files FR Y-9C; the parent files 20-F without US bank detail",
    ),
    "HC:1447376": Mapping(
        "United Services Automobile Association",
        Reachability.ABSENT_NO_REGISTRATION,
        None,
        "Member-owned reciprocal inter-insurance exchange with no registered securities",
    ),
    "BANK:57053": Mapping(
        "Signature Bank",
        Reachability.ABSENT_NO_REGISTRATION,
        None,
        "State-chartered bank with no holding company. CIK 1288784 carries only ownership "
        "forms and returns 404 from company facts",
    ),
    "HC:1075612": Mapping("First Citizens BancShares Inc", Reachability.COVERED_TOP_TIER, 798941),
    "HC:1232497": Mapping(
        "Royal Bank of Canada",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "RBC US Group Holdings files FR Y-9C; no US entity is an SEC registrant",
    ),
    "HC:1239254": Mapping(
        "Banco Santander SA",
        Reachability.COVERED_US_SUBSIDIARY,
        811830,
        "Santander Holdings USA, Inc. files 10-K with XBRL against its registered debt",
    ),
    "HC:4504654": Mapping("Synchrony Financial", Reachability.COVERED_TOP_TIER, 1601712),
    "HC:1231968": Mapping(
        "BNP Paribas",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "BNP Paribas USA files FR Y-9C; no US entity is an SEC registrant",
    ),
    "BANK:32541": Mapping(
        "Flagstar Bank, National Association",
        Reachability.COVERED_TOP_TIER,
        910073,
        "The FDIC record carries no high holder at this date, weeks after the New York "
        "Community Bancorp acquisition closed. Its holder files as CIK 910073",
    ),
    "BANK:2270": Mapping(
        "Zions Bancorporation, N.A.",
        Reachability.COVERED_TOP_TIER,
        109380,
        "Dissolved its holding company in 2018 and files as the bank itself. Shows that "
        "the driver of absence is registered securities, not holding-company structure",
    ),
    "HC:1199844": Mapping("Comerica Incorporated", Reachability.COVERED_TOP_TIER, 28412),
    "HC:1094640": Mapping("First Horizon Corporation", Reachability.COVERED_TOP_TIER, 36966),
    "HC:1145476": Mapping("Webster Financial Corporation", Reachability.COVERED_TOP_TIER, 801337),
    "HC:2349815": Mapping(
        "Western Alliance Bancorporation", Reachability.COVERED_TOP_TIER, 1212545
    ),
    "HC:1129382": Mapping("Popular, Inc.", Reachability.COVERED_TOP_TIER, 763901),
    "HC:2734233": Mapping("East West Bancorp, Inc.", Reachability.COVERED_TOP_TIER, 1069157),
    "HC:1078846": Mapping("Synovus Financial Corp.", Reachability.COVERED_TOP_TIER, 18349),
    "HC:3815157": Mapping("Raymond James Financial, Inc.", Reachability.COVERED_TOP_TIER, 720005),
    "HC:1048773": Mapping("Valley National Bancorp", Reachability.COVERED_TOP_TIER, 714310),
    "HC:2260406": Mapping("Wintrust Financial Corporation", Reachability.COVERED_TOP_TIER, 1015328),
    "BANK:33653": Mapping(
        "Bank of China",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "US branch network of a Chinese bank; no US entity is an SEC registrant",
    ),
    "BANK:33692": Mapping(
        "Standard Chartered Bank, PLC",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "US branch of a UK bank; no US entity is an SEC registrant",
    ),
}


class UnmappedGroupError(Exception):
    """Raised when the regulatory ranking contains a group the pinned table does not cover."""


@dataclass(frozen=True)
class Group:
    key: str
    fdic_name: str
    assets: float
    deposits: float
    certs: tuple[int, ...]


def fdic_client() -> JsonApiClient:
    settings = get_settings()
    return JsonApiClient(
        headers={"User-Agent": settings.sec_user_agent, "Accept": "application/json"},
        rate_limiter=RateLimiter(settings.fred_requests_per_second),
        cache=ResponseCache(
            root=settings.cache_dir / "fdic",
            ttl=timedelta(hours=settings.cache_ttl_hours),
        ),
        timeout=settings.request_timeout_seconds,
        max_retries=settings.max_retries,
    )


def fetch_all(
    client: JsonApiClient, path: str, fields: str, filters: str = ""
) -> list[dict[str, Any]]:
    """Page through an FDIC collection until it stops returning rows."""
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        params: dict[str, Any] = {
            "fields": fields,
            "limit": str(FDIC_PAGE_SIZE),
            "offset": str(offset),
            "format": "json",
        }
        if filters:
            params["filters"] = filters
        payload = client.get_json(f"{FDIC_HOST}/{path}", params=params)
        batch = [row["data"] for row in payload.get("data", [])]
        if not batch:
            return rows
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < FDIC_PAGE_SIZE:
            return rows


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
    client = fdic_client()
    try:
        logger.info("Fetching FDIC financials at %s", REFERENCE_DATE)
        financials = fetch_all(
            client, "financials", "CERT,ASSET,DEP,REPDTE", f"REPDTE:{REFERENCE_DATE}"
        )
        logger.info("Fetching FDIC institutions")
        institutions = fetch_all(client, "institutions", "CERT,NAME,RSSDHCR,NAMEHCR,BKCLASS")
    finally:
        client.close()

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
