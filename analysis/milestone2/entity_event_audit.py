"""Milestone 2: does every entity event match the filing it cites?

XBRL records no mergers, failures or deregistrations, so `entity_events` is curated by hand.
A hand-entered date is exactly the kind of figure that drifts unchecked, so every row cites
the filing that reports the event, and this script checks each citation against the
filer's own EDGAR history: the accession must belong to the filer, carry the form and the
8-K item cited, and have been filed no more than two days before the event or six after it.
Six calendar days covers the four business days an 8-K is due within; the two before allow
for a filing that announces a closing date the day it is fixed.

Reads the seed from the warehouse, so run `dbt build` first.

Usage:
    python analysis/milestone2/entity_event_audit.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from marketscope import store
from marketscope.ingestion.sec import SecClient
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

FILED_BEFORE = timedelta(days=2)
FILED_AFTER = timedelta(days=6)


@dataclass(frozen=True)
class Event:
    cik: int
    registrant_name: str
    event_date: date
    event_type: str
    counterparty: str
    evidence_accession: str
    evidence_form: str
    evidence_item: str | None


def read_events(database: Path) -> list[Event]:
    connection = store.connect(database, read_only=True)
    try:
        rows = connection.execute(
            """
            select events.cik, members.registrant_name, event_date, event_type,
                   coalesce(counterparty, ''), evidence_accession, evidence_form, evidence_item
            from entity_events as events
            join raw.universe as members using (cik)
            order by event_date, events.cik
            """
        ).fetchall()
    finally:
        connection.close()
    return [Event(*row) for row in rows]


def problems(event: Event, history: list[dict[str, Any]]) -> list[str]:
    """Every way the cited filing fails to support the event; empty when it does."""
    filing = next(
        (f for f in history if f.get("accessionNumber") == event.evidence_accession), None
    )
    if filing is None:
        return [f"{event.evidence_accession} is not in the filer's history"]

    found: list[str] = []
    if filing.get("form") != event.evidence_form:
        found.append(f"form is {filing.get('form')}, not {event.evidence_form}")

    items = [item.strip() for item in str(filing.get("items") or "").split(",") if item.strip()]
    if event.evidence_item and event.evidence_item not in items:
        found.append(f"items are {items or 'none'}, not {event.evidence_item}")

    filed = date.fromisoformat(str(filing.get("filingDate")))
    if not event.event_date - FILED_BEFORE <= filed <= event.event_date + FILED_AFTER:
        found.append(f"filed {filed}, outside the window around {event.event_date}")
    return found


def audit(events: list[Event]) -> list[tuple[Event, list[str]]]:
    results: list[tuple[Event, list[str]]] = []
    histories: dict[int, list[dict[str, Any]]] = {}
    with SecClient() as client:
        for event in events:
            if event.cik not in histories:
                logger.info("Fetching filing history for CIK %d", event.cik)
                histories[event.cik] = client.filing_history(event.cik)
            results.append((event, problems(event, histories[event.cik])))
    return results


def summarise(results: list[tuple[Event, list[str]]]) -> str:
    failed = [(event, found) for event, found in results if found]
    lines = [
        "Entity events checked against the filings they cite",
        "",
        f"Events: {len(results)}, supported: {len(results) - len(failed)}, "
        f"unsupported: {len(failed)}",
        "",
        f"{'date':<11} {'type':<20} {'filer':<32} {'counterparty':<30} evidence",
    ]
    for event, found in results:
        evidence = event.evidence_form + (f" {event.evidence_item}" if event.evidence_item else "")
        status = "ok" if not found else "UNSUPPORTED: " + "; ".join(found)
        lines.append(
            f"{event.event_date!s:<11} {event.event_type:<20} {event.registrant_name[:32]:<32} "
            f"{event.counterparty[:30]:<30} {evidence:<11} {status}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    results = audit(read_events(args.database))
    report = summarise(results)
    print(report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "entity_event_audit.txt").write_text(report, encoding="utf-8")
    return 1 if any(found for _, found in results) else 0


if __name__ == "__main__":
    sys.exit(main())
