"""Entrypoint: find the best-rated BeNeat cleaner for a selected district.

Flow:
  1. Load province/district reference data (cached, 30-day TTL).
  2. User selects a province, then a district.
  3. Paginate the professionals listing for that district (general cleaning).
  4. Keep only cleaners with the excellent badge and a repeat booking rate.
  5. Rank by weighted jobs/repeat score and write results to RESULTS.md.
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from beneat.api import (
    BeNeatAPIError,
    fetch_districts,
    fetch_professional_detail,
    fetch_provinces,
    fetch_services,
    iter_professionals,
)
from beneat.cache import CacheData, cache_path, is_fresh, load, save
from beneat.cli import (
    CancelSelectionError,
    display_top,
    select_district,
    select_province,
    write_markdown,
)
from beneat.config import settings
from beneat.ranking import CleanerRecord, enrich, from_listing, rank_cleaners

OUTPUT_FILE = "RESULTS.md"
PROFILE_BASE = "https://beneat.co"


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
    accepted: list[CleanerRecord] = []
    for item in iter_professionals(
        district_id, settings.service_id, limit=settings.listing_limit
    ):
        professional_id = int(item.get("id", 0))
        if not item.get("is_excellent"):
            continue
        record = from_listing(item, f"{PROFILE_BASE}/cleaner/{professional_id}")
        if record.job_qty > 0:
            accepted.append(record)
    return accepted


def _enrich_repeat_rates(
    records: list[CleanerRecord], workers: int
) -> list[CleanerRecord]:
    """Fetch each cleaner's detail to obtain the repeat booking rate.

    Uses a thread pool since the detail calls are I/O-bound and there can
    be hundreds of excellent cleaners in a single district.
    """

    def fetch(record: CleanerRecord) -> CleanerRecord:
        detail = fetch_professional_detail(record.professional_id)
        return enrich(record, detail, PROFILE_BASE)

    enriched: list[CleanerRecord] = []
    total = len(records)
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
            enriched.append(_future.result())
    print()
    return enriched


def _province_name(province: dict[str, Any]) -> str:
    name = province.get("name")
    if isinstance(name, dict):
        return str(name.get("th", ""))
    return str(name or "")


def _district_name(district: dict[str, Any]) -> str:
    return str(district.get("name_th") or district.get("name_en") or "")


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
        "--service",
        type=int,
        default=settings.service_id,
        help=f"Service ID filter (default: {settings.service_id}, general cleaning).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Concurrency for fetching repeat rates (default: 8).",
    )
    args = parser.parse_args()
    settings.service_id = args.service

    try:
        data = _load_reference_data(args.refresh)
        province = select_province(data.provinces)
        province_id = int(province["id"])
        districts = data.districts.get(province_id, [])
        if not districts:
            districts = fetch_districts(province_id)
        district = select_district(districts)
        district_id = int(district["id"])
    except CancelSelectionError:
        print("\nCancelled.")
        return
    except BeNeatAPIError as exc:
        print(f"\nAPI error: {exc}")
        raise SystemExit(1) from exc

    print(
        f"\nSearching {_province_name(province)} / {_district_name(district)} "
        f"for excellent cleaners (service_id={settings.service_id})..."
    )

    try:
        excellent = _fetch_and_gate_cleaners(district_id)
        if not excellent:
            print("No excellent-rated cleaners found in this district.")
            return

        enriched = _enrich_repeat_rates(excellent, args.workers)
        ranked = rank_cleaners(enriched)
        display_top(ranked)
        write_markdown(
            ranked,
            _province_name(province),
            _district_name(district),
            OUTPUT_FILE,
        )
    except BeNeatAPIError as exc:
        print(f"\nAPI error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
