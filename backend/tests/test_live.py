import os
from datetime import date, timedelta
import pytest
from graph import graph
from tests.test_workflow import REQUEST


@pytest.mark.integration
def test_live_trip():
    if os.getenv("RUN_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_TESTS=1 to enable live provider calls")
    start = date.today() + timedelta(days=2)
    request = {
        **REQUEST,
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "transport_mode": "Train",
        "rail_distance_km": 600,
    }
    plan = None
    for update in graph.stream({"user_requirements": request}):
        for node, result in update.items():
            print(f"Completed: {node}", flush=True)
            if node == "finalize_trip":
                plan = result["trip_plan"]
    assert plan is not None
    assert plan["tool_trace"], "No actual MCP calls recorded"
    assert plan["days"][0]["activities"], "No sourced itinerary generated"
    print("Final review:", plan["review"], flush=True)
    if plan["review"]["status"] == "NEEDS_REVISION":
        assert plan["metadata"]["revision_count"] == 2
        assert plan["review"]["issues"]
        assert plan["metadata"]["planning_status"] == "PARTIAL"
    else:
        assert plan["review"]["status"] == "APPROVED"
