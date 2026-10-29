from unittest.mock import Mock
from mcp_tools.server import ResearchTools
from mcp_tools.client import ResearchLedger, research_tools
from tests.test_workflow import REQUEST


def test_server_dates_leg_cache_and_stay_reuse(monkeypatch):
    weather = Mock(return_value={"success": True})
    flight = Mock(return_value={"success": True, "price": 100, "currency": "INR"})
    stay = Mock(return_value={"success": True, "total_price": 200, "currency": "INR"})
    monkeypatch.setattr("mcp_tools.server.get_live_weather", weather)
    monkeypatch.setattr("mcp_tools.server.search_ignav_flights", flight)
    monkeypatch.setattr("mcp_tools.server.search_stay_hotels", stay)
    server = ResearchTools(REQUEST)
    assert server.call("get_weather", {"day": 2})["date"] == "2026-11-01"
    weather.assert_called_once_with("Goa", "2026-11-01")
    assert not server.call("get_weather", {"day": 50})["success"]
    server.call("search_transport", {"leg_id": "leg-1"})
    assert server.call("search_transport", {"leg_id": "leg-1"})["cached"]
    assert not server.call("search_transport", {"leg_id": "local-taxi"})["success"]
    assert flight.call_count == 1
    server.call("search_stay", {"stay_id": "stay-1"})
    assert server.call("search_stay", {"stay_id": "stay-1"})["cached"]
    stay.assert_called_once_with(
        "Goa", "2026-10-31", "2026-11-02", 2, "Budget", rooms=1
    )


def test_candidate_ledger_contains_only_provider_results(monkeypatch):
    monkeypatch.setattr(
        "mcp_tools.server.search_wikipedia_places",
        Mock(
            return_value={
                "status": "SUCCESS",
                "places": [
                    {
                        "name": "Provider sight",
                        "url": "https://en.wikipedia.org/wiki/Goa",
                    }
                ],
            }
        ),
    )
    result = ResearchTools(REQUEST).call(
        "search_places", {"day": 1, "query": "culture"}
    )
    ledger = ResearchLedger()
    ledger.record("search_places", {"day": 1}, result)
    item = next(iter(ledger.findings.candidates.values()))
    assert item["day"] == 1 and item["kind"] == "places"
    assert item["name"] == "Provider sight"
    assert len(ledger.findings.tool_trace) == 1


def test_destination_knowledge_is_shared_without_requerying(monkeypatch):
    provider = Mock(
        return_value={"status": "SUCCESS", "places": [{"name": "Fort Aguada"}]}
    )
    monkeypatch.setattr("mcp_tools.server.search_wikipedia_places", provider)
    server = ResearchTools(REQUEST)
    first = server.call("search_places", {"day": 1, "query": "forts"})
    later = server.call("search_places", {"day": 2, "query": "beaches"})
    provider.assert_called_once()
    assert first["places"][0]["available_days"] == [1, 2, 3]
    assert later["knowledge_reused"]


def test_real_stdio_discovery_tool_call_and_cleanup():
    # No external provider call: invalid day is rejected inside the real MCP server.
    with research_tools(REQUEST) as (tools, ledger):
        assert {tool.name for tool in tools} == {
            "get_weather",
            "search_places",
            "search_food",
            "search_transport",
            "search_stay",
        }
        tool = next(tool for tool in tools if tool.name == "get_weather")
        tool.run(day=99)
        assert not ledger.findings.weather["99"]["success"]
        assert len(ledger.findings.tool_trace) == 1
    assert ledger.findings.warnings
