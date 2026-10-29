"""
Real Flight Service Integration using Ignav.
Re-exports and wraps services.ignav_service for full backward compatibility.
"""
from typing import Dict, Any, Optional
from services.ignav_service import (
    search_flights as search_ignav_api_flights,
    search_round_trip_flights as search_ignav_round_trip_flights,
    resolve_airport_code,
    test_ignav_connection
)

def search_ignav_flights(
    origin: str,
    destination: str,
    departure_date: str = "",
    return_date: str = "",
    passengers: int = 1,
    max_price: Optional[float] = None,
    max_stops: Optional[int] = None
) -> Dict[str, Any]:
    """
    Real Ignav Flight Search Integration.
    If return_date is provided, makes real round-trip request.
    Otherwise makes live one-way HTTP request (POST https://ignav.com/api/fares/one-way).
    """
    if return_date and return_date.strip():
        return search_ignav_round_trip_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            max_price=max_price,
            max_stops=max_stops
        )

    return search_ignav_api_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        adults=passengers,
        max_price=max_price,
        max_stops=max_stops
    )

search_flights = search_ignav_flights
search_round_trip_flights = search_ignav_round_trip_flights

