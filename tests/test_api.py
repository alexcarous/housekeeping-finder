import pytest
import requests
import requests_mock

from beneat import api


def test_fetch_provinces(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/address-provinces",
        json={"address_provinces": [{"id": 1, "name": "Bangkok"}]},
    )
    assert api.fetch_provinces() == [{"id": 1, "name": "Bangkok"}]


def test_fetch_districts(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/districts",
        json={"districts": [{"id": 9, "name_th": "เขตพระโขนง"}]},
    )
    assert api.fetch_districts(1) == [{"id": 9, "name_th": "เขตพระโขนง"}]
    assert requests_mock.last_request.qs["province_id"] == ["1"]


def test_fetch_services(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/services",
        json={"services": [{"id": 1, "name": "Cleaning"}]},
    )
    assert api.fetch_services() == [{"id": 1, "name": "Cleaning"}]
    assert requests_mock.last_request.qs["parent_id"] == ["0"]


def test_fetch_professionals_passes_query_params(
    requests_mock: requests_mock.Mocker,
) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professionals",
        json={"professionals": [{"id": 5}]},
    )
    assert api.fetch_professionals(9, 1, 200, 3) == [{"id": 5}]
    qs = requests_mock.last_request.qs
    assert qs["district_id"] == ["9"]
    assert qs["service_id"] == ["1"]
    assert qs["limit"] == ["200"]
    assert qs["page"] == ["3"]


def test_iter_professionals_stops_on_empty_page(
    requests_mock: requests_mock.Mocker,
) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professionals",
        response_list=[
            {"json": {"professionals": [{"id": 1}, {"id": 2}]}},
            {"json": {"professionals": []}},
        ],
    )
    result = list(api.iter_professionals(9, 1))
    assert [p["id"] for p in result] == [1, 2]


def test_fetch_professional_detail(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professionals/42",
        json={"professional": {"id": 42, "repeat_booking_rate": 80}},
    )
    assert api.fetch_professional_detail(42)["repeat_booking_rate"] == 80


def test_malformed_detail_raises(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professionals/42",
        json={"professional": None},
    )
    with pytest.raises(api.BeNeatAPIError):
        api.fetch_professional_detail(42)


def test_fetch_professional_calendar(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professional/calendars",
        json={"blocked_dates": [{"date": "2099-06-10", "blocked_type": "full"}]},
    )

    result = api.fetch_professional_calendar(42, "2099-06-10")

    assert result["blocked_dates"][0]["blocked_type"] == "full"
    assert requests_mock.last_request.qs == {
        "professional_id": ["42"],
        "start_date": ["2099-06-10"],
        "end_date": ["2099-06-10"],
    }


def test_fetch_calendar_jobs_treats_no_data_as_empty(
    requests_mock: requests_mock.Mocker,
) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professional/calendars/jobs",
        json={"error": True, "message": "No data"},
    )

    assert api.fetch_professional_calendar_jobs(42, "2099-06-10") == []


def test_fetch_calendar_jobs_returns_jobs(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/professional/calendars/jobs",
        json={"error": False, "calendar_jobs": [{"start_time": "10:00"}]},
    )

    jobs = api.fetch_professional_calendar_jobs(42, "2099-06-10")
    assert jobs == [{"start_time": "10:00"}]


def test_api_error_field_raises(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/address-provinces",
        json={"error": True, "message": "Something went wrong"},
    )
    with pytest.raises(api.BeNeatAPIError, match="Something went wrong"):
        api.fetch_provinces()


def test_http_error_raises(requests_mock: requests_mock.Mocker) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/address-provinces",
        status_code=500,
    )
    with pytest.raises(api.BeNeatAPIError):
        api.fetch_provinces()


def test_network_error_retries_then_raises(
    requests_mock: requests_mock.Mocker,
) -> None:
    requests_mock.get(
        f"{api.settings.beneat_api_base}/address-provinces",
        exc=requests.ConnectionError,
    )
    with pytest.raises(api.BeNeatAPIError):
        api.fetch_provinces()
    assert requests_mock.call_count == 2
