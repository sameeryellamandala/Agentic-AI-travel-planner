"""LangGraph controls CrewAI research, itinerary generation and bounded review."""

import logging
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents.tasks import CrewRunner
from schemas.research import ResearchFindings, ItineraryDraft
from schemas.review import ReviewResult
from schemas.travel import DayPlan, TripPlan
from utils.trip import prepare_context
from utils.budget import calculate_budget
from utils.day_guide import source_guide, valid_references
from utils.review_policy import apply_review_policy

MAX_REVISIONS = 2
logger = logging.getLogger(__name__)


class TravelState(TypedDict, total=False):
    user_requirements: dict
    context: dict
    research: dict
    itinerary: dict
    daily_plans: list
    transport_legs: list
    stay_periods: list
    budget_breakdown: dict
    validation_issues: list
    review: dict
    review_history: list
    revision_count: int
    attempts: int
    warnings: list
    agent_activity: list
    fatal_error: bool
    guide_mode: str
    trip_plan: dict


def prepare_trip(state):
    context = prepare_context(state["user_requirements"])
    return {
        "context": context,
        "user_requirements": context["user_requirements"],
        "transport_legs": context["transport_legs"],
        "stay_periods": context["stay_periods"],
        "research": ResearchFindings().model_dump(),
        "itinerary": {"days": []},
        "revision_count": 0,
        "attempts": 0,
        "review_history": [],
        "warnings": [],
        "agent_activity": ["Trip requirements checked"],
        "fatal_error": False,
        "guide_mode": "AI_GUIDE",
    }


def failure(state, stage, exc):
    logger.warning("%s failed (%s)", stage, type(exc).__name__)
    return {
        "warnings": state["warnings"]
        + [
            f"{stage} failed ({type(exc).__name__}). Check provider configuration and availability."
        ],
        "fatal_error": True,
    }


def research_trip(state, runner):
    try:
        research = ResearchFindings.model_validate(
            runner.research(state["context"])
        ).model_dump()
        warnings = state["warnings"] + research["warnings"]
        for day in state["context"]["days"]:
            if str(day["day"]) not in research["weather"]:
                warnings.append(f"Day {day['day']}: weather was not retrieved.")
        legs = [
            {**leg, "result": research["transport"].get(leg["id"], {})}
            for leg in state["transport_legs"]
        ]
        stays = [
            {**stay, "result": research["stays"].get(stay["id"], {})}
            for stay in state["stay_periods"]
        ]
        for record in legs + stays:
            if not record["result"]:
                warnings.append(f"{record['id']}: information was not retrieved.")
        return {
            "research": research,
            "transport_legs": legs,
            "stay_periods": stays,
            "warnings": warnings,
            "agent_activity": state["agent_activity"]
            + ["Research completed using MCP tools"],
            "fatal_error": not bool(research["candidates"]),
        }
    except Exception as exc:
        return failure(state, "Research", exc)


def create_itinerary(state, runner):
    try:
        previous = {
            "days": [
                {
                    key: value
                    for key, value in day.items()
                    if key in ("day", "date", "location", "title")
                }
                | {
                    "visits": [
                        visit["candidate_id"] for visit in day.get("visits", [])
                    ],
                    "food_experiences": [
                        item["candidate_id"] for item in day.get("food_experiences", [])
                    ],
                }
                for day in state["itinerary"].get("days", [])
            ]
        }
        draft = ItineraryDraft.model_validate(
            runner.itinerary(
                {
                    "context": state["context"],
                    "research": state["research"],
                    "previous_draft": previous,
                    "review_feedback": {}
                    if state.get("validation_issues")
                    else state.get("review", {}),
                    "validation_issues": state.get("validation_issues", []),
                }
            )
        ).model_dump()
        warnings = state["warnings"]
        mode = "AI_GUIDE"
        if not valid_references(draft, state["context"], state["research"]):
            draft = source_guide(state["context"], state["research"]).model_dump()
            warnings = warnings + [
                "AI draft references could not be verified; showing a destination-source guide instead."
            ]
            mode = "SOURCE_GUIDE"
        attempts = state["attempts"] + 1
        return {
            "itinerary": draft,
            "attempts": attempts,
            "revision_count": attempts - 1,
            "warnings": warnings,
            "guide_mode": mode,
            "agent_activity": state["agent_activity"]
            + [f"Itinerary attempt {attempts} completed"],
        }
    except Exception as exc:
        logger.warning(
            "Itinerary wording unavailable (%s); using sourced guide",
            type(exc).__name__,
        )
        return {
            "itinerary": source_guide(state["context"], state["research"]).model_dump(),
            "attempts": state["attempts"] + 1,
            "revision_count": state["attempts"],
            "guide_mode": "SOURCE_GUIDE",
            "warnings": state["warnings"]
            + [
                f"AI wording failed ({type(exc).__name__}); showing a guide from verified destination sources."
            ],
            "agent_activity": state["agent_activity"]
            + ["Source guide prepared from verified destination research"],
        }


def validate_and_price(state):
    expected = state["context"]["days"]
    drafts = state["itinerary"].get("days", [])
    registry = state["research"]["candidates"]
    issues, plans = [], []
    visited_names = set()
    if len(drafts) != len(expected):
        issues.append("Itinerary must contain exactly one entry per requested day.")
    for index, actual in enumerate(expected):
        draft = drafts[index] if index < len(drafts) else {}
        if any(draft.get(key) != actual[key] for key in ("day", "date", "location")):
            issues.append(
                f"Day {actual['day']}: date, location, or day number does not match the request."
            )

        def resolve(slot):
            selected = []
            for candidate_id in draft.get(slot, []):
                item = registry.get(candidate_id)
                kind = "food" if slot == "food" else "places"
                if (
                    not item
                    or (
                        item.get("day") != actual["day"]
                        and actual["day"] not in item.get("available_days", [])
                    )
                    or item.get("location") != actual["location"]
                    or item.get("kind") != kind
                ):
                    issues.append(
                        f"Day {actual['day']}: unsupported {slot} reference {candidate_id}."
                    )
                elif candidate_id not in [x["candidate_id"] for x in selected]:
                    selected.append(item)
            return selected

        slots = {
            slot: resolve(slot)
            for slot in ("morning", "afternoon", "evening", "food", "temples")
        }
        activities = []
        for visit in draft.get("visits", []):
            item = registry.get(visit["candidate_id"])
            if (
                not item
                or (
                    item.get("day") != actual["day"]
                    and actual["day"] not in item.get("available_days", [])
                )
                or item.get("location") != actual["location"]
                or item.get("kind") != "places"
            ):
                issues.append(
                    f"Day {actual['day']}: unsupported visit reference {visit['candidate_id']}."
                )
                continue
            activities.append(
                {
                    **item,
                    "why_visit": visit["why_visit"],
                    "what_to_do": visit["what_to_do"],
                }
            )
        if not draft.get("visits"):
            activities = slots["morning"] + slots["afternoon"] + slots["evening"]
        if draft.get("food_experiences"):
            slots["food"] = []
            for experience in draft["food_experiences"]:
                item = registry.get(experience["candidate_id"])
                if (
                    not item
                    or (
                        item.get("day") != actual["day"]
                        and actual["day"] not in item.get("available_days", [])
                    )
                    or item.get("location") != actual["location"]
                    or item.get("kind") != "food"
                ):
                    issues.append(
                        f"Day {actual['day']}: unsupported food reference {experience['candidate_id']}."
                    )
                    continue
                slots["food"].append({**item, "what_to_try": experience["what_to_try"]})
        for item in activities:
            identity = item.get("url") or item["name"].casefold()
            if identity in visited_names:
                issues.append(
                    f"Day {actual['day']}: {item['name']} is repeated; choose another sourced attraction."
                )
            visited_names.add(identity)
        ids = [item["candidate_id"] for item in activities]
        if len(ids) != len(set(ids)):
            issues.append(
                f"Day {actual['day']}: an attraction is scheduled more than once."
            )
        if not activities:
            issues.append(f"Day {actual['day']}: no sourced activities scheduled.")
        weather = state["research"]["weather"].get(str(actual["day"]))
        day_warnings = []
        if not weather or not weather.get("success"):
            day_warnings.append("Weather unavailable; verify conditions before travel.")
        elif (
            weather.get("date") != actual["date"]
            or weather.get("location") != actual["location"]
        ):
            issues.append(f"Day {actual['day']}: weather context mismatch.")
            weather = None
        stay = next(
            (
                s.get("result")
                for s in state["stay_periods"]
                if s["check_in"] <= actual["date"] < s["check_out"]
                and s["location"] == actual["location"]
            ),
            None,
        )
        places = list(
            {x["candidate_id"]: x for x in activities + slots["temples"]}.values()
        )
        plans.append(
            DayPlan(
                **actual,
                **slots,
                title=draft.get("title", ""),
                highlights=draft.get("highlights", ""),
                activities=activities,
                places=places,
                weather=weather,
                hotel=stay,
                warnings=day_warnings,
                summary=draft.get("highlights")
                or f"Day {actual['day']} in {actual['location']}",
                notes=[
                    "Wikipedia provides destination knowledge; confirm opening hours and availability before travel."
                ],
            ).model_dump()
        )
    budget = calculate_budget({**state, "daily_plans": plans})
    return {
        "daily_plans": plans,
        "validation_issues": list(dict.fromkeys(issues)),
        "budget_breakdown": budget,
    }


def review_itinerary(state, runner):
    if state["validation_issues"]:
        review = {
            "status": "NEEDS_REVISION",
            "issues": [
                {
                    "day": None,
                    "problem": issue,
                    "suggested_fix": "Return a complete guide for every requested day using valid source IDs.",
                }
                for issue in state["validation_issues"]
            ],
        }
        return {
            "review": review,
            "review_history": state["review_history"] + [review],
            "agent_activity": state["agent_activity"]
            + ["Draft returned for repair after Python validation"],
        }
    try:
        selected = {
            item["candidate_id"]
            for day in state["daily_plans"]
            for item in day["activities"] + day["food"]
        }
        review_research = {
            **state["research"],
            "candidates": {
                key: item
                for key, item in state["research"]["candidates"].items()
                if key in selected
            },
        }
        review = ReviewResult.model_validate(
            runner.review(
                {
                    "requirements": state["user_requirements"],
                    "research": review_research,
                    "itinerary": [
                        {
                            key: day[key]
                            for key in (
                                "day",
                                "date",
                                "location",
                                "title",
                                "highlights",
                            )
                        }
                        | {
                            "visits": [
                                {
                                    key: item.get(key)
                                    for key in (
                                        "candidate_id",
                                        "why_visit",
                                        "what_to_do",
                                    )
                                }
                                for item in day["activities"]
                            ],
                            "food": [
                                {
                                    key: item.get(key)
                                    for key in ("candidate_id", "what_to_try")
                                }
                                for item in day["food"]
                            ],
                        }
                        for day in state["daily_plans"]
                    ],
                    "validation_issues": state["validation_issues"],
                    "budget": state["budget_breakdown"],
                }
            )
        ).model_dump()
        review = apply_review_policy(review)
        if state["validation_issues"]:
            review["status"] = "NEEDS_REVISION"
            review["issues"] += [
                {
                    "day": None,
                    "problem": issue,
                    "suggested_fix": "Repair the itinerary using the supplied research and trip context.",
                }
                for issue in state["validation_issues"]
            ]
        if review["issues"]:
            review["status"] = "NEEDS_REVISION"
        return {
            "review": review,
            "review_history": state["review_history"] + [review],
            "agent_activity": state["agent_activity"]
            + [f"Review: {review['status'].lower().replace('_', ' ')}"],
        }
    except Exception as exc:
        return {
            **failure(state, "Review", exc),
            "review": {
                "status": "NEEDS_REVISION",
                "issues": [
                    {
                        "day": None,
                        "problem": "Review unavailable; this plan has not been approved.",
                        "suggested_fix": "Retry when the model is available.",
                    }
                ],
            },
        }


def finalize_trip(state):
    if "daily_plans" not in state:
        state = {**state, **validate_and_price(state)}
    warnings = list(state["warnings"]) + state["validation_issues"]
    for day in state["daily_plans"]:
        warnings += day["warnings"]
    review = state.get("review", {"status": "NEEDS_REVISION", "issues": []})
    warnings += [issue["problem"] for issue in review["issues"]]
    budget = state["budget_breakdown"]
    if not budget["complete"]:
        warnings.append(
            "Budget is partial: missing costs are excluded. Budget compliance cannot be confirmed."
        )
    if budget["status"] == "OVER_BUDGET":
        warnings.append("Known costs exceed your requested budget.")
    scheduled = sum(bool(day["activities"]) for day in state["daily_plans"])
    status = (
        "FAILED"
        if not scheduled
        else (
            "PARTIAL"
            if warnings or state["fatal_error"] or review["status"] != "APPROVED"
            else "COMPLETE"
        )
    )
    plan = TripPlan(
        metadata={
            **state["user_requirements"],
            "total_days": len(state["context"]["days"]),
            "planning_status": status,
            "revision_count": state["revision_count"],
            "review_status": review["status"],
            "guide_mode": state.get("guide_mode", "AI_GUIDE"),
        },
        transport=state["transport_legs"],
        accommodation=state["stay_periods"],
        days=state["daily_plans"],
        budget=budget,
        randomization={
            "seed": state["user_requirements"]["random_seed"],
            "decisions": [],
        },
        warnings=list(dict.fromkeys(warnings)),
        tool_trace=state["research"]["tool_trace"],
        review=review,
        review_history=state["review_history"],
        agent_activity=state["agent_activity"],
    ).model_dump()
    return {"trip_plan": plan}


def create_graph(runner=None):
    runner = runner or CrewRunner()
    builder = StateGraph(TravelState)
    builder.add_node("prepare_trip", prepare_trip)
    builder.add_node("research_trip", lambda s: research_trip(s, runner))
    builder.add_node("create_itinerary", lambda s: create_itinerary(s, runner))
    builder.add_node("validate_and_price", validate_and_price)
    builder.add_node("review_itinerary", lambda s: review_itinerary(s, runner))
    builder.add_node("finalize_trip", finalize_trip)
    builder.add_edge(START, "prepare_trip")
    builder.add_edge("prepare_trip", "research_trip")
    builder.add_conditional_edges(
        "research_trip",
        lambda s: "finalize_trip" if s["fatal_error"] else "create_itinerary",
    )
    builder.add_conditional_edges(
        "create_itinerary",
        lambda s: "finalize_trip" if s["fatal_error"] else "validate_and_price",
    )
    builder.add_edge("validate_and_price", "review_itinerary")
    builder.add_conditional_edges(
        "review_itinerary",
        lambda s: (
            "create_itinerary"
            if not s["fatal_error"]
            and s["review"]["status"] == "NEEDS_REVISION"
            and s["revision_count"] < MAX_REVISIONS
            else "finalize_trip"
        ),
    )
    builder.add_edge("finalize_trip", END)
    return builder.compile()


graph = create_graph()
