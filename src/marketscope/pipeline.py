"""Load the committed universe, its SEC filings, the FRED rate series, the Call Report
deposit figures for the regulatory comparison and the FFIEC quarterly averages into DuckDB.

Usage:
    python -m marketscope.pipeline
    python -m marketscope.pipeline --skip-sec --skip-fred
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from marketscope import store
from marketscope.facts import extract_facts
from marketscope.ingestion import ffiec
from marketscope.ingestion.fdic import FdicClient
from marketscope.ingestion.fred import FredClient
from marketscope.ingestion.sec import SecClient
from marketscope.regulatory import group_filter, regulatory_groups
from marketscope.store import DATABASE_PATH
from marketscope.universe import SEED_PATH, SeedRow, read_seed

logger = logging.getLogger(__name__)

# The policy rate the deposit beta is measured against, plus the two Treasury points the
# bank pages use for context. Cycle windows are derived from FEDFUNDS rather than hardcoded.
FRED_SERIES: tuple[str, ...] = ("FEDFUNDS", "DGS2", "DGS10")

# Every unit the deposit metric can be built from. Facts in other units — shares, ratios,
# per-share amounts — are not loaded, because nothing downstream reads them and they are
# most of the payload.
FACT_UNITS: tuple[str, ...] = ("USD",)

# Call Reports from the year the first members began filing XBRL, so every bank-quarter the
# metric can resolve has a regulatory counterpart.
FDIC_FIRST_REPORT = "20090101"


@dataclass
class LoadReport:
    counts: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class FilerPayload:
    facts: list[tuple[Any, ...]]
    filings: list[tuple[Any, ...]]
    registrant: tuple[Any, ...]


def fetch_filer(client: SecClient, member: SeedRow) -> FilerPayload:
    """Pull everything the warehouse holds for one filer.

    Facts are read across every taxonomy the endpoint publishes rather than us-gaap
    alone, so the raw layer is a copy of the payload and the choice of taxonomy is made
    downstream, where it can be tested. The endpoint publishes no filer's own extension
    namespace.
    """
    submissions = client.submissions(member.cik)
    payload = client.company_facts(member.cik)
    facts = extract_facts(payload, taxonomy=None, units=FACT_UNITS)

    return FilerPayload(
        facts=store.fact_rows(member.cik, facts),
        filings=store.filing_rows(member.cik, client.filing_history(member.cik)),
        registrant=store.registrant_row(member.cik, submissions),
    )


def load_sec(
    connection: duckdb.DuckDBPyConnection, members: list[SeedRow], report: LoadReport
) -> None:
    """Fetch each filer and stream it straight into the warehouse.

    Rows go in per filer rather than being accumulated across all of them, because the
    universe produces roughly two million facts and holding them in memory to insert once
    buys nothing. All three tables share a transaction each, so a run that fails partway
    leaves the previous load intact.
    """
    tables = {
        "sec_facts": store.FACT_COLUMNS,
        "sec_filings": store.FILING_COLUMNS,
        "sec_registrants": store.REGISTRANT_COLUMNS,
    }

    client = SecClient()
    try:
        with store.replacing_many(connection, tables) as appenders:
            for position, member in enumerate(members, start=1):
                logger.info(
                    "[%d/%d] %s (CIK %d)",
                    position,
                    len(members),
                    member.registrant_name,
                    member.cik,
                )
                try:
                    payload = fetch_filer(client, member)
                except Exception as error:
                    # One bad response should not cost the other fifty. The filer is
                    # recorded and the run still fails at the end.
                    report.failures.append(f"{member.registrant_name} (CIK {member.cik}): {error}")
                    logger.error("Failed for CIK %d: %s", member.cik, error)
                    continue

                appenders["sec_facts"].append(payload.facts)
                appenders["sec_filings"].append(payload.filings)
                appenders["sec_registrants"].append([payload.registrant])
    finally:
        client.close()

    # Read after the context exits, so the final partial batch is counted.
    for table, appender in appenders.items():
        report.counts[table] = appender.rows


def load_fred(connection: duckdb.DuckDBPyConnection, report: LoadReport) -> None:
    rows: list[tuple[Any, ...]] = []
    client = FredClient()
    try:
        for series_id in FRED_SERIES:
            logger.info("Fetching FRED series %s", series_id)
            try:
                rows.extend(store.fred_rows(series_id, client.observations(series_id)))
            except Exception as error:
                report.failures.append(f"FRED series {series_id}: {error}")
                logger.error("Failed for %s: %s", series_id, error)
    finally:
        client.close()

    report.counts["fred_observations"] = store.replace(
        connection, "fred_observations", store.FRED_COLUMNS, rows
    )


def load_fdic(connection: duckdb.DuckDBPyConnection, report: LoadReport) -> None:
    """Load Call Report deposit figures for every pinned regulatory group.

    A group that fails to load is recorded and the run fails at the end, as for the SEC: a
    comparison run on the groups that happened to load would describe a sample nobody chose.
    """
    rows: list[tuple[Any, ...]] = []
    with FdicClient() as client:
        for key, mapping in regulatory_groups():
            logger.info("Fetching Call Report deposits for %s", mapping.name)
            try:
                records = client.financials(
                    f"{group_filter(key)} AND REPDTE:[{FDIC_FIRST_REPORT} TO *]"
                )
            except Exception as error:
                report.failures.append(f"FDIC group {key} ({mapping.name}): {error}")
                logger.error("Failed for %s: %s", key, error)
                continue
            rows.extend(store.fdic_rows(key, mapping.cik, records))

    report.counts["fdic_financials"] = store.replace(
        connection, "fdic_financials", store.FDIC_COLUMNS, rows
    )


def load_ffiec(connection: duckdb.DuckDBPyConnection, report: LoadReport, directory: Path) -> None:
    """Load the deposit items of every bulk Call Report archive in a directory.

    The archives are downloaded by hand (decision 0038), so an empty directory is recorded
    as a failure rather than loaded as an empty table: a warehouse that silently lost its
    averages would report the averaging error as unmeasured without saying why. A malformed
    archive is recorded as a failure and leaves the previous load intact, since loading the
    quarters that parsed would describe a set of quarters nobody chose.
    """
    try:
        paths = ffiec.archives(directory) if directory.is_dir() else []
        if not paths:
            report.failures.append(f"FFIEC: no bulk Call Report archives in {directory}")
            logger.error("No FFIEC archives in %s", directory)
            return
        with store.replacing(connection, "ffiec_call_items", store.FFIEC_COLUMNS) as appender:
            for path in paths:
                logger.info("Reading %s", path.name)
                appender.append(store.ffiec_rows(ffiec.read_archive(path)))
    except ffiec.BulkFileError as error:
        report.failures.append(f"FFIEC: {error}")
        logger.error("FFIEC load failed: %s", error)
        return
    report.counts["ffiec_call_items"] = appender.rows


def run(
    database: Path = DATABASE_PATH,
    seed: Path = SEED_PATH,
    *,
    skip_sec: bool = False,
    skip_fred: bool = False,
    skip_fdic: bool = False,
    skip_ffiec: bool = False,
    ffiec_dir: Path = ffiec.FFIEC_DIR,
) -> LoadReport:
    members = read_seed(seed)
    logger.info("Loading %d universe members from %s", len(members), seed)

    report = LoadReport()
    connection = store.connect(database)
    try:
        report.counts["universe"] = store.replace(
            connection, "universe", store.UNIVERSE_COLUMNS, store.universe_rows(members)
        )
        if skip_sec:
            logger.info("Skipping SEC")
        else:
            load_sec(connection, members, report)
        if skip_fred:
            logger.info("Skipping FRED")
        else:
            load_fred(connection, report)
        if skip_fdic:
            logger.info("Skipping FDIC")
        else:
            load_fdic(connection, report)
        if skip_ffiec:
            logger.info("Skipping FFIEC")
        else:
            load_ffiec(connection, report, ffiec_dir)
    finally:
        connection.close()

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--seed", type=Path, default=SEED_PATH)
    parser.add_argument("--skip-sec", action="store_true")
    parser.add_argument("--skip-fred", action="store_true")
    parser.add_argument("--skip-fdic", action="store_true")
    parser.add_argument("--skip-ffiec", action="store_true")
    parser.add_argument("--ffiec-dir", type=Path, default=ffiec.FFIEC_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # httpx logs every request URL at INFO, and the FRED key travels in the query string.
    # A scheduled run would otherwise print it into a build log.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    report = run(
        args.database,
        args.seed,
        skip_sec=args.skip_sec,
        skip_fred=args.skip_fred,
        skip_fdic=args.skip_fdic,
        skip_ffiec=args.skip_ffiec,
        ffiec_dir=args.ffiec_dir,
    )

    print(f"\nLoaded into {args.database}")
    for table, rows in report.counts.items():
        print(f"  {table:<20} {rows:>10,}")

    if report.failures:
        print(f"\n{len(report.failures)} filer(s) failed:")
        for failure in report.failures:
            print(f"  {failure}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
