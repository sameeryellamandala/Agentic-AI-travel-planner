"""Destination-anchored Wikipedia evidence, not unchecked search snippets."""

import math
import os
import re
from functools import lru_cache
from urllib.parse import quote
import requests

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
PLACE = re.compile(
    r"\b(beach|fort|temple|church|basilica|cathedral|museum|palace|garden|park|sanctuary|waterfall|falls|lake|island|monastery|mosque|market|bridge|memorial|monument|castle|ruins|lighthouse|aquarium)\b",
    re.I,
)
FOOD = re.compile(
    r"\b(dish|curry|sausage|dessert|sweet|bread|stew|drink|beverage|spirit|confection|pickle|snack|cake|pudding|dumpling|noodle|pastry|soup|rice dish|seafood dish)\b",
    re.I,
)
NON_VISIT = re.compile(
    r"^(?:list of|tourism|history of|economy of|culture of|cuisine of)|\b(?:disambiguation)\b",
    re.I,
)
MEDIA_PERSON = re.compile(
    r"\b(?:film|musician|actor|actress|politician|album|television series|novel|singer|disc jockey)\b",
    re.I,
)


def _request(**params):
    response = requests.get(
        WIKIPEDIA_API_URL,
        params={"action": "query", "format": "json", "redirects": 1, **params},
        headers={
            "User-Agent": os.getenv("WIKIPEDIA_USER_AGENT", "VoyageTravelPlanner/3.0")
        },
        timeout=15,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise ValueError("Wikipedia request rejected")
    return body


def _pages(body):
    return [
        page
        for page in body.get("query", {}).get("pages", {}).values()
        if "missing" not in page
    ]


@lru_cache(maxsize=64)
def destination_page(location):
    pages = _pages(
        _request(
            titles=location,
            prop="extracts|info|coordinates|links|pageprops",
            inprop="url",
            exintro=1,
            explaintext=1,
            plnamespace=0,
            pllimit=500,
        )
    )
    if not pages or "disambiguation" in pages[0].get("pageprops", {}):
        raise ValueError(
            "Destination is unavailable or ambiguous; include a region/country"
        )
    return pages[0]


def _fetch_wikipedia_extracts(titles):
    if not titles:
        return {}
    pages = []
    for offset in range(0, min(len(titles), 100), 50):
        body = _request(
            titles="|".join(titles[offset : offset + 50]),
            prop="extracts|info|coordinates|pageprops",
            inprop="url",
            exintro=1,
            explaintext=1,
            exsentences=4,
        )
        for page in _pages(body):
            page["requested_titles"] = [page["title"]] + [
                row["from"]
                for row in body.get("query", {}).get("redirects", [])
                if row["to"] == page["title"]
            ]
            pages.append(page)
    return {page["title"].casefold(): page for page in pages}


def _nearby(page, destination):
    a, b = page.get("coordinates", []), destination.get("coordinates", [])
    if not a or not b:
        return False
    lat1, lat2 = math.radians(a[0]["lat"]), math.radians(b[0]["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(b[0]["lon"] - a[0]["lon"])
    hav = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1, math.sqrt(hav))) <= 120


def _mentions_destination(text, destination):
    name = destination["title"].split(",")[0].split("(")[0].strip()
    return bool(re.search(r"\b" + re.escape(name) + r"(?:n|an|ian)?\b", text, re.I))


def relevant_article(page, destination, category, cuisine_linked=False):
    title = page.get("title", "")
    extract = " ".join(page.get("extract", "").split())
    intro = extract[:450]
    if not extract or "disambiguation" in page.get("pageprops", {}):
        return False
    if NON_VISIT.search(title) or MEDIA_PERSON.search(intro[:220]):
        return False
    if category == "places":
        return bool(PLACE.search(title + " " + intro)) and (
            _mentions_destination(intro, destination) or _nearby(page, destination)
        )
    if "cuisine" in title.casefold():
        return False
    if title.casefold() in {
        "bread",
        "rice",
        "food",
        "meat",
        "fish",
        "seafood",
        "curry",
        "cake",
        "dessert",
        "soup",
        "drink",
        "vegetable",
        "spice",
        "pork",
        "beef",
    }:
        return False
    return bool(
        FOOD.search(
            title
            + " "
            + intro
            + " "
            + page.get("pageprops", {}).get("wikibase-shortdesc", "")
        )
    ) and (cuisine_linked or _mentions_destination(intro, destination))


def _search_titles(location, category):
    terms = (
        "(beach OR fort OR temple OR museum OR palace OR cathedral OR park OR waterfall)"
        if category == "places"
        else "(dish OR cuisine OR curry OR dessert OR drink)"
    )
    # The destination remains mandatory regardless of the agent's free-text query.
    body = _request(
        list="search", srsearch=f'"{location}" {terms}', srlimit=30, srnamespace=0
    )
    return [item["title"] for item in body.get("query", {}).get("search", [])]


def _collect(location, category, limit):
    field = "places" if category == "places" else "food_items"
    base = {"source": "Wikipedia", "location": location, field: []}
    try:
        root = destination_page(location.strip())
        links = [item["title"] for item in root.get("links", [])]
        cuisine_links = set()
        menu_names = []
        if category == "food":
            cuisines = [title for title in links if "cuisine" in title.casefold()]
            for title in cuisines[:1]:
                cuisine_pages = _pages(
                    _request(
                        titles=title,
                        prop="extracts|links",
                        explaintext=1,
                        plnamespace=0,
                        pllimit=500,
                    )
                )
                if not cuisine_pages:
                    continue
                cuisine = cuisine_pages[0]
                body = cuisine.get("extract", "").casefold()
                # Ignore navigation-template links to cuisines around the world.
                cuisine_links.update(
                    item["title"]
                    for item in cuisine.get("links", [])
                    if "cuisine" not in item["title"].casefold()
                    and item["title"].split(" (")[0].casefold() in body
                )
                for line in cuisine.get("extract", "").splitlines():
                    line = line.strip()
                    if not line or line.startswith("="):
                        continue
                    name = re.split(r"\s[–—]\s", line, maxsplit=1)[0]
                    name = re.sub(r"\([^)]*\)", "", name).strip()
                    if (
                        2 <= len(name) <= 65
                        and not any(char in name for char in ":;.")
                        and "cuisine" not in name.casefold()
                    ):
                        cuisine_links.add(name)
                        menu_names.append(name)
            candidates = menu_names + sorted(cuisine_links)
            # Search helps destinations whose primary article does not link a cuisine page.
            if not candidates:
                candidates = _search_titles(root["title"], category)
        else:
            candidates = [
                title
                for title in links
                if PLACE.search(title) and not NON_VISIT.search(title)
            ]
            if len(candidates) < limit:
                candidates += _search_titles(root["title"], category)
        candidates = list(dict.fromkeys(candidates))[
            : 100 if category == "food" else 50
        ]
        pages = _fetch_wikipedia_extracts(candidates)
        accepted = []
        for page in pages.values():
            linked = any(
                title in cuisine_links
                for title in page.get("requested_titles", [page["title"]])
            )
            if not relevant_article(page, root, category, linked):
                continue
            description = " ".join(page["extract"].split())
            accepted.append(
                {
                    "name": page["title"],
                    "description": description[:1000],
                    "url": page.get("fullurl")
                    or "https://en.wikipedia.org/wiki/"
                    + quote(page["title"].replace(" ", "_")),
                    "source": "Wikipedia",
                    "category": "Attraction" if category == "places" else "Local dish",
                    "estimated_cost": None,
                    "relevance_verified": True,
                    "destination": location,
                    "destination_source": root.get("fullurl")
                    or "https://en.wikipedia.org/wiki/" + quote(root["title"]),
                    "coordinates": page.get("coordinates", []),
                }
            )
        # Wikipedia returns pages by page ID; use a stable order for repeatable selection.
        accepted.sort(
            key=lambda item: (
                not _mentions_destination(item["description"], root),
                item["name"].casefold(),
            )
        )
        accepted = accepted[:limit]
        return {
            **base,
            field: accepted,
            "success": bool(accepted),
            "status": "SUCCESS" if accepted else "UNAVAILABLE",
            "source_type": "LIVE_PROVIDER" if accepted else "UNAVAILABLE",
            **(
                {}
                if accepted
                else {
                    "reason": "No destination-relevant attractions or dishes could be verified"
                }
            ),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {
            **base,
            "success": False,
            "status": "UNAVAILABLE",
            "source_type": "UNAVAILABLE",
            "reason": "Wikipedia research unavailable; no unverified search results were substituted",
        }


def search_wikipedia_places(location, query=None, interests=None, limit=16):
    return _collect(location, "places", limit)


def search_wikipedia_food(location, query=None, preferences=None, limit=12):
    return _collect(location, "food", limit)
