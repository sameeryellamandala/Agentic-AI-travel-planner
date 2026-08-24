import re
from typing import Dict, Any

def parse_budget(budget_str: str) -> int:
    """Parses a budget string (e.g. '20,000 INR') into an integer."""
    if not budget_str:
        return 0
    numbers = re.findall(r'\d+', budget_str.replace(',', ''))
    if numbers:
        return int(numbers[0])
    return 0

def calculate_budget(state: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministically calculates total budget from live and estimated items."""
    days = state.get("days", 1)
    breakdown = {
        "transport": 0,
        "hotel": 0,
        "food": 1000 * days,
        "activities": 500 * days
    }
    
    mode = state.get("transport_mode", "Flight").lower()
    
    transport_cost = 0
    if mode == "flight" and state.get("flights") and state["flights"][0].get("source_type") == "LIVE":
        transport_cost = state["flights"][0].get("price", 0)
    elif mode == "train" and state.get("train_estimate"):
        transport_cost = state["train_estimate"].get("max_price", 0)
    elif mode == "bus" and state.get("bus_estimate"):
        transport_cost = state["bus_estimate"].get("max_price", 0)
    else:
        if state.get("train_estimate"):
             transport_cost = state["train_estimate"].get("max_price", 0)
    breakdown["transport"] = transport_cost
    
    hotel_cost = 0
    if state.get("hotels") and state["hotels"][0].get("source_type") == "LIVE":
        hotel_cost = state["hotels"][0].get("price_per_night", 0) * days
    else:
        from tools.estimators import estimate_hotel_fallback
        est = estimate_hotel_fallback(days, state.get("hotel_type", "3-star"))
        hotel_cost = est["total_estimated"]
    breakdown["hotel"] = hotel_cost
    
    total = sum(breakdown.values())
    
    return {
        "total": total,
        "breakdown": breakdown,
        "currency": "INR"
    }
