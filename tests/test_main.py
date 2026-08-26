import argparse
from datetime import date, time, timedelta

import pytest

from beneat.availability import BookingSlot, booking_today
from beneat.main import (
    _fetch_and_gate_cleaners,
    _filter_available,
    _positive_worker_count,
    _serves_district,
)
from beneat.ranking import CleanerRecord


def _record(professional_id: int) -> CleanerRecord:
    return CleanerRecord(
        professional_id,
        f"Cleaner {professional_id}",
        10,
        80,
        5.0,
        5,
        True,
        f"https://beneat.co/cleaner/{professional_id}",
    )


def test_worker_count_must_be_positive() -> None:
    assert _positive_worker_count("8") == 8
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_worker_count("0")


def test_filter_available_removes_blocked_cleaner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar",
        lambda professional_id, booking_date: (
            {"blocked_dates": [{"date": booking_date, "blocked_type": "full"}]}
            if professional_id == 2
            else {"blocked_dates": []}
        ),
    )
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar_jobs",
        lambda _professional_id, _booking_date: [],
    )
    result = _filter_available(
        [_record(1), _record(2)], BookingSlot(date(2099, 6, 10), time(10, 0)), workers=1
    )
    assert [record.professional_id for record in result] == [1]


def test_filter_available_respects_same_day_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar",
        lambda _professional_id, _booking_date: {
            "blocked_dates": [],
            "is_available_today": False,
        },
    )
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar_jobs",
        lambda _professional_id, _booking_date: [],
    )
    assert (
        _filter_available(
            [_record(1)], BookingSlot(booking_today(), time(10, 0)), workers=1
        )
        == []
    )


def test_same_day_flag_does_not_affect_future_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar",
        lambda _professional_id, _booking_date: {
            "blocked_dates": [],
            "is_available_today": False,
        },
    )
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar_jobs",
        lambda _professional_id, _booking_date: [],
    )
    result = _filter_available(
        [_record(1)],
        BookingSlot(date.today() + timedelta(days=1), time(10, 0)),
        workers=1,
    )
    assert [record.professional_id for record in result] == [1]
    assert result[0].available_start_time == "10:00"


def test_flexible_time_records_first_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar",
        lambda _professional_id, _booking_date: {"blocked_dates": []},
    )
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar_jobs",
        lambda _professional_id, _booking_date: [
            {"start_time": "07:00", "end_time": "09:00"}
        ],
    )
    result = _filter_available(
        [_record(1)], BookingSlot(date(2099, 6, 10), None), workers=1
    )
    assert result[0].available_start_time == "10:00"


def test_listing_scan_displays_progress(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "beneat.main.iter_professionals",
        lambda *_args, **_kwargs: iter(
            [
                {"id": 1, "is_excellent": False},
                {"id": 2, "is_excellent": True, "job_qty": 5},
            ]
        ),
    )
    result = _fetch_and_gate_cleaners(9)
    assert [record.professional_id for record in result] == [2]
    output = capsys.readouterr().out
    assert "Scanning cleaner listings" in output
    assert "Scanned: 2 | excellent candidates: 1" in output


def test_service_area_must_include_selected_district() -> None:
    detail = {"professional_districts": [{"district_id": 55}, {"district_id": 49}]}
    assert _serves_district(detail, 49)
    assert not _serves_district(detail, 9)


def test_missing_service_area_is_not_assumed_to_match() -> None:
    assert not _serves_district({}, 9)
