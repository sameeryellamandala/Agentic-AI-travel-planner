from unittest.mock import Mock
from agents.llm import GroqLLM
from agents.tasks import CrewRunner
from schemas.research import ResearchFindings
from tests.test_workflow import REQUEST
from utils.trip import prepare_context


def test_groq_adapter_removes_only_unsupported_cache_fields():
    llm = GroqLLM(model="groq/openai/gpt-oss-120b", is_litellm=True, api_key="fixture")
    messages = [
        {"role": "system", "content": "Plan a trip", "cache_breakpoint": True},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "abc"}]},
    ]
    result = llm._format_messages_for_provider(messages)
    assert result[0] == {"role": "system", "content": "Plan a trip"}
    assert result[1]["tool_calls"] == [{"id": "abc"}]
    assert messages[0]["cache_breakpoint"] is True


def test_research_failure_keeps_actual_tool_results(monkeypatch):
    from contextlib import contextmanager

    findings = ResearchFindings(candidates={"real": {"name": "Provider item"}})

    @contextmanager
    def connection(_):
        yield [], Mock(findings=findings)

    monkeypatch.setattr("agents.tasks.research_tools", connection)
    runner = CrewRunner()
    runner._run = Mock(side_effect=RuntimeError("model stopped"))
    result = runner.research(prepare_context(REQUEST))
    assert result.candidates == {"real": {"name": "Provider item"}}
    assert result.warnings and "RuntimeError" in result.warnings[0]


def test_long_quota_wait_is_not_silently_retried(monkeypatch):
    from crewai import LLM
    from agents.llm import GroqQuotaUnavailable
    import pytest

    error = RuntimeError("tokens per day exhausted")
    request = Mock(side_effect=error)
    monkeypatch.setattr(LLM, "_handle_non_streaming_response", request)
    llm = GroqLLM(model="groq/openai/gpt-oss-120b", is_litellm=True, api_key="fixture")
    with pytest.raises(GroqQuotaUnavailable) as failure:
        llm._handle_non_streaming_response()
    assert failure.value.__context__ is None
    request.assert_called_once()


def test_writer_plans_each_day_and_excludes_already_used_places():
    from schemas.research import ItineraryDraft

    runner = CrewRunner()
    context = prepare_context(REQUEST)
    candidates = {
        f"L1-P{i}": {
            "candidate_id": f"L1-P{i}",
            "name": f"Place {i}",
            "location": "Goa",
            "day": 1,
            "available_days": [1, 2, 3],
            "kind": "places",
            "url": f"https://example.com/{i}",
        }
        for i in (1, 2, 3)
    }
    scopes = []

    def write(payload):
        scopes.append(payload)
        day = payload["planning_day"]
        return ItineraryDraft.model_validate(
            {
                "days": [
                    {
                        **day,
                        "title": "Local highlights",
                        "visits": [
                            {
                                "candidate_id": f"L1-P{day['day']}",
                                "why_visit": "Source-backed highlight",
                                "what_to_do": "Explore the site",
                            }
                        ],
                    }
                ]
            }
        )

    runner._write_day = write
    result = runner.itinerary(
        {"context": context, "research": {"candidates": candidates}}
    )
    assert len(result.days) == 3
    assert len(scopes[1]["context"]["days"]) == 1
    assert "L1-P1" not in scopes[1]["research"]["candidates"]
    assert "L1-P2" not in scopes[2]["research"]["candidates"]


def test_day_schema_restricts_candidate_ids_and_exact_day():
    import jsonschema
    import pytest
    from agents.tasks import day_response_format

    payload = {
        "planning_day": {"day": 1, "date": "2026-10-31", "location": "Goa"},
        "research": {
            "candidates": {"L1-P1": {"kind": "places"}, "L1-F1": {"kind": "food"}}
        },
    }
    schema = day_response_format(payload)["json_schema"]["schema"]
    llm = GroqLLM(
        model="groq/openai/gpt-oss-20b",
        is_litellm=True,
        api_key="fixture",
        response_format=day_response_format(payload),
    )
    assert llm.response_format["type"] == "json_schema"
    valid = {
        "days": [
            {
                **payload["planning_day"],
                "title": "Coastal highlights",
                "highlights": "Explore the coast.",
                "visits": [
                    {
                        "candidate_id": "L1-P1",
                        "why_visit": "A sourced fort.",
                        "what_to_do": "Explore the fort.",
                    }
                ],
                "food_experiences": [
                    {"candidate_id": "L1-F1", "what_to_try": "A local dessert."}
                ],
            }
        ]
    }
    jsonschema.validate(valid, schema)
    valid["days"][0]["food_experiences"][0]["candidate_id"] = "invented"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(valid, schema)
