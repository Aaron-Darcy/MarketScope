"""Milestone 3: why do four tier 1 filers disagree with their Call Reports?

Section 7.4 of the methodology finds four tier 1 filers whose cost of deposits misses the
Call Report figure by more than 10 basis points at the median: Citigroup, Capital One,
American Express and Morgan Stanley. Each is split here into a balance difference and an
expense difference, and each split is then tested against the cause it points to.

Capital One, American Express and Morgan Stanley disagree on consolidation scope. A
consolidated filing eliminates deposits one group entity holds at another, and the interest
paid on them, while a sum of the group's Call Reports keeps both. A holding company can
therefore report fewer deposits, or less deposit expense, than its insured banks; it cannot
report more of either from elimination alone.

Citigroup reports more deposit expense than its banks pay, which elimination cannot
produce. Its 10-K notes state that interest expense on deposits included FDIC and similar
foreign deposit insurance assessments until the fourth quarter of 2021, when they were
moved to operating expenses and 2019 to 2021 were restated. The disclosed assessments are
pinned below with the filing that reports each, and removed from the figures that contain
them to test whether they account for the gap.

Usage:
    python analysis/milestone3/disagreement_diagnosis.py
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from marketscope import store
from marketscope.deposit_cost import regulatory_cost_frame
from marketscope.metrics import cumulative_beta
from marketscope.persistence import CALIBRATION, HEADLINE, TEST, assess_pairs, eligible, read_filers
from marketscope.ranking import average_ranks
from marketscope.store import DATABASE_PATH

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

BASIS_POINTS = 10_000.0
MILLIONS = 1e6
AGREEMENT_BP = 10.0

CITIGROUP = 831001
CAPITAL_ONE = 927628
AMERICAN_EXPRESS = 4962
MORGAN_STANLEY = 895421
DISAGREEING = (CITIGROUP, CAPITAL_ONE, AMERICAN_EXPRESS, MORGAN_STANLEY)

# Capital One, N.A. Capital One Bank (USA), N.A., the card bank, merged into it in October
# 2022; ING Bank, fsb was a third insured institution in the group for most of 2012.
CAPITAL_ONE_LEAD_CERT = 4297
CAPITAL_ONE_CARD_BANK_CERT = 33954

# American Express National Bank has been the group's only insured institution since
# American Express Centurion Bank merged into it, effective with the 2018Q2 Call Report.
AMERICAN_EXPRESS_SINGLE_BANK_FROM = date(2018, 6, 30)

# The quarter Morgan Stanley's banks' deposit expense fell by nine tenths while the group's
# did not move.
MORGAN_STANLEY_BREAK = date(2015, 9, 30)

# Citigroup's deposit insurance assessments in interest expense on deposits, in millions.
# Annual figures: 2015 to 2017 from the 2017 10-K (0000831001-18-000040), Note 4; 2018 to
# 2020 from the 2020 10-K (0000831001-21-000042), Note 4; 2021 from the 2021 10-K
# (0000831001-22-000036), Note 1. Quarterly figures for 2020 and 2021 from the 2021 10-K's
# quarterly table; earlier years are published only annually.
CITIGROUP_ANNUAL_FEES: dict[int, float] = {
    2015: 1118.0,
    2016: 1145.0,
    2017: 1249.0,
    2018: 1182.0,
    2019: 781.0,
    2020: 1203.0,
    2021: 1207.0,
}
CITIGROUP_QUARTERLY_FEES: dict[date, float] = {
    date(2020, 3, 31): 225.0,
    date(2020, 6, 30): 270.0,
    date(2020, 9, 30): 375.0,
    date(2020, 12, 31): 333.0,
    date(2021, 3, 31): 340.0,
    date(2021, 6, 30): 279.0,
    date(2021, 9, 30): 293.0,
    date(2021, 12, 31): 295.0,
}
# The 2021 10-K is the first filing to present deposit insurance outside interest expense.
# A figure filed before it carries the assessment; one filed on or after it does not.
CITIGROUP_RECLASSIFIED_FROM = date(2022, 2, 28)


def quarterly_fee(quarter: date) -> float:
    """The assessment charged in a quarter, spread evenly where only a year is published."""
    if quarter in CITIGROUP_QUARTERLY_FEES:
        return CITIGROUP_QUARTERLY_FEES[quarter]
    return CITIGROUP_ANNUAL_FEES[quarter.year] / 4


def read_pairs(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Tier 1 bank-quarters of the four filers, with both measures' expense and balances.

    The XBRL expense is recovered from the cost and the two-point average base it was
    computed on, which gives back the numerator exactly, including a derived fourth quarter.
    """
    frame = connection.execute(
        f"""
        with balances as (

            select
                cik,
                quarter_end,
                total_deposits,
                interest_bearing_deposits,
                case
                    when lag(quarter_end) over (partition by cik order by quarter_end)
                        = last_day(quarter_end - interval 3 month)
                    then (interest_bearing_deposits + lag(interest_bearing_deposits) over (
                        partition by cik order by quarter_end)) / 2
                end as average_interest_bearing
            from int_deposit_balances

        )

        select
            costs.cik,
            costs.quarter_end,
            costs.q4_derived,
            costs.cost_of_deposits as xbrl_cost,
            costs.cost_of_deposits * balances.average_interest_bearing / 4 as xbrl_expense,
            balances.total_deposits as xbrl_total,
            balances.interest_bearing_deposits as xbrl_interest_bearing,
            regulatory.cost_of_deposits as regulatory_cost,
            regulatory.deposit_expense as regulatory_expense,
            regulatory.total_deposits as regulatory_total,
            regulatory.interest_bearing_deposits as regulatory_interest_bearing,
            regulatory.institutions
        from int_deposit_cost as costs
        join int_regulatory_deposit_cost as regulatory using (cik, quarter_end)
        left join balances using (cik, quarter_end)
        where costs.metric_tier = '1'
          and costs.cik in ({", ".join(str(cik) for cik in DISAGREEING)})
        order by costs.cik, costs.quarter_end
        """
    ).df()
    frame["quarter_end"] = pd.to_datetime(frame["quarter_end"]).dt.date
    frame["gap_bp"] = (frame["xbrl_cost"] - frame["regulatory_cost"]) * BASIS_POINTS
    frame["base_ratio"] = frame["xbrl_interest_bearing"] / frame["regulatory_interest_bearing"]
    frame["total_ratio"] = frame["xbrl_total"] / frame["regulatory_total"]
    frame["expense_ratio"] = frame["xbrl_expense"] / frame["regulatory_expense"]
    return frame


def split_by_filer(pairs: pd.DataFrame, names: dict[int, str]) -> list[str]:
    lines = [
        "Median over tier 1 quarters, XBRL against the sum of the group's Call Reports:",
        f"  {'':<28}{'quarters':>9}{'gap bp':>8}{'IB base':>9}{'total':>8}{'expense':>9}",
    ]
    for cik in DISAGREEING:
        rows = pairs[pairs["cik"] == cik]
        lines.append(
            f"  {names[cik][:28]:<28}{len(rows):>9}{rows['gap_bp'].abs().median():>8.1f}"
            f"{rows['base_ratio'].median():>9.3f}{rows['total_ratio'].median():>8.3f}"
            f"{rows['expense_ratio'].median():>9.3f}"
        )
    lines.append(
        "  A ratio below 1 is the holding company reporting less than its banks. Elimination "
        "of intra-group\n  balances can produce that and cannot produce a ratio above 1."
    )
    return lines


def capital_one(connection: duckdb.DuckDBPyConnection, pairs: pd.DataFrame) -> list[str]:
    """Measure Capital One against its lead bank alone while the card bank existed.

    If the card bank's deposits were held by other group entities, the consolidated filing
    eliminates them and should match the lead bank's Call Report on its own.
    """
    lead = regulatory_cost_frame(
        connection.execute(
            """
            select 'lead', cik, quarter_end, 1, total_deposits, interest_bearing_deposits,
                deposit_expense
            from main_staging.stg_fdic__financials
            where cert = ?
            """,
            [CAPITAL_ONE_LEAD_CERT],
        ).fetchall()
    )
    lead["quarter_end"] = pd.to_datetime(lead["quarter_end"]).dt.date
    card_quarters = {
        row[0]
        for row in connection.execute(
            "select quarter_end from main_staging.stg_fdic__financials where cert = ?",
            [CAPITAL_ONE_CARD_BANK_CERT],
        ).fetchall()
    }

    rows = pairs[
        (pairs["cik"] == CAPITAL_ONE)
        & (pairs["institutions"] == 2)
        & pairs["quarter_end"].isin(card_quarters)
    ].merge(
        lead[["quarter_end", "cost_of_deposits", "total_deposits"]].rename(
            columns={"cost_of_deposits": "lead_cost", "total_deposits": "lead_total"}
        ),
        on="quarter_end",
    )
    lead_gap = ((rows["xbrl_cost"] - rows["lead_cost"]) * BASIS_POINTS).abs()
    group_gap = rows["gap_bp"].abs()
    card_share = 1 - rows["lead_total"] / rows["regulatory_total"]
    return [
        "Capital One while it held two insured banks "
        f"({rows['quarter_end'].min()} to {rows['quarter_end'].max()}, {len(rows)} quarters):",
        f"  card bank's share of the two banks' deposits, median     {card_share.median():.1%}",
        f"  XBRL total deposits against both banks, median          {rows['total_ratio'].median():.3f}",
        "  XBRL total deposits against the lead bank alone, median "
        f"{(rows['xbrl_total'] / rows['lead_total']).median():>8.3f}",
        f"  cost gap against both banks: median {group_gap.median():.1f}bp, "
        f"{(group_gap <= AGREEMENT_BP).mean():.0%} within 10bp",
        f"  cost gap against the lead bank alone: median {lead_gap.median():.1f}bp, "
        f"{(lead_gap <= AGREEMENT_BP).mean():.0%} within 10bp",
    ]


def american_express(pairs: pd.DataFrame) -> list[str]:
    rows = pairs[
        (pairs["cik"] == AMERICAN_EXPRESS)
        & (pairs["quarter_end"] >= AMERICAN_EXPRESS_SINGLE_BANK_FROM)
    ]
    shortfall = (rows["regulatory_total"] - rows["xbrl_total"]) / 1e9
    return [
        f"American Express with one insured bank ({len(rows)} quarters from "
        f"{AMERICAN_EXPRESS_SINGLE_BANK_FROM}):",
        f"  quarters in which the group reports fewer total deposits than its bank  "
        f"{int((shortfall > 0).sum())} of {len(rows)}",
        f"  shortfall, median and range  ${shortfall.median():.1f}bn "
        f"(${shortfall.min():.1f}bn to ${shortfall.max():.1f}bn)",
        f"  interest-bearing base, median ratio {rows['base_ratio'].median():.3f}; "
        f"expense, median ratio {rows['expense_ratio'].median():.3f}",
    ]


def morgan_stanley(connection: duckdb.DuckDBPyConnection, pairs: pd.DataFrame) -> list[str]:
    """Compare the banks' deposit expense with the group's in every quarter both report.

    Morgan Stanley tags a complete deposit split only at year ends, so it has six tier 1
    quarters. The group's own quarterly expense, as reported in 10-Qs, shows the pattern at
    every tier.
    """
    rows = connection.execute(
        """
        select regulatory.quarter_end, regulatory.deposit_expense, reported.value,
            balances.total_deposits / regulatory.total_deposits
        from int_regulatory_deposit_cost as regulatory
        join (
            select period_end as quarter_end, value
            from (
                select *, row_number() over (
                    partition by period_start, period_end order by filed desc) as precedence
                from raw.sec_facts
                where cik = ? and tag = 'InterestExpenseDeposits'
                  and date_diff('day', period_start, period_end) between 80 and 100
            )
            where precedence = 1
        ) as reported using (quarter_end)
        join int_deposit_balances as balances using (cik, quarter_end)
        where regulatory.cik = ?
        order by regulatory.quarter_end
        """,
        [MORGAN_STANLEY, MORGAN_STANLEY],
    ).fetchall()
    before = [
        (bank - group) / MILLIONS for day, bank, group, _ in rows if day < MORGAN_STANLEY_BREAK
    ]
    after = [
        (bank - group) / MILLIONS for day, bank, group, _ in rows if day >= MORGAN_STANLEY_BREAK
    ]
    totals = [ratio for *_, ratio in rows]
    tier_one = pairs[pairs["cik"] == MORGAN_STANLEY]
    return [
        "Morgan Stanley, every quarter the group reports its own deposit expense:",
        f"  banks' expense less the group's, before {MORGAN_STANLEY_BREAK:%Y-%m}: "
        f"median ${statistics.median(before):.0f}m a quarter across {len(before)} quarters",
        f"  banks' expense less the group's, from {MORGAN_STANLEY_BREAK:%Y-%m}:   "
        f"median ${statistics.median(after):.0f}m a quarter across {len(after)} quarters",
        f"  XBRL total deposits against the banks', median {statistics.median(totals):.3f}",
        f"  tier 1 quarters: {len(tier_one)}, the last {tier_one['quarter_end'].max()}; the "
        "calibration cycle starts in 2015Q4",
    ]


def citigroup_fee_content(connection: duckdb.DuckDBPyConnection) -> dict[date, float]:
    """The assessment, in millions, inside each quarter's XBRL deposit expense.

    A quarter carries its own assessment if the filing that supplied it predates the
    reclassification. A derived fourth quarter is the fiscal year less nine months, so it
    carries the year's assessment if the annual figure predates it, less the nine months'
    if that figure does.
    """
    selected = connection.execute(
        """
        select period_start, period_end, filed
        from (
            select *, row_number() over (
                partition by period_start, period_end order by filed desc) as precedence
            from raw.sec_facts
            where cik = ? and tag = 'InterestExpenseDeposits' and period_start is not null
        )
        where precedence = 1
        """,
        [CITIGROUP],
    ).fetchall()
    filed: dict[tuple[date, date], date] = {(start, end): when for start, end, when in selected}

    content: dict[date, float] = {}
    for year in CITIGROUP_ANNUAL_FEES:
        opening = date(year, 1, 1)
        quarters = [date(year, 3, 31), date(year, 6, 30), date(year, 9, 30)]
        starts = [opening, date(year, 4, 1), date(year, 7, 1)]
        for start, end in zip(starts, quarters, strict=True):
            content[end] = (
                quarterly_fee(end) if filed[(start, end)] < CITIGROUP_RECLASSIFIED_FROM else 0.0
            )
        annual = (
            CITIGROUP_ANNUAL_FEES[year]
            if filed[(opening, date(year, 12, 31))] < CITIGROUP_RECLASSIFIED_FROM
            else 0.0
        )
        nine_months = (
            sum(quarterly_fee(end) for end in quarters)
            if filed[(opening, date(year, 9, 30))] < CITIGROUP_RECLASSIFIED_FROM
            else 0.0
        )
        content[date(year, 12, 31)] = annual - nine_months
    return content


def citigroup(connection: duckdb.DuckDBPyConnection, pairs: pd.DataFrame) -> list[str]:
    content = citigroup_fee_content(connection)
    rows = pairs[(pairs["cik"] == CITIGROUP) & pairs["quarter_end"].isin(content)].copy()
    unexplained = rows[rows["quarter_end"].apply(lambda day: day.month) == 12]
    if not unexplained["q4_derived"].all():
        raise ValueError("A Citigroup fourth quarter in the fee years is reported, not derived")

    rows["fee"] = rows["quarter_end"].map(content) * MILLIONS
    rows["adjusted_cost"] = (
        (rows["xbrl_expense"] - rows["fee"]) * 4 / (rows["xbrl_expense"] * 4 / rows["xbrl_cost"])
    )
    rows["adjusted_gap_bp"] = (rows["adjusted_cost"] - rows["regulatory_cost"]) * BASIS_POINTS

    lines = [
        "Citigroup, 2015 to 2021, against the deposit insurance assessments its 10-Ks disclose:",
        f"  {'year':<6}{'excess $m':>10}{'disclosed $m':>13}{'in XBRL $m':>11}",
    ]
    for year, group in rows.groupby(rows["quarter_end"].apply(lambda day: day.year)):
        excess = (group["xbrl_expense"] - group["regulatory_expense"]).sum() / MILLIONS
        lines.append(
            f"  {year:<6}{excess:>10.0f}{CITIGROUP_ANNUAL_FEES[int(year)]:>13.0f}"
            f"{group['fee'].sum() / MILLIONS:>11.0f}"
        )
    lines += [
        "  'In XBRL' is the assessment inside the figures the precedence rule selected: the "
        "whole year to 2018.\n  From 2019 the annual figure was restated and the first three "
        "quarters were not, so those\n  quarters carry their assessments and the derived "
        "fourth carries the same amount negative.",
        "",
        f"  cost gap as measured:           median {rows['gap_bp'].abs().median():.1f}bp, "
        f"{(rows['gap_bp'].abs() <= AGREEMENT_BP).mean():.0%} within 10bp",
        f"  cost gap, assessments removed:  median {rows['adjusted_gap_bp'].abs().median():.1f}bp, "
        f"{(rows['adjusted_gap_bp'].abs() <= AGREEMENT_BP).mean():.0%} within 10bp",
        "",
        "  Derived fourth quarters spanning the restatement:",
    ]
    for day in (date(2019, 12, 31), date(2020, 12, 31)):
        row = rows[rows["quarter_end"] == day].iloc[0]
        lines.append(
            f"    {day}  {row['xbrl_cost']:.2%} as derived, {row['adjusted_cost']:.2%} with "
            f"${-content[day]:.0f}m of assessments restored; Call Reports "
            f"{row['regulatory_cost']:.2%}"
        )
    return [*lines, "", *citigroup_beta(connection, rows)]


def citigroup_beta(connection: duckdb.DuckDBPyConnection, rows: pd.DataFrame) -> list[str]:
    """Citigroup's calibration beta without the assessments, and the headline beside it.

    A diagnostic, not a variant: specification 6.1 fixes the headline, and this changes one
    filer's figures by hand.
    """
    start, end, start_rate, end_rate, measured = connection.execute(
        """
        select start_quarter, end_quarter, start_rate_fraction, end_rate_fraction,
            deposit_beta
        from fct_deposit_beta
        where cik = ? and cycle_name = ?
        """,
        [CITIGROUP, CALIBRATION],
    ).fetchone() or (None, None, None, None, None)
    if measured is None:
        raise ValueError("Citigroup has no calibration beta")
    adjusted = rows.set_index("quarter_end")["adjusted_cost"]
    beta = cumulative_beta(adjusted[start], adjusted[end], start_rate, end_rate)
    if beta is None:
        raise ValueError("Citigroup's adjusted calibration beta does not resolve")

    sample = [filer for filer in read_filers(connection) if eligible(filer, HEADLINE)]
    calibration = [filer.beta(CALIBRATION) for filer in sample]
    test = [filer.beta(TEST) for filer in sample]
    position = next(index for index, filer in enumerate(sample) if filer.cik == CITIGROUP)
    before = average_ranks(calibration)[position]
    calibration[position] = beta
    after = average_ranks(calibration)[position]
    result = assess_pairs(calibration, test)

    return [
        f"  Calibration beta {start} to {end}: {measured:.3f} as measured, {beta:.3f} with "
        "the assessments removed at both ends",
        f"  ({start.year} and {end.year} assessments spread evenly across their quarters). "
        f"Rank of {len(sample)}: {before:g} to {after:g}.",
        "  The test cycle starts in 2022 and contains no assessment.",
        f"  Headline with that beta, as a diagnostic: Spearman {result.spearman:+.3f}, "
        f"p {result.p_value:.4f}, 95% interval {result.interval.low:+.3f} to "
        f"{result.interval.high:+.3f}",
        f"  Spread of the 2020 quarterly assessments about their mean: "
        f"{statistics.pstdev(list(CITIGROUP_QUARTERLY_FEES.values())[:4]) / (CITIGROUP_ANNUAL_FEES[2020] / 4):.0%}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    connection = store.connect(args.database, read_only=True)
    try:
        pairs = read_pairs(connection)
        names = dict(
            connection.execute(
                "select cik, registrant_name from dim_bank where cik in "
                f"({', '.join(str(cik) for cik in DISAGREEING)})"
            ).fetchall()
        )
        sections = [
            split_by_filer(pairs, names),
            capital_one(connection, pairs),
            american_express(pairs),
            morgan_stanley(connection, pairs),
            citigroup(connection, pairs),
        ]
    finally:
        connection.close()

    report = "\n\n".join("\n".join(section) for section in sections)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "disagreement_diagnosis.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
