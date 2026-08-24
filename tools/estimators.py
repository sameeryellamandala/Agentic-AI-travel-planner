def calculate_distance(origin: str, destination: str) -> float:
    """Mock distance calculation for estimators."""
    # In reality, this would use geopy or a routing API.
    # For now, generate a somewhat deterministic distance based on string length
    base = (len(origin) + len(destination)) * 100
    return float(base % 2000 + 500) # Between 500 and 2500 km

def estimate_train_fare(distance: float, train_class: str = "3A") -> dict:
    """Estimates train fare based on distance and class."""
    FARE_PER_KM = {
        "Sleeper": 0.55,
        "3A": 1.45,
        "2A": 2.05,
        "1A": 2.80
    }
    rate = FARE_PER_KM.get(train_class, 1.45)
    cost = int(distance * rate)
    
    return {
        "type": "train",
        "source": "Python Estimator",
        "source_type": "ESTIMATED",
        "min_price": int(cost * 0.9),
        "max_price": int(cost * 1.1),
        "currency": "INR",
        "reason": "No live train API"
    }

def estimate_bus_fare(distance: float, bus_type: str = "AC") -> dict:
    """Estimates bus fare based on distance and type."""
    FARE_PER_KM = {
        "Ordinary": 0.75,
        "AC": 1.20,
        "Sleeper": 1.50
    }
    rate = FARE_PER_KM.get(bus_type, 1.20)
    cost = int(distance * rate)
    
    return {
        "type": "bus",
        "source": "Python Estimator",
        "source_type": "ESTIMATED",
        "min_price": int(cost * 0.9),
        "max_price": int(cost * 1.1),
        "currency": "INR",
        "reason": "No live bus API"
    }

def estimate_hotel_fallback(nights: int, tier: str = "3-star") -> dict:
    """Deterministic fallback hotel estimator."""
    HOTEL_ESTIMATE = {
        "Budget": 1500,
        "3-star": 3000,
        "4-star": 6000,
        "5-star": 12000
    }
    base = HOTEL_ESTIMATE.get(tier, 3000)
    
    return {
        "type": "hotel",
        "source": "Python Fallback Estimator",
        "source_type": "ESTIMATED",
        "price_per_night": base,
        "total_estimated": base * nights,
        "currency": "INR",
        "reason": "Live hotel data unavailable"
    }
