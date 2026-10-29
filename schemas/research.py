from typing import Any
from pydantic import BaseModel, Field


class ResearchFindings(BaseModel):
    candidates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    weather: dict[str, dict[str, Any]] = Field(default_factory=dict)
    transport: dict[str, dict[str, Any]] = Field(default_factory=dict)
    stays: dict[str, dict[str, Any]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)


class ItineraryDay(BaseModel):
    day: int
    date: str
    location: str
    title: str = ""
    highlights: str = ""
    visits: list["PlannedVisit"] = Field(default_factory=list)
    food_experiences: list["FoodExperience"] = Field(default_factory=list)
    morning: list[str] = Field(default_factory=list)
    afternoon: list[str] = Field(default_factory=list)
    evening: list[str] = Field(default_factory=list)
    food: list[str] = Field(default_factory=list)
    temples: list[str] = Field(default_factory=list)


class ItineraryDraft(BaseModel):
    days: list[ItineraryDay]


class PlannedVisit(BaseModel):
    candidate_id: str
    why_visit: str
    what_to_do: str


class FoodExperience(BaseModel):
    candidate_id: str
    what_to_try: str


ItineraryDay.model_rebuild()
