"""Interactive CLI prompts, progress display, and markdown output."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    """Prompt the user to pick a district, returning its record."""
    print("Select a district:")
    _print_menu(districts)
    choice = _read_choice(len(districts), "District number (or blank to cancel): ")
    return districts[choice - 1]


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
            f"{repeat}% repeat, {r.rating:.1f}★ ({r.rating_qty} reviews)"
        )


def write_markdown(
    ranked: Sequence[RankedCleaner],
    province_name: str,
    district_name: str,
    path: str,
) -> None:
    """Write the ranked table to a markdown file."""
    lines = [
        "# BeNeat Cleaner Ranking",
        "",
        f"- Province: {province_name}",
        f"- District: {district_name}",
        "- Excellent badge: required (is_excellent)",
        "- Repeat booking rate: required (> 0)",
        "- Service: general cleaning (service_id=1)",
        "- Scoring: 0.4 x rank(jobs) + 0.6 x rank(repeat); tie-break by jobs",
        "",
        f"Total accepted cleaners: {len(ranked)}",
        "",
        "| Rank | Cleaner | Jobs | Repeat % | Rating | Reviews | URL |",
        "|------|---------|------|----------|--------|---------|-----|",
    ]
    for entry in ranked[:20]:
        r = entry.record
        repeat = r.repeat_booking_rate if r.repeat_booking_rate is not None else 0
        lines.append(
            f"| {entry.rank} | {r.name} | {r.job_qty} | {repeat} | "
            f"{r.rating:.1f} | {r.rating_qty} | {r.profile_url} |"
        )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nResults written to {path}")
