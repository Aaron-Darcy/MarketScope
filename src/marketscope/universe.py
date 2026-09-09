from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from marketscope.banks import DEPOSIT_INTEREST_EXPENSE_TAGS
from marketscope.ingestion.sec import SecClient, normalise_entity_name

ASSETS_TAG = "Assets"
DEPOSITS_TAG = "Deposits"

# Quarter-end instants spanning the study window. Ranking on the peak of this window
# rather than on a current snapshot keeps institutions that stopped filing inside it,
# which is the same survivorship argument that pins the terminal filers.
BALANCE_FRAMES: tuple[str, ...] = (
    "CY2015Q4I",
    "CY2016Q4I",
    "CY2017Q4I",
    "CY2018Q4I",
    "CY2019Q4I",
    "CY2020Q4I",
    "CY2021Q4I",
    "CY2022Q4I",
    "CY2023Q3I",
    "CY2023Q4I",
)

# Flow concepts are published against durations, so they are read from annual frames.
# The instant frames that carry balances return 404 for them.
FLOW_FRAMES: tuple[str, ...] = tuple(f"CY{year}" for year in range(2015, 2024))

# SIC 6020 is a group heading rather than an assignable code: EDGAR returns no entities
# for it. It is retained because the specification names it and its emptiness is a fact
# about EDGAR worth asserting rather than a filter silently doing nothing.
BANK_SIC_CODES: tuple[str, ...] = ("6020", "6021", "6022", "6035", "6036")

# Deposits as a share of assets, above which a filer is treated as deposit funded.
# Across filers above $20bn of assets the largest non-depository ratio is 0.024 and the
# smallest depository ratio is 0.210, so any threshold inside that gap selects the same
# set and the precise value carries no weight.
DEPOSIT_FUNDED_FLOOR = 0.05

UNIVERSE_SIZE = 50

EARLIEST_FISCAL_YEAR = 2015

# Annual report forms of a foreign private issuer. A filer using these instead of a 10-K
# is outside the specification's scope rather than a filer whose coverage has failed, and
# the two are counted separately.
FOREIGN_ANNUAL_FORMS: frozenset[str] = frozenset({"20-F", "40-F"})

# Filers admitted regardless of where they rank. Ranking on peak assets already keeps an
# institution that shrank or stopped filing inside the window, so this is not a
# survivorship patch: it admits institutions the ranking cannot express a reason for.
# They are additional to the fifty rather than displacing the smallest member, because
# displacing a bank that was larger would distort the ranking to fit a bank that was not.
PINNED_FILERS: dict[int, str] = {
    1102112: (
        "PacWest Bancorp. Peaked at 41bn and ranks outside the fifty, but is one of the "
        "two terminal filers decision 0010 selected: it spans both cycles, sustained "
        "acute deposit outflow through 2023 and exited by merger rather than closure, "
        "which exercises the terminal filer and entity event paths together"
    ),
}


class EdgarCoverage(StrEnum):
    """How far into EDGAR an institution can actually be followed."""

    COVERED = "covered"
    NO_TEN_K = "no_ten_k"
    NO_XBRL = "no_xbrl"
    ABSENT = "absent"


class FilerSource(Protocol):
    """The part of the EDGAR client that describing a filer depends on.

    Narrowing the dependency to three calls keeps selection testable without a network
    and states what universe construction actually needs, which the full client does not.
    """

    def submissions(self, cik: int | str) -> dict[str, Any]: ...

    def has_company_facts(self, cik: int | str) -> bool: ...

    def filing_history(self, cik: int | str) -> list[dict[str, Any]]: ...


class PinnedFilerError(Exception):
    """Raised when a pinned CIK cannot be seated in the universe."""


class Exclusion(StrEnum):
    """Why a filer large enough to rank is nonetheless outside the universe."""

    NOT_DEPOSIT_FUNDED = "not_deposit_funded"
    NO_DEPOSIT_INTEREST = "no_deposit_interest"
    FOREIGN_PRIVATE_ISSUER = "foreign_private_issuer"


@dataclass(frozen=True)
class Candidate:
    """A filer observed in the XBRL frames, before any universe rule is applied."""

    cik: int
    entity_name: str
    peak_assets: float
    peak_deposits: float
    deposit_share: float
    pays_deposit_interest: bool

    @property
    def is_deposit_funded(self) -> bool:
        return self.deposit_share >= DEPOSIT_FUNDED_FLOOR

    @property
    def exclusion(self) -> Exclusion | None:
        """Why the frames alone rule this filer out, if they do.

        Deposit funding is not sufficient on its own: an insurer tags annuity and other
        deposit-type contracts under the same ``Deposits`` concept a bank uses for its
        funding base. Requiring the filer to also report interest paid on deposits
        separates a deposit-taking institution from one merely holding a balance the
        taxonomy happens to call deposits.
        """
        if not self.is_deposit_funded:
            return Exclusion.NOT_DEPOSIT_FUNDED
        if not self.pays_deposit_interest:
            return Exclusion.NO_DEPOSIT_INTEREST
        return None


@dataclass(frozen=True)
class Filer:
    """A ranked candidate with the registrant metadata the remaining rules depend on."""

    candidate: Candidate
    registrant_name: str
    sic: str | None
    sic_description: str | None
    tickers: tuple[str, ...]
    exchanges: tuple[str, ...]
    first_ten_k: date | None
    last_ten_k: date | None
    ten_k_count: int
    foreign_annual_forms: int
    coverage: EdgarCoverage
    pinned_reason: str | None = None

    @property
    def cik(self) -> int:
        return self.candidate.cik

    @property
    def has_bank_sic(self) -> bool:
        return self.sic in BANK_SIC_CODES

    @property
    def is_pinned(self) -> bool:
        return self.pinned_reason is not None

    @property
    def is_foreign_private_issuer(self) -> bool:
        """Whether the filer reports to the SEC as a foreign issuer rather than a domestic one.

        A filer that has never lodged a 10-K but files 20-F or 40-F is a foreign private
        issuer. It is out of the specification's scope, which covers US bank holding
        companies, and excluding it is a scope judgement rather than a coverage failure.
        """
        return self.ten_k_count == 0 and self.foreign_annual_forms > 0

    @property
    def exclusion(self) -> Exclusion | None:
        if self.is_foreign_private_issuer:
            return Exclusion.FOREIGN_PRIVATE_ISSUER
        return self.candidate.exclusion


def peak_by_cik(frames: Mapping[str, Mapping[int, float]]) -> dict[int, float]:
    """Largest value each filer reported for a concept across the study window."""
    peaks: dict[int, float] = {}
    for values in frames.values():
        for cik, value in values.items():
            if value > peaks.get(cik, float("-inf")):
                peaks[cik] = value
    return peaks


def deposit_share(
    assets: Mapping[str, Mapping[int, float]],
    deposits: Mapping[str, Mapping[int, float]],
    cik: int,
) -> float:
    """Highest deposits-to-assets ratio a filer reached, comparing within a period.

    Ratios are formed inside a single frame rather than from separately taken peaks, so a
    filer whose assets and deposits peaked in different years is not credited with a ratio
    it never reported.
    """
    best = 0.0
    for frame, frame_assets in assets.items():
        total = frame_assets.get(cik)
        held = deposits.get(frame, {}).get(cik)
        if total is None or held is None or total <= 0:
            continue
        best = max(best, held / total)
    return best


def build_candidates(
    assets: Mapping[str, Mapping[int, float]],
    deposits: Mapping[str, Mapping[int, float]],
    payers: Iterable[int],
    names: Mapping[int, str],
) -> list[Candidate]:
    """Assemble every filer reporting assets into candidates the universe rules can judge."""
    peak_assets = peak_by_cik(assets)
    peak_deposits = peak_by_cik(deposits)
    paying = set(payers)

    return [
        Candidate(
            cik=cik,
            entity_name=names.get(cik, ""),
            peak_assets=value,
            peak_deposits=peak_deposits.get(cik, 0.0),
            deposit_share=deposit_share(assets, deposits, cik),
            pays_deposit_interest=cik in paying,
        )
        for cik, value in peak_assets.items()
    ]


def rank(candidates: Iterable[Candidate]) -> list[Candidate]:
    """Order the candidates the frames admit, largest peak total assets first.

    Total assets is the ranking basis the specification names and the basis the Federal
    Reserve uses to rank holding companies, so it is kept even though the metric under
    study is a deposit metric. The screens, not the ranking, keep non-depository balance
    sheets out.
    """
    eligible = [candidate for candidate in candidates if candidate.exclusion is None]
    eligible.sort(key=lambda candidate: (-candidate.peak_assets, candidate.cik))
    return eligible


def ten_k_history(filings: Iterable[Mapping[str, Any]]) -> list[date]:
    """Report dates of every 10-K a filer has published, oldest first.

    Amendments are excluded: a 10-K/A restates a period the original already covered, so
    counting it would overstate how many fiscal years a filer actually reported.
    """
    dates: list[date] = []
    for filing in filings:
        if filing.get("form") != "10-K":
            continue
        report_date = filing.get("reportDate")
        if not report_date:
            continue
        dates.append(date.fromisoformat(str(report_date)))
    return sorted(dates)


def count_foreign_annual_forms(filings: Iterable[Mapping[str, Any]]) -> int:
    """Number of foreign annual reports a filer has lodged."""
    return sum(1 for filing in filings if filing.get("form") in FOREIGN_ANNUAL_FORMS)


def classify_coverage(has_facts: bool, ten_k_dates: Iterable[date]) -> EdgarCoverage:
    """Grade how far a filer can be followed, from XBRL presence and 10-K recency.

    ``ABSENT`` is never assigned here. An institution that files nothing with the SEC has
    no CIK to classify, so it can only be identified against an external register of
    institutions and is recorded by the reference audit rather than by this function.
    """
    if not has_facts:
        return EdgarCoverage.NO_XBRL
    if not any(reported.year >= EARLIEST_FISCAL_YEAR for reported in ten_k_dates):
        return EdgarCoverage.NO_TEN_K
    return EdgarCoverage.COVERED


def collect_frames(
    client: SecClient, tag: str, frames: Sequence[str]
) -> dict[str, dict[int, float]]:
    """Fetch one concept across a set of frames, skipping periods the concept does not cover."""
    collected: dict[str, dict[int, float]] = {}
    for frame in frames:
        collected[frame] = client.frame(tag, frame)
    return collected


def collect_deposit_interest_payers(client: SecClient) -> dict[str, set[int]]:
    """Filers reporting interest paid on deposits, per candidate concept.

    The aggregate concept alone is not enough. A filer may tag only leaf categories such
    as time or savings deposits and never the total, which is the tagging pattern already
    recorded against M&T Bank, so the whole candidate concept list is swept and the
    result is reported per concept. A concept that no filer uses in any year is visible
    as an empty set rather than folded silently into the union.
    """
    return {
        tag: {cik for frame in FLOW_FRAMES for cik in client.frame_or_empty(tag, frame)}
        for tag in DEPOSIT_INTEREST_EXPENSE_TAGS
    }


def collect_frame_names(client: SecClient, tag: str, frames: Sequence[str]) -> dict[int, str]:
    """Entity names as the frames report them, for labelling before identity is resolved.

    These are the names attached to whichever entity published a fact and are not the
    registrant. They are replaced by the submissions name once a filer enters the universe,
    for the reason recorded against CIK 70858 in the decision record.
    """
    names: dict[int, str] = {}
    for frame in frames:
        payload = client.frame_payload(tag, frame)
        for row in payload.get("data", []):
            names.setdefault(int(row["cik"]), str(row.get("entityName", "")))
    return names


def describe(client: FilerSource, candidate: Candidate) -> Filer:
    """Resolve a candidate's registrant metadata, filing history and coverage grade."""
    submissions = client.submissions(candidate.cik)
    has_facts = client.has_company_facts(candidate.cik)
    filings = client.filing_history(candidate.cik) if has_facts else []
    ten_ks = ten_k_history(filings)

    return Filer(
        candidate=candidate,
        registrant_name=normalise_entity_name(str(submissions.get("name", ""))),
        sic=str(submissions.get("sic")) or None,
        sic_description=str(submissions.get("sicDescription")) or None,
        tickers=tuple(submissions.get("tickers", [])),
        exchanges=tuple(submissions.get("exchanges", [])),
        first_ten_k=ten_ks[0] if ten_ks else None,
        last_ten_k=ten_ks[-1] if ten_ks else None,
        ten_k_count=len(ten_ks),
        foreign_annual_forms=count_foreign_annual_forms(filings),
        coverage=classify_coverage(has_facts, ten_ks),
    )


def select(
    client: FilerSource,
    ranked: Sequence[Candidate],
    size: int = UNIVERSE_SIZE,
    pinned: Mapping[int, str] | None = None,
) -> tuple[list[Filer], list[Filer]]:
    """Walk the ranking, describing filers until the universe is full, then add the pins.

    Filers are described lazily rather than in a fixed oversized slate, so the number of
    company facts and submissions requests scales with how many exclusions are actually
    encountered rather than with a guess about how many there will be.

    A pinned filer already inside the top ``size`` is left where it is and marked, so the
    universe carries one row per filer whether or not the ranking would have reached it.
    """
    pins = dict(PINNED_FILERS if pinned is None else pinned)
    members: list[Filer] = []
    excluded: list[Filer] = []

    for candidate in ranked:
        if len(members) >= size:
            break
        filer = describe(client, candidate)
        if filer.exclusion is None:
            members.append(replace(filer, pinned_reason=pins.get(filer.cik)))
        else:
            excluded.append(filer)

    seated = {filer.cik for filer in members}
    by_cik = {candidate.cik: candidate for candidate in ranked}

    for cik, reason in pins.items():
        if cik in seated:
            continue
        pin = by_cik.get(cik)
        if pin is None:
            raise PinnedFilerError(
                f"CIK {cik} is pinned into the universe but does not survive the "
                f"membership screens, so there is nothing to add. Remove the pin or "
                f"record why the screens should not apply to it."
            )
        members.append(replace(describe(client, pin), pinned_reason=reason))

    return members, excluded


def bank_sic_entities(client: SecClient) -> dict[str, list[int]]:
    """Every EDGAR entity carrying one of the specification's bank SIC codes."""
    return {sic: client.companies_by_sic(sic) for sic in BANK_SIC_CODES}
