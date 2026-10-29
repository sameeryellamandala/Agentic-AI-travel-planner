"""Prepare trip dates and approved provider requests without an LLM."""

from datetime import date, timedelta
from schemas.travel import TravelRequest
from tools.estimators import is_local_mobility


def prepare_context(requirements):
    req = TravelRequest.model_validate(requirements).model_dump(mode="json")
    count = (
        date.fromisoformat(req["end_date"]) - date.fromisoformat(req["start_date"])
    ).days + 1
    locations = req.get("day_locations") or [req["destination"]] * count
    days = [
        {
            "day": i + 1,
            "date": (
                date.fromisoformat(req["start_date"]) + timedelta(days=i)
            ).isoformat(),
            "location": location,
        }
        for i, location in enumerate(locations)
    ]
    legs = []
    for origin, destination, departure in [
        (req["source_city"], req["destination"], req["start_date"]),
        (req["destination"], req["source_city"], req["end_date"]),
    ]:
        if not is_local_mobility(origin, destination):
            legs.append(
                {
                    "id": f"leg-{len(legs) + 1}",
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure,
                    "mode": req["transport_mode"],
                }
            )
    stays = []
    for day in days[:-1]:
        checkout = (date.fromisoformat(day["date"]) + timedelta(days=1)).isoformat()
        if stays and stays[-1]["location"] == day["location"]:
            stays[-1]["check_out"] = checkout
            stays[-1]["nights"] += 1
        else:
            stays.append(
                {
                    "id": f"stay-{len(stays) + 1}",
                    "location": day["location"],
                    "check_in": day["date"],
                    "check_out": checkout,
                    "nights": 1,
                }
            )
    return {
        "user_requirements": req,
        "days": days,
        "transport_legs": legs,
        "stay_periods": stays,
    }
