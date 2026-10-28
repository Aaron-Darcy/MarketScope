from __future__ import annotations

import pathlib
import zipfile
from collections.abc import Callable

import pytest

# RC-K deposit items as the schedule carries them from 2017Q1, and before it, when average
# time deposits were split at $100,000 rather than $250,000.
CURRENT_RCK = ("RCON3485", "RCONB563", "RCONHK16", "RCONHK17", "RCFN3404")
FORMER_RCK = ("RCON3485", "RCONB563", "RCONA514", "RCONA529", "RCFN3404")


def _schedule(items: tuple[str, ...], rows: list[list[str]]) -> str:
    lines = [
        "\t".join(['"IDRSSD"', *items]) + "\t",
        "\t".join(["", *(f"DESCRIPTION OF {item}" for item in items)]) + "\t",
    ]
    lines += ["\t".join(row) + "\t" for row in rows]
    return "\n".join(lines) + "\n"


def write_archive(
    directory: pathlib.Path,
    stamp: str = "12312023",
    *,
    former_form: bool = False,
    rck_items: tuple[str, ...] | None = None,
    rck_rows: list[list[str]] | None = None,
    rce_rows: list[list[str]] | None = None,
    rc_rows: list[list[str]] | None = None,
    por_rows: list[str] | None = None,
    omit: str | None = None,
    extra: dict[str, str] | None = None,
) -> pathlib.Path:
    """A bulk Call Report archive for two filers, laid out as the FFIEC publishes one.

    RSSD 100 is certificate 628 and files the FFIEC 031, with foreign offices; RSSD 200 is
    certificate 3510 and leaves its foreign items blank. Figures are in thousands.
    """
    items = rck_items or (FORMER_RCK if former_form else CURRENT_RCK)
    path = directory / f"FFIEC CDR Call Bulk All Schedules {stamp}.zip"
    members = {
        f"FFIEC CDR Call Bulk POR {stamp}.txt": "\n".join(
            ['"IDRSSD"\tFDIC Certificate Number\tFinancial Institution Name']
            + (por_rows if por_rows is not None else ["100\t628\tFIRST BANK", "200\t3510\tSECOND"])
        ),
        f"FFIEC CDR Call Schedule RCK {stamp}.txt": _schedule(
            items,
            rck_rows
            if rck_rows is not None
            else [["100", "10", "20", "30", "40", "5"], ["200", "1", "2", "3", "4", ""]],
        ),
        f"FFIEC CDR Call Schedule RCE {stamp}.txt": _schedule(
            ("RCON2385",), rce_rows if rce_rows is not None else [["100", "95"], ["200", "9"]]
        ),
        f"FFIEC CDR Call Schedule RC {stamp}.txt": _schedule(
            ("RCON6636", "RCFN6636"),
            rc_rows if rc_rows is not None else [["100", "90", "6"], ["200", "10", ""]],
        ),
    }
    if omit is not None:
        members.pop(f"FFIEC CDR Call Schedule {omit} {stamp}.txt")
    members.update(extra or {})
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return path


@pytest.fixture
def bulk_archive() -> Callable[..., pathlib.Path]:
    return write_archive
