"""Entrypoint: find the best-rated BeNeat cleaner for a selected district.

Flow:
  1. Load province/district reference data (cached, 30-day TTL).
  2. User selects a province, then a district.
  3. User enters a date and time for a two-hour, one-time cleaning.
  4. Paginate the professionals listing for that district (general cleaning).
  5. Keep only excellent cleaners with repeat data who are available then.
  6. Rank by weighted jobs/repeat score and write output/RESULTS.html.
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from beneat.api import (
    BeNeatAPIError,
    fetch_districts,
    fetch_professional_calendar,
    fetch_professional_calendar_jobs,
    fetch_professional_detail,
    fetch_provinces,
    fetch_services,
    iter_professionals,
)
from beneat.availability import (
    BookingSlot,
    booking_now,
    booking_today,
    find_available_start,
)
from beneat.cache import CacheData, cache_path, is_fresh, load, save
from beneat.cli import (
    CancelSelectionError,
    display_top,
    select_booking_slot,
    select_district,
    select_province,
    write_html,
)
from beneat.config import settings
from beneat.ranking import (
    CleanerRecord,
    enrich,
    from_listing,
    is_acceptable,
    rank_cleaners,
)

OUTPUT_FILE = "output/RESULTS.html"
PROFILE_BASE = "https://beneat.co"
CLEANING_SERVICE_ID = 1


def _serves_district(detail: dict[str, Any], district_id: int) -> bool:
    """Return whether a profile explicitly lists the selected service district."""
    districts = detail.get("professional_districts")
    if not isinstance(districts, list):
        return False
    return any(
        isinstance(entry, dict)
        and str(entry.get("district_id", "")) == str(district_id)
        for entry in districts
    )


def _load_reference_data(refresh: bool) -> CacheData:
    """Load reference data from cache or the live API."""
    if not refresh and is_fresh(cache_path()):
        cached = load()
        if cached is not None:
            print("Using cached province/district data.")
            return cached

    print("Fetching reference data from BeNeat API...")
    provinces = fetch_provinces()
    districts: dict[int, list[dict[str, Any]]] = {}
    for province in provinces:
        province_id = int(province["id"])
        districts[province_id] = fetch_districts(province_id)
    services = fetch_services()
    data = CacheData(
        provinces=provinces,
        districts=districts,
        services=services,
        cached_at=time.time(),
    )
    save(data)
    print("Reference data cached.")
    return data


def _fetch_and_gate_cleaners(
    district_id: int,
) -> list[CleanerRecord]:
    """Paginate the listing and build acceptable (excellent) records."""
    print("Scanning cleaner listings...", flush=True)
    accepted: list[CleanerRecord] = []
    for scanned, item in enumerate(
        iter_professionals(
            district_id, CLEANING_SERVICE_ID, limit=settings.listing_limit
        ),
        start=1,
    ):
        professional_id = int(item.get("id", 0))
        if item.get("is_excellent"):
            record = from_listing(item, f"{PROFILE_BASE}/cleaner/{professional_id}")
            if record.job_qty > 0:
                accepted.append(record)
        print(
            f"\r  Scanned: {scanned} | excellent candidates: {len(accepted)}  ",
            end="",
            flush=True,
        )
    print()
    return accepted


def _enrich_repeat_rates(
    records: list[CleanerRecord], workers: int, district_id: int
) -> list[CleanerRecord]:
    """Fetch each cleaner's detail to obtain the repeat booking rate.

    Uses a thread pool since the detail calls are I/O-bound and there can
    be hundreds of excellent cleaners in a single district.
    """

    def fetch(record: CleanerRecord) -> CleanerRecord | None:
        detail = fetch_professional_detail(record.professional_id)
        # The listing endpoint can return professionals outside the selected
        # district.  The profile's explicit service-area list is authoritative.
        if not _serves_district(detail, district_id):
            return None
        return enrich(record, detail, PROFILE_BASE)

    enriched: list[CleanerRecord] = []
    total = len(records)
    print(f"Fetching repeat rates for {total} cleaners...", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, r) for r in records]
        for _future in as_completed(futures):
            completed += 1
            print(
                "\r  " + f"Fetching repeat rates: {completed}/{total}" + "  ",
                end="",
                flush=True,
            )
            result = _future.result()
            if result is not None:
                enriched.append(result)
    print()
    return enriched


def _filter_available(
    records: list[CleanerRecord], slot: BookingSlot, workers: int
) -> list[CleanerRecord]:
    """Keep only cleaners whose BeNeat calendars accept the requested slot."""
    not_before = booking_now().time() if slot.booking_date == booking_today() else None

    def check(record: CleanerRecord) -> tuple[CleanerRecord, str | None]:
        calendar = fetch_professional_calendar(record.professional_id, slot.date_text)
        if (
            slot.booking_date == booking_today()
            and calendar.get("is_available_today") is False
        ):
            return record, None
        blocks = list(calendar.get("blocked_dates", []))
        jobs = fetch_professional_calendar_jobs(record.professional_id, slot.date_text)
        matched = find_available_start(slot, blocks, jobs, not_before=not_before)
        return record, matched.strftime("%H:%M") if matched else None

    available: list[CleanerRecord] = []
    total = len(records)
    print(f"Checking availability for {total} cleaners...", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(check, record) for record in records]
        for future in as_completed(futures):
            completed += 1
            print(
                "\r  " + f"Checking availability: {completed}/{total}" + "  ",
                end="",
                flush=True,
            )
            record, matched_time = future.result()
            if matched_time is not None:
                record.available_start_time = matched_time
                available.append(record)
    print()
    return available


def _province_name(province: dict[str, Any]) -> str:
    name = province.get("name")
    if isinstance(name, dict):
        return str(name.get("th", ""))
    return str(name or "")


def _district_name(district: dict[str, Any]) -> str:
    return str(district.get("name_th") or district.get("name_en") or "")


def _positive_worker_count(value: str) -> int:
    """Parse a strictly positive worker count for argparse."""
    try:
        workers = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("workers must be an integer") from exc
    if workers < 1:
        raise argparse.ArgumentTypeError("workers must be at least 1")
    return workers


def main() -> None:
    """Run the interactive cleaner-finder flow."""
    parser = argparse.ArgumentParser(
        description="Find the best-rated BeNeat cleaner for a district."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the cache and re-fetch province/district data.",
    )
    parser.add_argument(
        "--workers",
        type=_positive_worker_count,
        default=8,
        help="Concurrency for detail and availability requests (default: 8).",
    )
    args = parser.parse_args()
    try:
        data = _load_reference_data(args.refresh)
        province = select_province(data.provinces)
        province_id = int(province["id"])
        districts = data.districts.get(province_id, [])
        if not districts:
            districts = fetch_districts(province_id)
        district = select_district(districts)
        district_id = int(district["id"])
        booking_slot = select_booking_slot()
    except CancelSelectionError:
        print("\nCancelled.")
        return
    except BeNeatAPIError as exc:
        print(f"\nAPI error: {exc}")
        raise SystemExit(1) from exc

    print(
        f"\nSearching {_province_name(province)} / {_district_name(district)} "
        f"for excellent cleaners on {booking_slot.date_text} at "
        f"{booking_slot.time_text} (service_id={CLEANING_SERVICE_ID})..."
    )

    try:
        excellent = _fetch_and_gate_cleaners(district_id)
        if not excellent:
            print("No excellent-rated cleaners found in this district.")
            write_html(
                [],
                _province_name(province),
                _district_name(district),
                booking_slot,
                OUTPUT_FILE,
            )
            return

        enriched = _enrich_repeat_rates(excellent, args.workers, district_id)
        qualified = [record for record in enriched if is_acceptable(record)]
        if not qualified:
            print("No excellent-rated cleaners with repeat data found in this area.")
            write_html(
                [],
                _province_name(province),
                _district_name(district),
                booking_slot,
                OUTPUT_FILE,
            )
            return

        available = _filter_available(qualified, booking_slot, args.workers)
        if not available:
            print(
                "No qualifying cleaners are available for the requested "
                f"date/time ({booking_slot.date_text}, {booking_slot.time_text})."
            )
        ranked = rank_cleaners(available)
        if ranked:
            display_top(ranked)
        write_html(
            ranked,
            _province_name(province),
            _district_name(district),
            booking_slot,
            OUTPUT_FILE,
        )
    except BeNeatAPIError as exc:
        print(f"\nAPI error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
