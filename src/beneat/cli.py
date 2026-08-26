"""Interactive CLI prompts, progress display, and HTML output."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any

from beneat.availability import BookingSlot, parse_booking_slot
from beneat.ranking import RankedCleaner


class CancelSelectionError(Exception):
    """Raised when the user cancels an interactive prompt."""


def _print_menu(items: Sequence[dict[str, Any]]) -> None:
    """Print a numbered menu with bilingual names if available."""
    for index, item in enumerate(items, start=1):
        name_th = str(item.get("name_th") or item.get("name", ""))
        name_en = str(item.get("name_en") or "")
        if name_en and name_en != name_th:
            print(f"  {index:>2}. {name_th} ({name_en})")
        else:
            print(f"  {index:>2}. {name_th}")


def _read_choice(max_choice: int, prompt: str) -> int:
    """Read a 1-based choice from stdin, or exit on Ctrl-C / EOF."""
    try:
        raw = input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        raise CancelSelectionError from None
    if not raw:
        raise CancelSelectionError
    try:
        choice = int(raw)
    except ValueError:
        raise CancelSelectionError from None
    if choice < 1 or choice > max_choice:
        raise CancelSelectionError
    return choice


def select_province(provinces: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Prompt the user to pick a province, returning its record."""
    print("Select a province:")
    _print_menu(provinces)
    choice = _read_choice(len(provinces), "Province number (or blank to cancel): ")
    return provinces[choice - 1]


def select_district(districts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Prompt with districts sorted by English name without a Khet prefix."""
    ordered = sorted(districts, key=_district_sort_key)
    print("Select a district:")
    for index, item in enumerate(ordered, start=1):
        name_th = str(item.get("name_th") or item.get("name", ""))
        name_en = _district_english_name(item)
        if name_en and name_en != name_th:
            print(f"  {index:>2}. {name_th} ({name_en})")
        else:
            print(f"  {index:>2}. {name_th}")
    choice = _read_choice(len(ordered), "District number (or blank to cancel): ")
    return ordered[choice - 1]


def _district_english_name(item: dict[str, Any]) -> str:
    name = str(item.get("name_en") or "")
    return name[5:] if name.casefold().startswith("khet ") else name


def _district_sort_key(item: dict[str, Any]) -> str:
    return (_district_english_name(item) or str(item.get("name_th", ""))).casefold()


def select_booking_slot() -> BookingSlot:
    """Prompt until the user enters a valid booking date and start time."""
    while True:
        try:
            date_text = input("Booking date (YYYY-MM-DD, blank to cancel): ").strip()
            if not date_text:
                raise CancelSelectionError
            time_text = input(
                "Start time (HH:MM; blank = any start before 14:00): "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            raise CancelSelectionError from None
        try:
            return parse_booking_slot(date_text, time_text)
        except ValueError as exc:
            print(f"Invalid booking slot: {exc}")


def display_top(ranked: Sequence[RankedCleaner], limit: int = 3) -> None:
    """Print the top N cleaners to stdout."""
    if not ranked:
        print("\nNo excellent-rated cleaners with repeat data found in this area.")
        return
    print("\nTop cleaners by combined score (40% jobs / 60% repeat):")
    for entry in ranked[:limit]:
        r = entry.record
        repeat = r.repeat_booking_rate if r.repeat_booking_rate is not None else 0
        print(
            f"  #{entry.rank} {r.name} — {r.job_qty} jobs, "
            f"{repeat}% repeat, {r.rating:.1f}★ ({r.rating_qty} reviews), "
            f"available {r.available_start_time or 'time unknown'}"
        )


def write_html(
    ranked: Sequence[RankedCleaner],
    province_name: str,
    district_name: str,
    booking_slot: BookingSlot,
    path: str,
) -> None:
    """Write the ranked table to a standalone HTML file."""
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>BeNeat Cleaner Ranking</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; margin: 2rem auto; "
        "max-width: 1100px; padding: 0 1rem; color: #222; }",
        "    table { border-collapse: collapse; width: 100%; }",
        "    th, td { border: 1px solid #ddd; padding: .65rem; text-align: left; }",
        "    th { background: #f5f5f5; }",
        "    tbody tr:nth-child(even) { background: #fafafa; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>BeNeat Cleaner Ranking</h1>",
        "  <ul>",
        f"    <li>Province: {escape(province_name)}</li>",
        f"    <li>District: {escape(district_name)}</li>",
        f"    <li>Date: {booking_slot.date_text}</li>",
        f"    <li>Start time: {booking_slot.time_text}</li>",
        f"    <li>Duration: {booking_slot.duration_hours} hours</li>",
        f"    <li>Service: {escape(booking_slot.service)}</li>",
        f"    <li>Frequency: {escape(booking_slot.frequency)}</li>",
        "    <li>Excellent badge: required (is_excellent)</li>",
        "    <li>Repeat booking rate: required (&gt; 0)</li>",
        "    <li>Scoring: 0.4 x rank(jobs) + 0.6 x rank(repeat); "
        "tie-break by jobs</li>",
        "  </ul>",
        f"  <p>Total accepted cleaners: {len(ranked)}</p>",
        "  <table>",
        "    <thead><tr><th>Rank</th><th>Cleaner</th><th>Jobs</th>"
        "<th>Available start</th><th>Repeat %</th><th>Rating</th><th>Reviews</th>"
        "<th>Profile</th></tr></thead>",
        "    <tbody>",
    ]
    for entry in ranked:
        r = entry.record
        repeat = r.repeat_booking_rate if r.repeat_booking_rate is not None else 0
        name = escape(r.name)
        url = escape(r.profile_url, quote=True)
        lines.append(
            "      <tr>"
            f"<td>{entry.rank}</td><td>{name}</td><td>{r.job_qty}</td>"
            f"<td>{escape(r.available_start_time or 'Unknown')}</td>"
            f"<td>{repeat}</td><td>{r.rating:.1f}</td><td>{r.rating_qty}</td>"
            f'<td><a href="{url}" target="_blank" '
            'rel="noopener noreferrer">Open profile</a></td>'
            "</tr>"
        )
    lines.extend(["    </tbody>", "  </table>", "</body>", "</html>", ""])
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nResults written to {path}")
