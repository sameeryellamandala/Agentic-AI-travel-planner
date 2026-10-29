"""Workflow contracts use scripted agent outputs, never production fallbacks."""

from copy import deepcopy
from unittest.mock import Mock
import json
import pytest
from fastapi.testclient import TestClient
import api
from graph import create_graph
from schemas.travel import TravelRequest
from utils.trip import prepare_context

REQUEST = {
    "source_city": "Bengaluru",
    "destination": "Goa",
    "start_date": "2026-10-31",
    "end_date": "2026-11-02",
    "passengers": 2,
    "budget": 30000,
}


class ScriptedCrew:
    def __init__(self, rejections=0, bad_reference=False):
        self.rejections = rejections
        self.bad_reference = bad_reference
        self.research_calls = 0
        self.itinerary_inputs = []
        self.review_inputs = []

    def research(self, context):
        self.research_calls += 1
        self.context = context
        candidates, weather = {}, {}
        for day in context["days"]:
            ident = f"place-{day['day']}"
            candidates[ident] = {
                **day,
                "candidate_id": ident,
                "name": f"Sourced attraction {day['day']}",
                "kind": "places",
                "url": f"https://en.wikipedia.org/wiki/Fixture_{day['day']}",
            }
            weather[str(day["day"])] = {**day, "success": True, "temperature": 28}
        return {
            "candidates": candidates,
            "weather": weather,
            "transport": {
                leg["id"]: {"success": True, "price": 2500.25, "currency": "INR"}
                for leg in context["transport_legs"]
            },
            "stays": {
                stay["id"]: {
                    "success": True,
                    "name": "Provider hotel",
                    "total_price": 6000.5,
                    "currency": "INR",
                }
                for stay in context["stay_periods"]
            },
        }

    def itinerary(self, payload):
        self.itinerary_inputs.append(deepcopy(payload))
        return {
            "days": [
                {
                    **day,
                    "title": f"Explore {day['location']}",
                    "highlights": "Discover local sights and the stories behind them.",
                    "visits": [
                        {
                            "candidate_id": "invented"
                            if self.bad_reference
                            else f"place-{day['day']}",
                            "why_visit": "A sourced landmark.",
                            "what_to_do": "Explore the site.",
                        }
                    ],
                }
                for day in self.context["days"]
            ]
        }

    def review(self, payload):
        self.review_inputs.append(deepcopy(payload))
        failed = len(self.review_inputs) <= self.rejections
        return {
            "status": "NEEDS_REVISION" if failed else "APPROVED",
            "issues": [
                {
                    "day": 1,
                    "problem": "Pacing needs adjustment",
                    "suggested_fix": "Allow a slower morning",
                }
            ]
            if failed
            else [],
        }


def run(runner=None, request=None):
    return create_graph(runner or ScriptedCrew()).invoke(
        {"user_requirements": request or REQUEST}
    )


@pytest.mark.parametrize(
    ("rejects", "attempts", "status"),
    [
        (0, 1, "APPROVED"),
        (1, 2, "APPROVED"),
        (2, 3, "APPROVED"),
        (10, 3, "NEEDS_REVISION"),
    ],
)
def test_review_routing_and_handoffs(rejects, attempts, status):
    runner = ScriptedCrew(rejects)
    result = run(runner)
    plan = result["trip_plan"]
    assert runner.research_calls == 1
    assert len(runner.itinerary_inputs) == len(runner.review_inputs) == attempts
    assert plan["metadata"]["revision_count"] == attempts - 1
    assert plan["review"]["status"] == status
    assert len(plan["review_history"]) == attempts
    for payload in runner.itinerary_inputs:
        assert payload["research"]["candidates"]
        assert payload["context"]["user_requirements"]["passengers"] == 2
    if attempts > 1:
        assert runner.itinerary_inputs[1]["review_feedback"]["issues"]
        assert runner.itinerary_inputs[1]["previous_draft"]["days"]
    assert runner.review_inputs[0]["budget"]["total"] == 11001
    assert runner.review_inputs[0]["research"]["candidates"]
    assert plan["budget"]["within_budget"] is None
    assert plan["metadata"]["planning_status"] == "PARTIAL"


def test_hallucinated_references_are_replaced_with_verified_source_guide():
    runner = ScriptedCrew(bad_reference=True)
    result = run(runner)["trip_plan"]
    assert len(runner.itinerary_inputs) == 1
    assert result["metadata"]["guide_mode"] == "SOURCE_GUIDE"
    assert all(day["activities"] for day in result["days"])
    assert all(
        item["candidate_id"] != "invented"
        for day in result["days"]
        for item in day["activities"]
    )
    assert any("could not be verified" in warning for warning in result["warnings"])


def test_cross_day_and_date_mismatch_are_rejected():
    runner = ScriptedCrew()
    original = runner.itinerary

    def wrong(payload):
        draft = original(payload)
        draft["days"][0]["visits"][0]["candidate_id"] = "place-2"
        draft["days"][0]["date"] = "2026-10-30"
        return draft

    runner.itinerary = wrong
    plan = run(runner)["trip_plan"]
    assert plan["days"][0]["activities"][0]["candidate_id"] == "place-1"
    assert plan["days"][0]["date"] == REQUEST["start_date"]
    assert plan["metadata"]["guide_mode"] == "SOURCE_GUIDE"


@pytest.mark.parametrize("stage", ["research", "itinerary", "review"])
def test_agent_failure_is_explicit_and_terminates(stage):
    runner = ScriptedCrew()
    setattr(runner, stage, Mock(side_effect=RuntimeError("provider unavailable")))
    plan = run(runner)["trip_plan"]
    assert plan["metadata"]["planning_status"] != "COMPLETE"
    assert any("failed" in warning for warning in plan["warnings"])
    assert plan["metadata"]["revision_count"] == 0


def test_single_day_and_multiple_stay_periods():
    assert not prepare_context({**REQUEST, "end_date": REQUEST["start_date"]})[
        "stay_periods"
    ]
    context = prepare_context({**REQUEST, "day_locations": ["Goa", "Panaji", "Panaji"]})
    assert [stay["nights"] for stay in context["stay_periods"]] == [1, 1]
    assert len(context["transport_legs"]) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"passengers": 0},
        {"source_city": ""},
        {"end_date": "2026-10-30"},
        {"budget": "-1"},
        {"budget": "nan"},
        {"day_locations": ["Goa"]},
    ],
)
def test_request_validation(changes):
    with pytest.raises(ValueError):
        TravelRequest.model_validate({**REQUEST, **changes})


def test_api_response_and_progress_stream(monkeypatch):
    monkeypatch.setattr(api, "graph", create_graph(ScriptedCrew()))
    client = TestClient(api.app)
    response = client.post("/api/plan", json=REQUEST)
    assert response.status_code == 200
    assert response.json()["data"]["review"]["status"] == "APPROVED"
    response = client.post("/api/plan/stream", json=REQUEST)
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]["type"] == "result"
    assert {event.get("completed") for event in events} >= {
        "research_trip",
        "review_itinerary",
    }
    assert (
        client.post("/api/plan", json={**REQUEST, "passengers": 0}).status_code == 422
    )


def test_stream_reports_failure(monkeypatch):
    monkeypatch.setattr(api, "graph", Mock(stream=Mock(side_effect=RuntimeError())))
    events = (
        TestClient(api.app).post("/api/plan/stream", json=REQUEST).text.splitlines()
    )
    assert json.loads(events[-1])["type"] == "error"


def test_empty_research_stops_before_generation():
    runner = ScriptedCrew()
    runner.research = Mock(return_value={"warnings": ["No provider data available"]})
    runner.itinerary = Mock()
    plan = run(runner)["trip_plan"]
    runner.itinerary.assert_not_called()
    assert plan["metadata"]["planning_status"] == "FAILED"
