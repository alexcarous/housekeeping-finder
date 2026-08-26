from datetime import date
from datetime import time as dt_time

import pytest

from beneat.availability import BookingSlot
from beneat.cli import (
    CancelSelectionError,
    select_booking_slot,
    select_district,
    select_province,
    write_html,
)
from beneat.ranking import CleanerRecord, rank_cleaners

PROVINCES = [
    {"id": 1, "name_th": "กรุงเทพมหานคร", "name_en": "Bangkok"},
    {"id": 11, "name_th": "ชลบุรี", "name_en": "Chon Buri"},
]

DISTRICTS = [
    {"id": 39, "name_th": "เขตวัฒนา", "name_en": "Khet Watthana"},
    {"id": 9, "name_th": "เขตพระโขนง", "name_en": "Khet Phra Khanong"},
]


def test_select_province(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert select_province(PROVINCES) == PROVINCES[1]


def test_select_district_sorted_without_khet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert select_district(DISTRICTS) == DISTRICTS[1]
    output = capsys.readouterr().out
    assert "(Phra Khanong)" in output
    assert "(Watthana)" in output
    assert "Khet" not in output
    assert output.index("Phra Khanong") < output.index("Watthana")


def test_select_province_blank_cancels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(CancelSelectionError):
        select_province(PROVINCES)


def test_select_province_out_of_range_cancels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "99")
    with pytest.raises(CancelSelectionError):
        select_province(PROVINCES)


def test_select_booking_slot_retries_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["bad-date", "10:00", "2099-06-10", "09:30"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    slot = select_booking_slot()

    assert slot.date_text == "2099-06-10"
    assert slot.time_text == "09:30"
    assert slot.duration_hours == 2
    assert slot.service == "Cleaning Service"
    assert slot.frequency == "Once"


def test_select_booking_slot_allows_blank_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter(["2099-06-10", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    slot = select_booking_slot()

    assert slot.start_time is None
    assert slot.time_text == "Any available start before 14:00"


def _record(pid: int, name: str, jobs: int, repeat: int) -> CleanerRecord:
    return CleanerRecord(
        professional_id=pid,
        name=name,
        job_qty=jobs,
        repeat_booking_rate=repeat,
        rating=4.9,
        rating_qty=10,
        is_excellent=True,
        profile_url=f"https://beneat.co/cleaner/{pid}",
    )


def test_write_html_table(tmp_path: pytest.TempPathFactory) -> None:
    ranked = rank_cleaners(
        [_record(1, "Krongkan P.", 1318, 91), _record(2, "Pimkamon R.", 894, 82)]
    )
    ranked[0].record.available_start_time = "09:30"
    target = tmp_path / "output" / "RESULTS.html"
    slot = BookingSlot(date(2099, 6, 10), dt_time(9, 30))
    write_html(ranked, "กรุงเทพมหานคร", "เขตพระโขนง", slot, str(target))

    content = target.read_text(encoding="utf-8")
    assert "เขตพระโขนง" in content
    assert "Krongkan P." in content
    assert "<td>1</td>" in content
    assert "<td>2</td>" in content
    assert 'href="https://beneat.co/cleaner/1"' in content
    assert 'target="_blank"' in content
    assert 'rel="noopener noreferrer"' in content
    assert "2099-06-10" in content
    assert "09:30" in content
    assert "2 hours" in content
    assert "Available start" in content
    assert "09:30" in content


def test_empty_html_explains_no_availability(
    tmp_path: pytest.TempPathFactory,
) -> None:
    target = tmp_path / "output" / "RESULTS.html"
    slot = BookingSlot(date(2099, 6, 10), None)

    write_html([], "กรุงเทพมหานคร", "เขตพระโขนง", slot, str(target))

    content = target.read_text(encoding="utf-8")
    assert "No qualifying cleaners were available for this booking slot" in content
