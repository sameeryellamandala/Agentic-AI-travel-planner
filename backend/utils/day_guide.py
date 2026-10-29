"""A usable, sourced guide when model wording or references cannot be verified."""

import math
import re
from schemas.research import ItineraryDraft


def source_excerpt(item):
    text = re.sub(r"\([^)]*\)", "", item.get("description", ""))
    text = " ".join(text.split())
    if not text:
        return f"{item['name']} is included in the destination research."
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return " ".join(sentences[:2])[:550]


def suggestion(item):
    text = (item["name"] + " " + item.get("description", "")[:350]).casefold()
    if "beach" in text:
        return "Take a relaxed walk along the shore and enjoy the coastal setting."
    if "fort" in text:
        return "Explore the fort and its surroundings, staying within areas open to visitors."
    if any(word in text for word in ("temple", "basilica", "church", "cathedral")):
        return "Look closely at the architecture and explore respectfully at your own pace."
    if "museum" in text:
        return "Browse the exhibits and spend time with the collections that interest you most."
    if any(word in text for word in ("sanctuary", "national park", "wildlife")):
        return "Make this a nature-focused stop and use designated visitor areas."
    if "falls" in text or "waterfall" in text:
        return (
            "Enjoy the waterfall and surrounding scenery from permitted visitor areas."
        )
    return "Explore the setting at your own pace and use the source link to learn its story."


def proximity(left, right):
    a, b = left.get("coordinates", []), right.get("coordinates", [])
    if not a or not b:
        return float("inf")
    lat1, lat2 = math.radians(a[0]["lat"]), math.radians(b[0]["lat"])
    dlat, dlon = lat2 - lat1, math.radians(b[0]["lon"] - a[0]["lon"])
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def source_guide(context, research):
    used, food_used, days = set(), set(), []
    for day in context["days"]:
        eligible = [
            (key, item)
            for key, item in research["candidates"].items()
            if item.get("location") == day["location"]
            and (
                item.get("day") == day["day"]
                or day["day"] in item.get("available_days", [])
            )
        ]
        places = [
            (key, item)
            for key, item in eligible
            if item["kind"] == "places"
            and (item.get("url") or item["name"]) not in used
        ]
        if places:
            anchor = places[0][1]
            places.sort(key=lambda pair: proximity(anchor, pair[1]))
        selected = places[:3]
        for _, item in selected:
            used.add(item.get("url") or item["name"])
        foods = [(key, item) for key, item in eligible if item["kind"] == "food"]
        foods.sort(
            key=lambda pair: (pair[1].get("url") or pair[1]["name"]) in food_used
        )
        chosen_food = foods[:2]
        for _, item in chosen_food:
            food_used.add(item.get("url") or item["name"])
        names = ", ".join(item["name"] for _, item in selected)
        dishes = ", ".join(item["name"] for _, item in chosen_food)
        days.append(
            {
                **day,
                "title": f"{selected[0][1]['name']} & local discoveries"
                if selected
                else f"Explore {day['location']}",
                "highlights": (f"Discover {names} at your own pace. " if names else "")
                + (
                    f"For a taste of the local cuisine, try {dishes}." if dishes else ""
                ),
                "visits": [
                    {
                        "candidate_id": key,
                        "why_visit": source_excerpt(item),
                        "what_to_do": suggestion(item),
                    }
                    for key, item in selected
                ],
                "food_experiences": [
                    {"candidate_id": key, "what_to_try": source_excerpt(item)}
                    for key, item in chosen_food
                ],
            }
        )
    return ItineraryDraft.model_validate({"days": days})


def valid_references(draft, context, research):
    if len(draft["days"]) != len(context["days"]):
        return False
    used = set()
    for actual, day in zip(context["days"], draft["days"]):
        if any(day.get(key) != actual[key] for key in ("day", "date", "location")):
            return False
        if not day.get("title", "").strip() or not day.get("highlights", "").strip():
            return False
        for field, kind in [("visits", "places"), ("food_experiences", "food")]:
            available = any(
                item.get("kind") == kind
                and item.get("location") == actual["location"]
                and (
                    item.get("day") == actual["day"]
                    or actual["day"] in item.get("available_days", [])
                )
                for item in research["candidates"].values()
            )
            if available and not day.get(field):
                return False
            for visit in day.get(field, []):
                item = research["candidates"].get(visit["candidate_id"])
                if (
                    not item
                    or item.get("location") != actual["location"]
                    or item.get("kind") != kind
                    or not (
                        item.get("day") == actual["day"]
                        or actual["day"] in item.get("available_days", [])
                    )
                ):
                    return False
                identity = item.get("url") or item["name"]
                if kind == "places" and identity in used:
                    return False
                if kind == "places":
                    used.add(identity)
    return True
