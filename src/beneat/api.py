"""Client for the BeNeat public API (https://lumen.beneat.co).

Endpoints used:
  GET /address-provinces          -> provinces BeNeat serves
  GET /districts?province_id=N    -> districts for a province
  GET /professionals              -> paginated cleaner listings
  GET /professionals/{id}         -> detail incl. repeat_booking_rate
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import requests

from beneat.config import settings

TIMEOUT_SECONDS = 30
_USER_AGENT = "beneat-finder/0.1.0"


class BeNeatAPIError(RuntimeError):
    """Raised when the BeNeat API returns a non-OK response."""


def _get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    allow_error: bool = False,
) -> dict[str, Any]:
    """Perform a GET against the BeNeat API with a single retry on failure."""
    url = f"{settings.beneat_api_base}{path}"
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError("Unexpected non-object JSON response")
            if data.get("error") and not allow_error:
                raise BeNeatAPIError(
                    str(data.get("message", "API returned error"))
                )
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == 0:
                continue
    raise BeNeatAPIError(f"Failed to fetch {url}: {last_error}") from last_error


def fetch_provinces() -> list[dict[str, Any]]:
    """Return the list of provinces served by BeNeat."""
    data = _get("/address-provinces")
    return list(data.get("address_provinces", []))


def fetch_districts(province_id: int) -> list[dict[str, Any]]:
    """Return districts belonging to a province."""
    data = _get("/districts", {"province_id": province_id})
    return list(data.get("districts", []))


def fetch_services() -> list[dict[str, Any]]:
    """Return the top-level service categories (parent_id=0)."""
    data = _get("/services", {"parent_id": 0})
    return list(data.get("services", []))


def fetch_professionals(
    district_id: int,
    service_id: int,
    limit: int,
    page: int,
) -> list[dict[str, Any]]:
    """Return one page of cleaner listings for a district."""
    data = _get(
        "/professionals",
        {
            "district_id": district_id,
            "service_id": service_id,
            "limit": limit,
            "page": page,
        },
    )
    return list(data.get("professionals", []))


def iter_professionals(
    district_id: int,
    service_id: int,
    limit: int = 200,
    max_pages: int = 100,
) -> Iterable[dict[str, Any]]:
    """Yield every professional listing for a district across all pages."""
    for page in range(1, max_pages + 1):
        items = fetch_professionals(district_id, service_id, limit, page)
        if not items:
            return
        yield from items


def fetch_professional_detail(professional_id: int) -> dict[str, Any]:
    """Return the full profile of a single professional."""
    data = _get(f"/professionals/{professional_id}")
    professional = data.get("professional")
    if not isinstance(professional, dict):
        raise BeNeatAPIError(
            f"Malformed detail response for professional {professional_id}"
        )
    return professional


def fetch_professional_calendar(
    professional_id: int, booking_date: str
) -> dict[str, Any]:
    """Return provider-level calendar data for a booking date."""
    return _get(
        "/professional/calendars",
        {
            "professional_id": professional_id,
            "start_date": booking_date,
            "end_date": booking_date,
        },
    )


def fetch_professional_calendar_jobs(
    professional_id: int, booking_date: str
) -> list[dict[str, Any]]:
    """Return a provider's existing jobs; BeNeat reports no jobs as an error."""
    data = _get(
        "/professional/calendars/jobs",
        {"professional_id": professional_id, "cleaning_date": booking_date},
        allow_error=True,
    )
    if data.get("error") and data.get("message") == "No data":
        return []
    if data.get("error"):
        raise BeNeatAPIError(str(data.get("message", "Calendar API returned error")))
    return list(data.get("calendar_jobs", []))
