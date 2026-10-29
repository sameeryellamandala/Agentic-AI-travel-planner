from datetime import date, timedelta
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class TravelRequest(BaseModel):
    source_city: str
    destination: str
    start_date: date
    end_date: date
    budget: str | float = 0
    passengers: int = Field(default=1, ge=1, le=100)
    rooms: int = Field(default=1, ge=1, le=100)
    food_allowance: float = Field(default=600, ge=0, allow_inf_nan=False)
    activity_allowance: float = Field(default=300, ge=0, allow_inf_nan=False)
    hotel_allowance: float = Field(default=2500, ge=0, allow_inf_nan=False)
    transport_mode: Literal["Flight", "Train"] = "Flight"
    train_class: Literal["SL", "3A", "2A", "1A"] = "3A"
    rail_distance_km: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    hotel_type: str = "Budget"
    interests: list[str] = Field(default_factory=list)
    random_seed: int = 0
    day_locations: list[str] | None = None

    @field_validator("source_city", "destination")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Location must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def dates(self):
        if self.transport_mode == "Train" and self.rail_distance_km is None:
            raise ValueError(
                "Enter the one-way source to destination railway distance in km for Train"
            )
        days = (self.end_date - self.start_date).days + 1
        if not 1 <= days <= 30:
            raise ValueError("Trip must contain 1 to 30 inclusive calendar days")
        if self.day_locations is not None and (
            len(self.day_locations) != days
            or any(not x.strip() for x in self.day_locations)
        ):
            raise ValueError("day_locations must contain one nonempty location per day")
        from utils.budget import parse_budget

        parse_budget(self.budget)
        return self


class DayPlan(BaseModel):
    title: str = ""
    highlights: str = ""
    day: int
    date: str
    location: str
    weather: dict[str, Any] | None = None
    hotel: dict[str, Any] | None = None
    places: list[dict[str, Any]] = Field(default_factory=list)
    food: list[dict[str, Any]] = Field(default_factory=list)
    temples: list[dict[str, Any]] = Field(default_factory=list)
    activities: list[dict[str, Any]] = Field(default_factory=list)
    morning: list[dict[str, Any]] = Field(default_factory=list)
    afternoon: list[dict[str, Any]] = Field(default_factory=list)
    evening: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""
    daily_cost: float = 0


class TripPlan(BaseModel):
    metadata: dict[str, Any]
    transport: list[dict[str, Any]]
    accommodation: list[dict[str, Any]]
    days: list[DayPlan]
    budget: dict[str, Any]
    randomization: dict[str, Any]
    warnings: list[str]
    tool_trace: list[dict[str, Any]]
    review: dict[str, Any] = Field(default_factory=dict)
    review_history: list[dict[str, Any]] = Field(default_factory=list)
    agent_activity: list[str] = Field(default_factory=list)


TripResponseData = TripPlan


class APIResponse(BaseModel):
    status: str = "success"
    data: TripPlan
