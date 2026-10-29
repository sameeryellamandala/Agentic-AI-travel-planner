from unittest.mock import Mock
import pytest
from services.hotel_service import search_stay_hotels, resolve_city, parse_inr


def response(data, status=200):
    return Mock(status_code=status, json=Mock(return_value=data))


def test_makcorps_mapping_dates_and_price_basis(monkeypatch):
    resolve_city.cache_clear()
    monkeypatch.setenv("MAKCORPS_API_KEY", "fixture-key")
    get = Mock(
        side_effect=[
            response(
                [{"type": "GEO", "document_id": "123", "details": {"name": "Goa"}}]
            ),
            response(
                [
                    {
                        "hotelId": 44,
                        "name": "Sourced hotel",
                        "reviews": {"rating": 4.5},
                        "vendor1": "Vendor",
                        "price1": "₹3,200",
                    },
                    [{"totalHotelCount": 1}],
                ]
            ),
        ]
    )
    monkeypatch.setattr("services.hotel_service.requests.get", get)
    result = search_stay_hotels("Goa", "2026-10-31", "2026-11-02", 2)
    assert result["success"] and result["provider_quote"] == 3200
    assert result["total_price"] is None and result["price_per_night"] is None
    assert result["warnings"]
    params = get.call_args.kwargs["params"]
    assert (
        params["cityid"] == "123" and params["cur"] == "INR" and params["adults"] == 2
    )
    assert params["checkin"] == "2026-10-31" and params["checkout"] == "2026-11-02"


def test_missing_key_and_ambiguous_city(monkeypatch):
    monkeypatch.delenv("MAKCORPS_API_KEY", raising=False)
    assert not search_stay_hotels("Goa")["success"]
    monkeypatch.setenv("MAKCORPS_API_KEY", "ambiguous-fixture")
    monkeypatch.setattr(
        "services.hotel_service.requests.get",
        Mock(
            return_value=response(
                [
                    {"type": "GEO", "document_id": "1"},
                    {"type": "GEO", "document_id": "2"},
                ]
            )
        ),
    )
    assert not search_stay_hotels("Springfield", "2026-10-31", "2026-11-02")["success"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("₹1,234.50", 1234.5),
        ("INR 999", 999),
        ("$25", None),
        ("free", None),
        (None, None),
        ("0", None),
    ],
)
def test_price_parser(value, expected):
    assert parse_inr(value) == expected
