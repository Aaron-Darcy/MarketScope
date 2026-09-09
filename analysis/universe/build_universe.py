"""Milestone 1: build the top-50 universe from EDGAR and grade XBRL coverage across it.

Ranks every deposit-taking filer by peak total assets over the study window, takes the
largest fifty, and records how far each can be followed in EDGAR. Also reports the bank
SIC population and every filer the screens reject, so the cost of the specification's SIC
screen is measured rather than assumed.

Usage:
    python analysis/universe/build_universe.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from marketscope.ingestion.sec import SecClient
from marketscope.universe import (
    ASSETS_TAG,
    BALANCE_FRAMES,
    DEPOSIT_FUNDED_FLOOR,
    DEPOSITS_TAG,
    UNIVERSE_SIZE,
    Candidate,
    EdgarCoverage,
    Filer,
    bank_sic_entities,
    build_candidates,
    collect_deposit_interest_payers,
    collect_frame_names,
    collect_frames,
    rank,
    select,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


@dataclass(frozen=True)
class Result:
    members: list[Filer]
    excluded: list[Filer]
    candidates: list[Candidate]
    payers_by_tag: dict[str, set[int]]
    bank_sic: set[int]
    sic_entities: dict[str, list[int]]


def filer_rows(filers: list[Filer], *, ranked: bool) -> list[dict[str, Any]]:
    return [
        {
            **({"rank": position} if ranked else {}),
            "cik": filer.cik,
            "registrant_name": filer.registrant_name,
            "sic": filer.sic,
            "sic_description": filer.sic_description,
            "bank_sic": filer.has_bank_sic,
            "tickers": "|".join(filer.tickers),
            "exchanges": "|".join(filer.exchanges),
            "peak_assets": filer.candidate.peak_assets,
            "peak_deposits": filer.candidate.peak_deposits,
            "deposit_share": filer.candidate.deposit_share,
            "first_ten_k": filer.first_ten_k,
            "last_ten_k": filer.last_ten_k,
            "ten_k_count": filer.ten_k_count,
            "foreign_annual_forms": filer.foreign_annual_forms,
            "coverage": filer.coverage.value,
            "pinned": filer.is_pinned,
            "pinned_reason": filer.pinned_reason or "",
            "exclusion": filer.exclusion.value if filer.exclusion else "",
        }
        for position, filer in enumerate(filers, start=1)
    ]


def run(output_dir: Path) -> Result:
    client = SecClient()
    try:
        logger.info("Fetching %s and %s frames", ASSETS_TAG, DEPOSITS_TAG)
        assets = collect_frames(client, ASSETS_TAG, BALANCE_FRAMES)
        deposits = collect_frames(client, DEPOSITS_TAG, BALANCE_FRAMES)
        names = collect_frame_names(client, ASSETS_TAG, BALANCE_FRAMES)

        logger.info("Sweeping deposit interest expense concepts")
        payers_by_tag = collect_deposit_interest_payers(client)
        payers = {cik for ciks in payers_by_tag.values() for cik in ciks}

        logger.info("Enumerating bank SIC entities")
        sic_entities = bank_sic_entities(client)
        bank_sic = {cik for ciks in sic_entities.values() for cik in ciks}

        candidates = build_candidates(assets, deposits, payers, names)
        members, excluded = select(client, rank(candidates), UNIVERSE_SIZE)
    finally:
        client.close()

    result = Result(
        members=members,
        excluded=excluded,
        candidates=candidates,
        payers_by_tag=payers_by_tag,
        bank_sic=bank_sic,
        sic_entities=sic_entities,
    )
    write(result, output_dir)
    return result


def write(result: Result, output_dir: Path) -> None:
    reporting = {candidate.cik for candidate in result.candidates}
    output_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(filer_rows(result.members, ranked=True)).to_csv(
        output_dir / "universe.csv", index=False
    )
    pd.DataFrame(filer_rows(result.excluded, ranked=False)).to_csv(
        output_dir / "excluded.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "sic": sic,
                "entities": len(ciks),
                "with_xbrl_assets": sum(1 for cik in ciks if cik in reporting),
            }
            for sic, ciks in result.sic_entities.items()
        ]
    ).to_csv(output_dir / "sic_population.csv", index=False)
    pd.DataFrame(
        [
            {
                "cik": candidate.cik,
                "frame_entity_name": candidate.entity_name,
                "peak_assets": candidate.peak_assets,
                "peak_deposits": candidate.peak_deposits,
                "deposit_share": candidate.deposit_share,
                "pays_deposit_interest": candidate.pays_deposit_interest,
                "bank_sic": candidate.cik in result.bank_sic,
                "exclusion": candidate.exclusion.value if candidate.exclusion else "",
            }
            for candidate in sorted(result.candidates, key=lambda c: -c.peak_assets)
            if candidate.is_deposit_funded
        ]
    ).to_csv(output_dir / "deposit_funded_candidates.csv", index=False)


def summarise(result: Result) -> str:
    reporting = {candidate.cik for candidate in result.candidates}
    lines = ["Bank SIC population in EDGAR", ""]
    for sic, ciks in result.sic_entities.items():
        with_xbrl = sum(1 for cik in ciks if cik in reporting)
        lines.append(f"  SIC {sic}: {len(ciks):>5} entities, {with_xbrl:>4} reporting XBRL assets")

    lines += ["", "Deposit interest expense concepts, filers reporting each:"]
    for tag, payers in result.payers_by_tag.items():
        lines.append(f"  {len(payers):>4}  {tag}")

    funded = [candidate for candidate in result.candidates if candidate.is_deposit_funded]
    paying = [candidate for candidate in funded if candidate.pays_deposit_interest]
    in_sic = sum(1 for candidate in paying if candidate.cik in result.bank_sic)
    lines += [
        "",
        f"Filers reporting assets:                        {len(result.candidates)}",
        f"  deposit funded at {DEPOSIT_FUNDED_FLOOR:.2f} deposits/assets:      {len(funded)}",
        f"  and reporting deposit interest expense:       {len(paying)}",
        f"    carrying a bank SIC code:                   {in_sic}",
        f"    not carrying one:                           {len(paying) - in_sic}",
        "",
        f"Top {len(result.members)} by peak total assets, 2015Q4-2023Q4:",
        "",
    ]

    for position, filer in enumerate(result.members, start=1):
        flag = "" if filer.has_bank_sic else "  <- outside the SIC screen"
        if filer.is_pinned:
            flag += "  <- pinned"
        lines.append(
            f"{position:>3}. {filer.candidate.peak_assets / 1e9:>9,.0f}bn  "
            f"{filer.registrant_name[:44]:<44} SIC {filer.sic!s:<5} "
            f"{filer.coverage.value}{flag}"
        )

    lines += ["", "EDGAR coverage across the universe:"]
    for grade in EdgarCoverage:
        count = sum(1 for filer in result.members if filer.coverage is grade)
        lines.append(f"  {grade.value:<10} {count}")

    lines += ["", "Ranked above the cut but excluded:"]
    for filer in result.excluded:
        lines.append(
            f"  {filer.candidate.peak_assets / 1e9:>8,.0f}bn  {filer.registrant_name[:40]:<40} "
            f"{filer.exclusion.value if filer.exclusion else ''}"
        )

    pins = [filer for filer in result.members if filer.is_pinned]
    lines += ["", f"Pinned into the universe: {len(pins)}"]
    for filer in pins:
        lines.append(f"  {filer.registrant_name[:40]:<40} {filer.pinned_reason}")

    missed = [filer for filer in result.members if not filer.has_bank_sic]
    lines += ["", f"In the universe but outside the SIC screen: {len(missed)}"]
    for filer in missed:
        lines.append(
            f"  {filer.registrant_name[:40]:<40} SIC {filer.sic} "
            f"({filer.sic_description}) {filer.candidate.peak_assets / 1e9:,.0f}bn"
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    result = run(args.output_dir)
    report = summarise(result)
    print(report)
    (args.output_dir / "universe_report.txt").write_text(report, encoding="utf-8")
    return 0 if result.members else 1


if __name__ == "__main__":
    sys.exit(main())
