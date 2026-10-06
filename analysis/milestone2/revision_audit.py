"""Milestone 2: what are the revisions the precedence rule resolves?

`int_fact_revisions` records every change of value for a us-gaap period. A change can be
a correction, a reclassification or recast, or something with no economic content at all:
the same figure republished at a coarser rounding, a sign convention reversed, a scale
error in one of two filings. Before restatement frequency means anything, and before the
precedence rule can be judged, the mechanical changes have to be separated from the rest.

The metric reads a small set of concepts, so the revisions that can move a cost of
deposits are reported separately, and those whose replacing value is the one the panel
uses are listed.

Usage:
    python analysis/milestone2/revision_audit.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.metrics import (
    EXPENSE_REPORTED_TAG,
    IB_REPORTED_TAG,
    NIB_REPORTED_TAG,
    TOTAL_DEPOSITS_TAG,
)
from marketscope.panel import PANEL_TAGS
from marketscope.restatements import RevisionKind, classify_revision
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

# The concepts a tier 1 or tier 2 cost of deposits is computed from directly.
HEADLINE_CONCEPTS = frozenset(
    {EXPENSE_REPORTED_TAG, IB_REPORTED_TAG, NIB_REPORTED_TAG, TOTAL_DEPOSITS_TAG}
)


def read_revisions(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    frame = connection.execute(
        """
        select revisions.*, members.registrant_name
        from int_fact_revisions as revisions
        join raw.universe as members using (cik)
        """
    ).df()
    frame["kind"] = [
        classify_revision(previous, revised, form).value
        for previous, revised, form in zip(
            frame["previous_value"], frame["revised_value"], frame["revised_form"], strict=True
        )
    ]
    frame["relative_change"] = (frame["revised_value"] - frame["previous_value"]).abs() / frame[
        "previous_value"
    ].abs().where(frame["previous_value"] != 0)
    frame["scope"] = "other"
    frame.loc[frame["tag"].isin(PANEL_TAGS), "scope"] = "panel"
    frame.loc[frame["tag"].isin(HEADLINE_CONCEPTS), "scope"] = "headline"
    return frame


def summarise(frame: pd.DataFrame) -> str:
    kinds = [kind.value for kind in RevisionKind]
    lines = [
        "Revisions to us-gaap values, by what changed",
        "",
        f"Revisions: {len(frame):,} across {frame['cik'].nunique()} filers",
        "",
        f"{'kind':<12} {'all':>8} {'share':>7} {'median change':>14} "
        f"{'panel':>7} {'headline':>9} {'headline, current':>18}",
    ]
    for kind in kinds:
        rows = frame[frame["kind"] == kind]
        panel = rows[rows["scope"] != "other"]
        headline = rows[rows["scope"] == "headline"]
        lines.append(
            f"{kind:<12} {len(rows):>8,} {len(rows) / len(frame):>7.1%} "
            f"{rows['relative_change'].median():>14.3f} {len(panel):>7,} {len(headline):>9,} "
            f"{int(headline['is_current'].sum()):>18,}"
        )

    substantive = frame[frame["kind"] == RevisionKind.SUBSTANTIVE.value]
    lines += [
        "",
        "Substantive revisions, first carried by:",
        *(
            f"  {form:<8} {count:>7,}"
            for form, count in substantive["revised_form"].value_counts().items()
        ),
        "",
        "Substantive revisions, size of the change relative to the replaced value:",
    ]
    for share in (0.25, 0.5, 0.75, 0.9):
        lines.append(
            f"  {share:.0%} quantile  {substantive['relative_change'].quantile(share):.3f}"
        )

    current = substantive[(substantive["scope"] == "headline") & substantive["is_current"]]
    lines += [
        "",
        "Substantive revisions to headline concepts that the panel now uses, by filer:",
        f"{'filer':<40} {'revisions':>9} {'median change':>14}",
    ]
    by_filer = (
        current.groupby("registrant_name")["relative_change"]
        .agg(["count", "median"])
        .sort_values("count", ascending=False)
    )
    for name, row in by_filer.iterrows():
        lines.append(f"{str(name)[:40]:<40} {int(row['count']):>9} {row['median']:>14.3f}")

    return "\n".join(lines)


def run(database: Path, output_dir: Path) -> pd.DataFrame:
    connection = store.connect(database, read_only=True)
    try:
        frame = read_revisions(connection)
    finally:
        connection.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    (
        frame.groupby(["kind", "scope"])
        .agg(revisions=("tag", "size"), current=("is_current", "sum"))
        .reset_index()
        .to_csv(output_dir / "revision_kinds.csv", index=False)
    )
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    frame = run(args.database, args.output_dir)
    if frame.empty:
        print("int_fact_revisions holds no revisions.")
        return 1

    report = summarise(frame)
    print(report)
    (args.output_dir / "revision_audit.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
