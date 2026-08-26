"""Booking-slot validation and BeNeat calendar availability rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

BOOKING_DURATION_HOURS = 2
BOOKING_FREQUENCY = "Once"
BOOKING_SERVICE = "Cleaning Service"
EARLIEST_START = time(7, 0)
LATEST_START = time(19, 30)
FLEXIBLE_LATEST_START = time(13, 30)
BANGKOK_TIME_ZONE = ZoneInfo("Asia/Bangkok")


def booking_today() -> date:
    """Return the current booking date in BeNeat's Bangkok timezone."""
    return datetime.now(BANGKOK_TIME_ZONE).date()


def booking_now() -> datetime:
    """Return the current date and time in BeNeat's Bangkok timezone."""
    return datetime.now(BANGKOK_TIME_ZONE)


@dataclass(frozen=True)
class BookingSlot:
    """The fixed-assumption booking slot requested by the user."""

    booking_date: date
    start_time: time | None
    duration_hours: int = BOOKING_DURATION_HOURS
    service: str = BOOKING_SERVICE
    frequency: str = BOOKING_FREQUENCY

    @property
    def date_text(self) -> str:
        return self.booking_date.isoformat()

    @property
    def time_text(self) -> str:
        if self.start_time is None:
            return "Any available start before 14:00"
        return self.start_time.strftime("%H:%M")


def parse_booking_slot(date_text: str, time_text: str) -> BookingSlot:
    """Parse a date and floor an optional start time to a half-hour."""
    try:
        booking_date = date.fromisoformat(date_text)
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format.") from exc
    if booking_date < booking_today():
        raise ValueError("Date cannot be in the past.")

    if not time_text:
        return BookingSlot(booking_date, None)

    try:
        start_time = time.fromisoformat(time_text)
    except ValueError as exc:
        raise ValueError("Time must use HH:MM in 24-hour format.") from exc
    start_time = time(start_time.hour, 30 if start_time.minute >= 30 else 0)
    if not EARLIEST_START <= start_time <= LATEST_START:
        raise ValueError("Time must be between 07:00 and 19:30.")
    return BookingSlot(booking_date, start_time)


def _minutes(value: str) -> int:
    parsed = time.fromisoformat(value)
    return parsed.hour * 60 + parsed.minute


def _candidate_start_times(slot: BookingSlot) -> list[time]:
    if slot.start_time is not None:
        return [slot.start_time]
    first = EARLIEST_START.hour * 60 + EARLIEST_START.minute
    last = FLEXIBLE_LATEST_START.hour * 60 + FLEXIBLE_LATEST_START.minute
    return [time(value // 60, value % 60) for value in range(first, last + 1, 30)]


def find_available_start(
    slot: BookingSlot,
    blocked_dates: list[dict[str, Any]],
    calendar_jobs: list[dict[str, Any]],
    not_before: time | None = None,
) -> time | None:
    """Return the first matching start time using BeNeat's web rules."""
    partial_blocks: list[tuple[int, int]] = []
    for blocked in blocked_dates:
        if str(blocked.get("date", "")) != slot.date_text:
            continue
        blocked_type = str(blocked.get("blocked_type", ""))
        if blocked_type == "full":
            return None
        if blocked_type == "partial":
            try:
                partial_blocks.append(
                    (
                        _minutes(str(blocked["start_time"])),
                        _minutes(str(blocked["end_time"])),
                    )
                )
            except (KeyError, ValueError):
                return None

    for candidate in _candidate_start_times(slot):
        if not_before is not None and candidate < not_before:
            continue
        start = candidate.hour * 60 + candidate.minute
        end = start + slot.duration_hours * 60
        if any(
            start < block_end and end > block_start
            for block_start, block_end in partial_blocks
        ):
            continue

        # The web client adds 30 minutes before a following job and requires
        # at least 60 minutes after a preceding job.
        buffered_end = end + 30
        conflict = False
        for job in calendar_jobs:
            try:
                job_start = _minutes(str(job["start_time"]))
                job_end = _minutes(str(job["end_time"]))
            except (KeyError, ValueError):
                return None
            if (
                job_start <= start <= job_end
                or (start < job_start and buffered_end >= job_start)
                or (start > job_end and start - job_end < 60)
            ):
                conflict = True
                break
        if not conflict:
            return candidate
    return None


def is_available(
    slot: BookingSlot,
    blocked_dates: list[dict[str, Any]],
    calendar_jobs: list[dict[str, Any]],
) -> bool:
    """Return whether any requested start time is available."""
    return find_available_start(slot, blocked_dates, calendar_jobs) is not None
