"""Request-scoped MCP server. Tool arguments cannot change the approved route."""

import json
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from services.weather_service import get_live_weather
from services.flight_service import search_ignav_flights
from services.hotel_service import search_stay_hotels
from services.wikipedia_service import search_wikipedia_places, search_wikipedia_food
from tools.estimators import search_train_transport
from utils.trip import prepare_context

load_dotenv()
mcp = FastMCP("Voyage travel research")


class ResearchTools:
    def __init__(self, requirements):
        self.context = prepare_context(requirements)
        self.cache = {}
        self.knowledge_cache = {}

    def call(self, name, args):
        key = json.dumps([name, args], sort_keys=True)
        if key in self.cache:
            return {**self.cache[key], "cached": True}
        req = self.context["user_requirements"]
        try:
            if name in ("get_weather", "search_places", "search_food"):
                if type(args.get("day")) is not int or not 1 <= args["day"] <= len(
                    self.context["days"]
                ):
                    raise ValueError("Unknown trip day")
                day = self.context["days"][args["day"] - 1]
                if name == "get_weather":
                    result = get_live_weather(day["location"], day["date"])
                else:
                    fn = (
                        search_wikipedia_places
                        if name == "search_places"
                        else search_wikipedia_food
                    )
                    query = str(args.get("query", "")).strip()[:200]
                    knowledge_key = (name, day["location"])
                    knowledge_reused = knowledge_key in self.knowledge_cache
                    if knowledge_key not in self.knowledge_cache:
                        self.knowledge_cache[knowledge_key] = fn(
                            day["location"], query or None
                        )
                    result = dict(self.knowledge_cache[knowledge_key])
                    result["knowledge_reused"] = knowledge_reused
                    field = "places" if name == "search_places" else "food_items"
                    kind = "places" if field == "places" else "food"
                    result[field] = [
                        {
                            **item,
                            "candidate_id": f"L{list(dict.fromkeys(entry['location'] for entry in self.context['days'])).index(day['location']) + 1}-{kind[0].upper()}{i}",
                            "day": day["day"],
                            "available_days": [
                                entry["day"]
                                for entry in self.context["days"]
                                if entry["location"] == day["location"]
                            ],
                            "location": day["location"],
                            "kind": kind,
                        }
                        for i, item in enumerate(result.get(field, []), 1)
                    ]
                result = {
                    **result,
                    "day": day["day"],
                    "date": day["date"],
                    "location": day["location"],
                }
            elif name == "search_transport":
                leg = next(
                    x
                    for x in self.context["transport_legs"]
                    if x["id"] == args["leg_id"]
                )
                result = (
                    search_ignav_flights(
                        leg["origin"],
                        leg["destination"],
                        departure_date=leg["departure_date"],
                        passengers=req["passengers"],
                    )
                    if leg["mode"] == "Flight"
                    else search_train_transport(
                        leg["origin"],
                        leg["destination"],
                        passengers=req["passengers"],
                        selected_class=req["train_class"],
                        supplied_distance=req["rail_distance_km"],
                    )
                )
            elif name == "search_stay":
                stay = next(
                    x
                    for x in self.context["stay_periods"]
                    if x["id"] == args["stay_id"]
                )
                result = search_stay_hotels(
                    stay["location"],
                    stay["check_in"],
                    stay["check_out"],
                    req["passengers"],
                    req["hotel_type"],
                    rooms=req["rooms"],
                )
            else:
                raise ValueError("Unknown tool")
            result = {
                **result,
                "success": result.get("success", result.get("status") == "SUCCESS"),
            }
        except Exception:
            result = {
                "success": False,
                "status": "UNAVAILABLE",
                "reason": f"{name} failed or received invalid arguments",
            }
        self.cache[key] = result
        return {**result, "cached": False}


_tools = None


def execute(name, args):
    global _tools
    if _tools is None:
        _tools = ResearchTools(json.loads(os.environ["TRAVEL_REQUIREMENTS"]))
    return _tools.call(name, args)


@mcp.tool()
def get_weather(day: int) -> dict:
    """Get weather for an exact trip day; date and location come from the request."""
    return execute("get_weather", {"day": day})


@mcp.tool()
def search_places(day: int, query: str = "") -> dict:
    """Find sourced destination attractions for this trip day. Returns candidate IDs."""
    return execute("search_places", {"day": day, "query": query})


@mcp.tool()
def search_food(day: int, query: str = "") -> dict:
    """Find sourced local dishes for this trip day; does not return meal prices."""
    return execute("search_food", {"day": day, "query": query})


@mcp.tool()
def search_transport(leg_id: str) -> dict:
    """Search an approved outward or return journey by leg ID, not local mobility."""
    return execute("search_transport", {"leg_id": leg_id})


@mcp.tool()
def search_stay(stay_id: str) -> dict:
    """Search accommodation once per approved stay period using its ID."""
    return execute("search_stay", {"stay_id": stay_id})


if __name__ == "__main__":
    mcp.run(transport="stdio")
