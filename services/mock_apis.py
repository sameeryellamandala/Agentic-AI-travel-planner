import random

def get_flight_data(origin: str, destination: str, date: str):
    """Mocks the Ignav API for flights."""
    # Simulate API failure randomly for testing fallback (10% chance)
    if random.random() < 0.1:
        return {"type": "flight", "source": "Ignav", "source_type": "UNAVAILABLE", "error": "API unavailable"}
    
    price = random.randint(4000, 15000)
    return {
        "type": "flight",
        "source": "Ignav",
        "source_type": "LIVE",
        "origin": origin,
        "destination": destination,
        "price": price,
        "currency": "INR",
        "airline": random.choice(["Air India", "IndiGo", "SpiceJet", "Vistara"])
    }

def get_hotel_data(destination: str, checkin: str, checkout: str, tier: str = "3-star"):
    """Mocks the StayingAPI for hotels."""
    # Simulate API failure randomly for testing fallback (20% chance)
    if random.random() < 0.2:
        return {"type": "hotel", "source": "StayingAPI", "source_type": "UNAVAILABLE", "error": "API unavailable"}
    
    base_prices = {"Budget": 1500, "3-star": 3000, "4-star": 6000, "5-star": 12000}
    # Fallback to standard 3-star if tier is unknown
    base = base_prices.get(tier, 3000)
    price = int(base * random.uniform(0.8, 1.2))
    
    return {
        "type": "hotel",
        "source": "StayingAPI",
        "source_type": "LIVE",
        "name": f"The {destination} Grand",
        "price_per_night": price,
        "currency": "INR",
        "rating": round(random.uniform(3.5, 5.0), 1)
    }

def get_weather_data(destination: str):
    """Mocks the OpenWeather API."""
    if random.random() < 0.1:
        return {"type": "weather", "source": "OpenWeather", "source_type": "UNAVAILABLE"}
    
    return {
        "type": "weather",
        "source": "OpenWeather",
        "source_type": "LIVE",
        "temperature": random.randint(15, 35),
        "condition": random.choice(["Clear", "Cloudy", "Rain", "Partly Cloudy"])
    }
