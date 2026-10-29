"""Makcorps city mapping and dated hotel quotes; never assume a quote's basis."""

import os
import re
from datetime import date
from functools import lru_cache
import requests
from utils.budget import valid_amount

BASE_URL = "https://api.makcorps.com"


@lru_cache(maxsize=128)
def resolve_city(location, api_key):
    response = requests.get(
        BASE_URL + "/mapping", params={"api_key": api_key, "name": location}, timeout=20
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected city mapping response")
    matches = [
        row for row in rows if row.get("type") == "GEO" and row.get("document_id")
    ]
    exact = [
        row
        for row in matches
        if row.get("details", {}).get("name", "").casefold() == location.casefold()
    ]
    if len(exact) == 1:
        return exact[0]["document_id"]
    if len(matches) == 1:
        return matches[0]["document_id"]
    raise ValueError("City is ambiguous or unavailable; include country or region")


def parse_inr(value):
    if isinstance(value, str):
        value = (
            re.sub(r"^(?:INR\s*|₹\s*|Rs\.?\s*)", "", value.strip(), flags=re.I)
            .replace(",", "")
            .strip()
        )
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
            return None
    amount = valid_amount(value)
    return float(amount) if amount is not None and amount > 0 else None


def search_stay_hotels(
    location,
    check_in="",
    check_out="",
    guests=1,
    hotel_type="Budget",
    max_price=None,
    rooms=1,
):
    base = {
        "source": "Makcorps",
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
    }

    def unavailable(reason):
        return {
            **base,
            "success": False,
            "status": "UNAVAILABLE",
            "source_type": "UNAVAILABLE",
            "hotels": [],
            "reason": reason,
        }

    key = os.getenv("MAKCORPS_API_KEY")
    if not key:
        return unavailable("MAKCORPS_API_KEY is not configured")
    try:
        nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
        if nights < 1 or type(guests) is not int or guests < 1:
            return unavailable("Invalid stay dates or guest count")
        cityid = resolve_city(location.strip(), key)
        response = requests.get(
            BASE_URL + "/city",
            params={
                "api_key": key,
                "cityid": cityid,
                "pagination": 0,
                "cur": "INR",
                "rooms": rooms,
                "adults": guests,
                "checkin": check_in,
                "checkout": check_out,
                "tax": "true",
            },
            timeout=45,
        )
        if response.status_code != 200:
            return unavailable(
                f"Makcorps hotel search returned HTTP {response.status_code}"
            )
        rows = response.json()
        if not isinstance(rows, list):
            return unavailable("Makcorps returned an unexpected hotel response")
        hotels = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            offers = [
                {
                    "vendor": row.get(f"vendor{i}"),
                    "price": parse_inr(row.get(f"price{i}")),
                }
                for i in range(1, 5)
            ]
            offers = [offer for offer in offers if offer["price"] is not None]
            quote = min((offer["price"] for offer in offers), default=None)
            # The public city API documents vendor prices without a nightly/stay-total definition.
            # Only an explicit provider total is safe to include in budget arithmetic.
            total = (
                parse_inr(row.get("total_price"))
                if row.get("currency") == "INR"
                else None
            )
            hotels.append(
                {
                    "id": row.get("hotelId"),
                    "name": row["name"],
                    "url": row.get("url"),
                    "rating": (row.get("reviews") or {}).get("rating"),
                    "currency": "INR",
                    "provider_quote": quote,
                    "price_basis": "UNSPECIFIED",
                    "total_price": total,
                    "price_per_night": None,
                    "offers": offers,
                    "source": "Makcorps",
                    "source_type": "LIVE_PROVIDER",
                }
            )
        if not hotels:
            return unavailable("No hotels returned for the requested city and dates")
        selected = min(
            hotels,
            key=lambda hotel: (
                hotel["provider_quote"]
                if hotel["provider_quote"] is not None
                else float("inf")
            ),
        )
        warnings = [
            "Makcorps vendor quotes have no confirmed nightly/stay-total basis; unconfirmed totals are excluded from the budget."
        ]
        if hotel_type != "Budget":
            warnings.append(
                "Requested hotel star class cannot be verified from the Makcorps city response; guest ratings are not star classifications."
            )
        return {
            **base,
            **selected,
            "success": True,
            "status": "SUCCESS",
            "hotels": hotels[:10],
            "warnings": warnings,
        }
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return unavailable(
            "Makcorps request failed or the city could not be resolved uniquely"
        )
