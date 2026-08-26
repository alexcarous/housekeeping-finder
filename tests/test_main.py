import argparse
from datetime import date, time, timedelta

import pytest

from beneat.availability import BookingSlot, booking_today
from beneat.main import (
    _fetch_and_gate_cleaners,
    _filter_available,
    _positive_worker_count,
)
from beneat.ranking import CleanerRecord


def _record(professional_id: int) -> CleanerRecord:
    return CleanerRecord(
        professional_id=professional_id,
        name=f"Cleaner {professional_id}",
        job_qty=10,
        repeat_booking_rate=80,
        rating=5.0,
        rating_qty=5,
        is_excellent=True,
        profile_url=f"https://beneat.co/cleaner/{professional_id}",
    )


def test_worker_count_must_be_positive() -> None:
    assert _positive_worker_count("8") == 8
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_worker_count("0")


def test_filter_available_removes_blocked_cleaner(monkeypatch: object) -> None:
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar",
        lambda professional_id, booking_date: (
            {
                "blocked_dates": [
                    {"date": booking_date, "blocked_type": "full"}
                ]
            }
            if professional_id == 2
            else {"blocked_dates": []}
        ),
    )
    monkeypatch.setattr(
        "beneat.main.fetch_professional_calendar_jobs",
        lambda _professional_id, _booking_date: [],
    )
    slot = BookingSlot(date(2099, 6, 10), time(10, 0))

    result = _filter_available([_record(1), _record(2)], slot, workers=1)

    assert [record.professional_id for record in result] == [1]


def test_filter_available_respects_same_day_flag(monkeypatch: object) -> None:
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
    slot = BookingSlot(booking_today(), time(10, 0))

    assert _filter_available([_record(1)], slot, workers=1) == []


def test_same_day_flag_does_not_affect_future_dates(monkeypatch: object) -> None:
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
    slot = BookingSlot(date.today() + timedelta(days=1), time(10, 0))

    result = _filter_available([_record(1)], slot, workers=1)
    assert [record.professional_id for record in result] == [1]
    assert result[0].available_start_time == "10:00"


def test_flexible_time_records_first_match(monkeypatch: object) -> None:
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
    slot = BookingSlot(date(2099, 6, 10), None)

    result = _filter_available([_record(1)], slot, workers=1)

    assert result[0].available_start_time == "10:00"


def test_listing_scan_displays_progress(
    monkeypatch: object, capsys: object
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
