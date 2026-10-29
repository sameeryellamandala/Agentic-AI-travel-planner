from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from schemas.travel import TravelRequest
from utils.budget import calculate_budget

REQUEST = {
    "source_city": "Bengaluru",
    "destination": "Goa",
    "start_date": "2026-10-31",
    "end_date": "2026-11-02",
    "budget": 30000,
    "passengers": 2,
}


def test_weather_local_timezone_and_invalid_date(monkeypatch):
    from services.weather_service import get_weather

    monkeypatch.setenv("OPENWEATHER_API_KEY", "test")
    timestamp = int(datetime(2026, 10, 10, 23, tzinfo=timezone.utc).timestamp())
    response = Mock(status_code=200)
    response.json.return_value = {
        "city": {"timezone": 19800},
        "list": [
            {"dt": timestamp, "main": {"temp": 28}, "weather": [{"main": "Clouds"}]}
        ],
    }
    monkeypatch.setattr(
        "services.weather_service.requests.get", Mock(return_value=response)
    )
    assert get_weather("Goa", "2026-10-11")["temperature"] == 28
    assert not get_weather("Goa", "2026-10-10")["success"]
    assert not get_weather("Goa", "invalid")["success"]
    assert get_weather("Goa", "2026-10-11")["rain_probability"] is None


def test_ignav_occupancy_currency_and_no_defaults(monkeypatch):
    import services.ignav_service as provider

    monkeypatch.setenv("IGNAV_API_KEY", "test")
    response = Mock(status_code=200)
    response.json.return_value = {
        "itineraries": [
            {
                "price": {"amount": 100, "currency": "USD", "status": "verified"},
                "outbound": {"segments": []},
            }
        ]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(provider.requests, "post", post)
    result = provider.search_flights("BLR", "GOI", "2026-10-10", adults=2)
    assert post.call_args.kwargs["json"]["adults"] == 2
    assert result["price"] == 100 and result["currency"] == "USD"
    assert result["duration_minutes"] is None and result["airline"] is None
    response.json.return_value["itineraries"][0]["price"]["status"] = "unverified"
    assert provider.search_flights("BLR", "GOI", "2026-10-10")["price"] is None


def test_budget_determinism_no_exchange_fallback():
    state = {
        "user_requirements": REQUEST,
        "transport_legs": [
            {
                "origin": "BLR",
                "destination": "GOI",
                "departure_date": "2026-10-10",
                "result": {"success": True, "price": 100, "currency": "USD"},
            }
        ],
        "stay_periods": [],
        "daily_plans": [],
    }
    assert calculate_budget(state) == calculate_budget(state)
    assert calculate_budget(state)["total"] == 0
    assert calculate_budget(state)["entries"][0]["provenance"] == "UNAVAILABLE"


def test_wikipedia_provider_no_prices(monkeypatch):
    from services import wikipedia_service as wiki

    monkeypatch.setattr(
        wiki,
        "destination_page",
        lambda _: {"title": "Goa", "links": [{"title": "Fort Aguada"}]},
    )
    monkeypatch.setattr(
        wiki,
        "_fetch_wikipedia_extracts",
        lambda _: {
            "fort aguada": {
                "title": "Fort Aguada",
                "extract": "Fort Aguada is a seventeenth-century fort in Goa.",
                "fullurl": "https://en.wikipedia.org/wiki/Fort_Aguada",
            }
        },
    )
    assert (
        wiki.search_wikipedia_places("Goa", limit=1)["places"][0]["estimated_cost"]
        is None
    )


def test_duckduckgo_distance_accepts_rail_rejects_road_and_other_routes(monkeypatch):
    import tools.estimators as estimators

    row = {
        "title": "Vijayawada to Visakhapatnam trains",
        "body": "Railway route distance: 350 km.",
        "href": "https://indiarailinfo.com/search/29/401",
    }
    search = Mock(return_value=[row])
    monkeypatch.setattr(estimators, "railway_search_results", search)
    monkeypatch.delenv("RAIL_DISTANCE_URL", raising=False)
    result = estimators.calculate_distance("Vijayawada", "Vizag")
    assert result["distance_km"] == 350 and result["source"] == row["href"]
    for changes in (
        {"body": "Road distance: 350 km."},
        {"title": "Delhi to Mumbai trains"},
        {"href": "https://example.com/unknown"},
        {"body": "Distance: 350 km. Distance: 900 km."},
    ):
        assert (
            estimators.distance_from_search_result(
                {**row, **changes}, "Vijayawada", "Vizag"
            )
            is None
        )


def test_train_requires_user_distance():
    from schemas.travel import TravelRequest

    with pytest.raises(ValueError, match="one-way"):
        TravelRequest(**{**REQUEST, "transport_mode": "Train"})
    assert (
        TravelRequest(
            **{**REQUEST, "transport_mode": "Train", "rail_distance_km": 600}
        ).rail_distance_km
        == 600
    )


def test_bus_is_not_a_supported_transport_mode():
    with pytest.raises(ValueError):
        TravelRequest.model_validate({**REQUEST, "transport_mode": "Bus"})


def test_four_train_fares_taxes_and_party_totals():
    from tools.estimators import estimate_train_fares

    result = estimate_train_fares(
        {"success": True, "distance_km": 600, "source_type": "USER_PROVIDED"},
        passengers=2,
    )
    fares = {f["class"]: f for f in result["fares"]}
    assert [fares[code]["base_fare"] for code in ("SL", "3A", "2A", "1A")] == [
        360,
        720,
        1080,
        1440,
    ]
    assert [fares[code]["tax"] for code in ("SL", "3A", "2A", "1A")] == [0, 36, 54, 72]
    assert result["price"] == 1512
    assert result["source_type"] == "CONFIGURED_ESTIMATE"
    assert all(f["total_fare"] > 0 for f in result["fares"])


def test_missing_distance_and_local_routes_no_fares(monkeypatch):
    import tools.estimators as estimators

    lookup = Mock(return_value=estimators.unavailable("Distance unavailable"))
    monkeypatch.setattr(estimators, "calculate_distance", lookup)
    assert not estimators.search_train_transport("Bangalore", "Goa")["success"]
    for route in [("Goa", "Baga Beach"), ("Goa", "Old Goa"), ("Airport", "Hotel")]:
        before = lookup.call_count
        result = estimators.search_train_transport(*route)
        assert not result["success"] and result["price"] is None and not result["fares"]
        assert lookup.call_count == before
