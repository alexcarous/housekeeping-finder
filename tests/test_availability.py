from datetime import date
from datetime import time as dt_time

import pytest

from beneat.availability import (
    BookingSlot,
    booking_today,
    find_available_start,
    is_available,
    parse_booking_slot,
)

SLOT = BookingSlot(date(2099, 6, 10), dt_time(10, 0))


def test_booking_today_uses_bangkok_date() -> None:
    assert booking_today().isoformat() >= "2026-01-01"


def test_parse_booking_slot_applies_fixed_assumptions() -> None:
    slot = parse_booking_slot("2099-06-10", "09:30")

    assert slot.duration_hours == 2
    assert slot.service == "Cleaning Service"
    assert slot.frequency == "Once"


@pytest.mark.parametrize("start", ["06:30", "20:00", "not-time"])
def test_parse_booking_slot_rejects_unsupported_times(start: str) -> None:
    with pytest.raises(ValueError):
        parse_booking_slot("2099-06-10", start)


@pytest.mark.parametrize(
    ("entered", "expected"),
    [("08:15", "08:00"), ("08:31", "08:30"), ("19:59", "19:30")],
)
def test_parse_booking_slot_floors_to_half_hour(
    entered: str, expected: str
) -> None:
    assert parse_booking_slot("2099-06-10", entered).time_text == expected


def test_blank_time_finds_first_available_start_before_1400() -> None:
    slot = parse_booking_slot("2099-06-10", "")
    jobs = [{"start_time": "07:00", "end_time": "09:00"}]

    matched = find_available_start(slot, [], jobs)

    assert matched == dt_time(10, 0)


def test_blank_time_can_use_start_before_a_later_partial_block() -> None:
    slot = parse_booking_slot("2099-06-10", "")
    blocks = [
        {
            "date": slot.date_text,
            "blocked_type": "partial",
            "start_time": "14:00",
            "end_time": "19:30",
        }
    ]
    assert find_available_start(slot, blocks, []) == dt_time(7, 0)


def test_flexible_time_skips_starts_before_current_time() -> None:
    slot = parse_booking_slot("2099-06-10", "")

    matched = find_available_start(slot, [], [], not_before=dt_time(10, 10))

    assert matched == dt_time(10, 30)


def test_available_with_empty_calendar() -> None:
    assert is_available(SLOT, [], [])


def test_full_day_block_is_unavailable() -> None:
    blocks = [{"date": SLOT.date_text, "blocked_type": "full"}]
    assert not is_available(SLOT, blocks, [])


def test_partial_blocked_window_is_unavailable() -> None:
    blocks = [
        {
            "date": SLOT.date_text,
            "blocked_type": "partial",
            "start_time": "12:00",
            "end_time": "17:00",
        }
    ]
    assert is_available(SLOT, blocks, [])
    blocks[0]["start_time"] = "09:30"
    blocks[0]["end_time"] = "12:00"
    assert not is_available(SLOT, blocks, [])


def test_existing_job_and_buffers_are_unavailable() -> None:
    assert not is_available(
        SLOT, [], [{"start_time": "11:00", "end_time": "13:00"}]
    )
    assert not is_available(
        SLOT, [], [{"start_time": "08:30", "end_time": "09:30"}]
    )
    assert is_available(
        SLOT, [], [{"start_time": "07:00", "end_time": "09:00"}]
    )
