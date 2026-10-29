from copy import deepcopy
from tests.test_workflow import ScriptedCrew, run, REQUEST
from utils.budget import calculate_budget
from utils.evidence import compact


def test_guide_keeps_source_and_practical_advice():
    plan = run()["trip_plan"]
    day = plan["days"][0]
    assert day["title"] and day["highlights"]
    assert day["activities"][0]["why_visit"] == "A sourced landmark."
    assert day["activities"][0]["what_to_do"] == "Explore the site."
    assert not day["morning"] and not day["afternoon"] and not day["evening"]


def test_same_place_under_different_day_ids_is_flagged():
    runner = ScriptedCrew()
    original = runner.research

    def repeated(context):
        data = original(context)
        for item in data["candidates"].values():
            item["url"] = "https://en.wikipedia.org/wiki/Fort_Aguada"
        return data

    runner.research = repeated
    result = run(runner)["trip_plan"]
    assert result["review"]["status"] == "NEEDS_REVISION"
    used = [item["url"] for day in result["days"] for item in day["activities"]]
    assert len(used) == len(set(used)) == 1
    assert result["metadata"]["guide_mode"] == "SOURCE_GUIDE"


def test_shared_knowledge_can_be_used_on_a_later_allowed_day():
    runner = ScriptedCrew()
    original = runner.research

    def shared(context):
        data = original(context)
        data["candidates"]["place-2"]["day"] = 1
        data["candidates"]["place-2"]["available_days"] = [1, 2, 3]
        return data

    runner.research = shared
    plan = run(runner)["trip_plan"]
    assert plan["days"][1]["activities"]
    assert plan["review"]["status"] == "APPROVED"


def test_estimate_covers_whole_party_and_aggregates_missing_costs():
    state = {
        "user_requirements": {
            **REQUEST,
            "rooms": 1,
            "food_allowance": 600,
            "activity_allowance": 300,
            "hotel_allowance": 2500,
        },
        "daily_plans": [{"day": i} for i in (1, 2, 3)],
        "transport_legs": [],
        "stay_periods": [
            {
                "location": "Goa",
                "check_in": "2026-10-31",
                "check_out": "2026-11-02",
                "nights": 2,
            }
        ],
    }
    budget = calculate_budget(state)
    assert (
        budget["planning_total"] == 10400
    )  # 3 days × 2 people × (600 + 300), plus 2 hotel nights
    assert budget["known_subtotal"] == 0
    assert len(budget["entries"]) == 3
    assert budget["within_budget"] is None
    assert {item["provenance"] for item in budget["planning_entries"]} == {
        "PLANNING_ALLOWANCE"
    }


def test_shared_source_evidence_is_sent_once_without_changing_ledger():
    raw = {
        "candidates": {
            f"d{i}": {
                "name": "Fort Aguada",
                "description": "A fort in Goa.",
                "url": "https://en.wikipedia.org/wiki/Fort_Aguada",
                "day": i,
            }
            for i in (1, 2, 3)
        }
    }
    before = deepcopy(raw)
    result = compact(raw)
    assert sum("description" in item for item in result["candidates"].values()) == 1
    assert result["candidates"]["d2"]["same_as"] == "d1"
    assert len(result["candidates"]) == 3
    assert raw == before


def test_missing_provider_prices_do_not_trigger_revisions():
    runner = ScriptedCrew()
    runner.review = lambda _: {
        "status": "NEEDS_REVISION",
        "issues": [
            {
                "day": None,
                "problem": "Missing cost data for accommodation, food, and activities; hotel search failed and no pricing available.",
                "suggested_fix": "Obtain hotel quotes.",
            }
        ],
    }
    plan = run(runner)["trip_plan"]
    assert len(runner.itinerary_inputs) == 1
    assert plan["review"]["status"] == "APPROVED"
    assert plan["review"]["notes"]


def test_fabricated_price_claim_is_still_blocking():
    from utils.review_policy import apply_review_policy

    review = apply_review_policy(
        {
            "status": "NEEDS_REVISION",
            "issues": [
                {"problem": "Hotel cost is fabricated and price source unavailable."}
            ],
        }
    )
    assert review["status"] == "NEEDS_REVISION"
    assert review["issues"]
