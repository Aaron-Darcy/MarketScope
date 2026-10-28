from __future__ import annotations

import pathlib
from collections.abc import Callable
from datetime import date

import pytest

from marketscope.ingestion.ffiec import BulkFileError, archives, read_archive, report_date

Writer = Callable[..., pathlib.Path]


def test_items_carry_the_quarter_and_the_certificate(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    items = read_archive(bulk_archive(tmp_path))

    first = [item for item in items if item.rssd == 100 and item.schedule == "RCK"]
    assert {item.item: item.value for item in first} == {
        "RCON3485": 10,
        "RCONB563": 20,
        "RCONHK16": 30,
        "RCONHK17": 40,
        "RCFN3404": 5,
    }
    assert {item.cert for item in first} == {628}
    assert {item.report_date for item in items} == {date(2023, 12, 31)}


def test_a_blank_item_is_absent_and_a_zero_is_kept(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(
        tmp_path, rck_rows=[["100", "0", "20", "30", "40", ""], ["200"] + ["1"] * 5]
    )

    reported = {
        (item.rssd, item.item): item.value for item in read_archive(path) if item.schedule == "RCK"
    }
    assert reported[(100, "RCON3485")] == 0
    assert (100, "RCFN3404") not in reported


def test_quarters_before_2017_read_the_100000_split(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(tmp_path, "12312016", former_form=True)

    read = {item.item for item in read_archive(path) if item.schedule == "RCK"}
    assert {"RCONA514", "RCONA529"} <= read
    assert not {"RCONHK16", "RCONHK17"} & read


def test_quarter_end_balances_are_read_from_rc_and_rc_e(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    items = read_archive(bulk_archive(tmp_path))

    balances = {
        (item.schedule, item.item, item.rssd): item.value
        for item in items
        if item.schedule != "RCK"
    }
    assert balances == {
        ("RCE", "RCON2385", 100): 95,
        ("RCE", "RCON2385", 200): 9,
        ("RC", "RCON6636", 100): 90,
        ("RC", "RCFN6636", 100): 6,
        ("RC", "RCON6636", 200): 10,
    }


def test_the_report_date_is_read_from_the_file_name() -> None:
    name = pathlib.Path("FFIEC CDR Call Bulk All Schedules 09302015.zip")
    assert report_date(name) == date(2015, 9, 30)


@pytest.mark.parametrize(
    "name",
    [
        "FFIEC CDR Call Bulk All Schedules 08312015.zip",
        "FFIEC CDR Call Bulk All Schedules 13312015.zip",
        "Call Reports 09302015.zip",
    ],
)
def test_a_name_that_is_not_a_quarter_archive_is_refused(name: str) -> None:
    with pytest.raises(BulkFileError):
        report_date(pathlib.Path(name))


def test_archives_are_listed_in_quarter_order(tmp_path: pathlib.Path, bulk_archive: Writer) -> None:
    bulk_archive(tmp_path, "03312016", former_form=True)
    bulk_archive(tmp_path, "12312015", former_form=True)

    assert [report_date(path) for path in archives(tmp_path)] == [
        date(2015, 12, 31),
        date(2016, 3, 31),
    ]


def test_a_second_download_of_a_quarter_is_refused(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    bulk_archive(tmp_path)
    copy = tmp_path / "copy"
    copy.mkdir()
    bulk_archive(copy).rename(tmp_path / "FFIEC CDR Call Bulk All Schedules 12312023 (1).zip")

    with pytest.raises(BulkFileError, match=r"\(1\)"):
        archives(tmp_path)


def test_a_missing_schedule_is_refused(tmp_path: pathlib.Path, bulk_archive: Writer) -> None:
    path = bulk_archive(tmp_path, omit="RCE")

    with pytest.raises(BulkFileError, match="RCE"):
        read_archive(path)


def test_a_schedule_split_into_parts_is_refused(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(
        tmp_path,
        omit="RC",
        extra={"FFIEC CDR Call Schedule RC 12312023(1 of 2).txt": ""},
    )

    with pytest.raises(BulkFileError, match="split"):
        read_archive(path)


def test_a_schedule_without_a_required_item_is_refused(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(
        tmp_path,
        rck_items=("RCON3485", "RCONHK16", "RCONHK17", "RCFN3404"),
        rck_rows=[["100", "1", "2", "3", "4"], ["200", "1", "2", "3", "4"]],
    )

    with pytest.raises(BulkFileError, match="RCONB563"):
        read_archive(path)


@pytest.mark.parametrize(
    "items",
    [
        ("RCON3485", "RCONB563", "RCONHK16", "RCFN3404"),
        ("RCON3485", "RCONB563", "RCONA514", "RCONA529", "RCONHK16", "RCONHK17", "RCFN3404"),
    ],
)
def test_time_deposits_must_come_as_exactly_one_pair(
    tmp_path: pathlib.Path, bulk_archive: Writer, items: tuple[str, ...]
) -> None:
    rows = [["100"] + ["1"] * len(items), ["200"] + ["1"] * len(items)]
    path = bulk_archive(tmp_path, rck_items=items, rck_rows=rows)

    with pytest.raises(BulkFileError, match="time-deposit"):
        read_archive(path)


def test_a_value_that_is_not_a_whole_number_is_refused(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(tmp_path, rck_rows=[["100", "1.5", "2", "3", "4", "5"]])

    with pytest.raises(BulkFileError, match=r"1\.5"):
        read_archive(path)


def test_a_filer_missing_from_the_por_file_is_refused(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(tmp_path, por_rows=["100\t628\tFIRST BANK"])

    with pytest.raises(BulkFileError, match="RSSD 200"):
        read_archive(path)


def test_a_filer_without_a_certificate_is_refused(
    tmp_path: pathlib.Path, bulk_archive: Writer
) -> None:
    path = bulk_archive(tmp_path, por_rows=["100\t628\tFIRST BANK", "200\t0\tSECOND"])

    with pytest.raises(BulkFileError, match="certificate"):
        read_archive(path)
