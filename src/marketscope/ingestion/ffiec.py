"""Reader for the FFIEC Central Data Repository's bulk Call Report archives.

Each archive holds one quarter's Call Reports for every filer, one tab-delimited file per
schedule. The archives are downloaded by hand and read from disk (decision 0038).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from marketscope.panel import quarter_end

FFIEC_DIR = Path("data/raw/ffiec")

ARCHIVE_PATTERN = re.compile(r"FFIEC CDR Call Bulk All Schedules (\d{2})(\d{2})(\d{4})\.zip")

# Schedule RC-K reports quarterly averages. RC-E and RC report the quarter-end balances of
# the same deposit categories, which is what endpoint averaging is measured against.
# Foreign-office items (RCFN) are carried only by the FFIEC 031, so a smaller filer's row
# leaves them blank.
SCHEDULE_ITEMS: dict[str, tuple[str, ...]] = {
    "RCK": (
        "RCON3485",
        "RCONB563",
        "RCONA514",
        "RCONA529",
        "RCONHK16",
        "RCONHK17",
        "RCFN3404",
    ),
    "RCE": ("RCON2385",),
    "RC": ("RCON6636", "RCFN6636"),
}

# Average time deposits were split at $100,000 until 2016Q4 and at $250,000 from 2017Q1. A
# quarter's RC-K carries one pair in full, and an item of either pair is optional on its own.
TIME_DEPOSIT_PAIRS: tuple[tuple[str, str], ...] = (
    ("RCONA514", "RCONA529"),
    ("RCONHK16", "RCONHK17"),
)


class BulkFileError(Exception):
    """A bulk Call Report archive is not laid out as the reader expects."""


@dataclass(frozen=True)
class CallItem:
    """One reported Call Report item, in thousands of dollars as the FFIEC publishes it."""

    report_date: date
    rssd: int
    cert: int
    schedule: str
    item: str
    value: int


def report_date(path: Path) -> date:
    """The quarter end an archive reports, read from its file name."""
    match = ARCHIVE_PATTERN.fullmatch(path.name)
    if match is None:
        raise BulkFileError(f"{path.name} is not named as a bulk Call Report archive")
    month, day, year = (int(part) for part in match.groups())
    try:
        day_reported = date(year, month, day)
    except ValueError as error:
        raise BulkFileError(f"{path.name} names no valid date") from error
    if quarter_end(day_reported) != day_reported:
        raise BulkFileError(f"{path.name} names {day_reported}, which is not a quarter end")
    return day_reported


def archives(directory: Path = FFIEC_DIR) -> list[Path]:
    """Every archive in a directory, in quarter order.

    Any other zip is refused rather than skipped: a browser saves a second download of the
    same quarter under a suffixed name, and skipping it would hide which copy was read.
    """
    return sorted(directory.glob("*.zip"), key=report_date)


def _member_text(archive: zipfile.ZipFile, name: str) -> str:
    if name not in archive.namelist():
        stem = name.removesuffix(".txt")
        if any(member.startswith(f"{stem}(") for member in archive.namelist()):
            raise BulkFileError(f"{name} is split into parts, which the reader does not join")
        raise BulkFileError(f"{archive.filename} has no {name}")
    return archive.read(name).decode("utf-8")


def _table(text: str, name: str) -> tuple[list[str], list[list[str]]]:
    """Header and data rows of one schedule file.

    The second line carries each item's description under an empty identifier field, and is
    not data.
    """
    lines = text.splitlines()
    if len(lines) < 2:
        raise BulkFileError(f"{name} has no description line")
    header = [field.strip().strip('"') for field in lines[0].split("\t")]
    if header[0] != "IDRSSD":
        raise BulkFileError(f"{name} does not start with IDRSSD")
    if lines[1].split("\t")[0].strip():
        raise BulkFileError(f"{name} has data where its description line should be")
    return header, [line.split("\t") for line in lines[2:] if line.strip()]


def _integer(text: str, where: str) -> int:
    try:
        return int(text)
    except ValueError as error:
        raise BulkFileError(f"{where}: {text!r} is not a whole number of thousands") from error


def _certificates(archive: zipfile.ZipFile, stamp: str) -> dict[int, int]:
    """FDIC certificate number of every filer, keyed by its RSSD identifier."""
    name = f"FFIEC CDR Call Bulk POR {stamp}.txt"
    lines = _member_text(archive, name).splitlines()
    certificates: dict[int, int] = {}
    for number, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if not line.strip():
            continue
        rssd = _integer(fields[0], f"{name} line {number}")
        cert = _integer(fields[1], f"{name} line {number}")
        if cert <= 0:
            raise BulkFileError(f"{name} line {number}: RSSD {rssd} has no FDIC certificate")
        certificates[rssd] = cert
    return certificates


def _required(schedule: str, header: list[str], name: str) -> tuple[str, ...]:
    """The items to read from a schedule, given the items its header carries."""
    wanted = SCHEDULE_ITEMS[schedule]
    paired = {item for pair in TIME_DEPOSIT_PAIRS for item in pair}
    missing = [item for item in wanted if item not in paired and item not in header]
    if missing:
        raise BulkFileError(f"{name} lacks {', '.join(missing)}")
    if schedule == "RCK":
        complete = [pair for pair in TIME_DEPOSIT_PAIRS if all(item in header for item in pair)]
        if len(complete) != 1:
            raise BulkFileError(f"{name} carries {len(complete)} complete time-deposit pairs")
    return tuple(item for item in wanted if item in header)


def read_archive(path: Path) -> list[CallItem]:
    """Every reported deposit item in one quarter's archive.

    A blank field is an item the filer does not report, and produces no row rather than a
    zero; a reported zero is kept.
    """
    quarter = report_date(path)
    stamp = f"{quarter:%m%d%Y}"
    items: list[CallItem] = []
    with zipfile.ZipFile(path) as archive:
        certificates = _certificates(archive, stamp)
        for schedule in SCHEDULE_ITEMS:
            name = f"FFIEC CDR Call Schedule {schedule} {stamp}.txt"
            header, rows = _table(_member_text(archive, name), name)
            columns = {item: header.index(item) for item in _required(schedule, header, name)}
            for row in rows:
                rssd = _integer(row[0], f"{name} identifier")
                if rssd not in certificates:
                    raise BulkFileError(f"{name}: RSSD {rssd} is not in the POR file")
                for item, column in columns.items():
                    text = row[column].strip() if column < len(row) else ""
                    if not text:
                        continue
                    items.append(
                        CallItem(
                            report_date=quarter,
                            rssd=rssd,
                            cert=certificates[rssd],
                            schedule=schedule,
                            item=item,
                            value=_integer(text, f"{name} RSSD {rssd} {item}"),
                        )
                    )
    return items
