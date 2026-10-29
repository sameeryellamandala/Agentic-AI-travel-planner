# Implementation Plan

## Goal

Replace the current direct LLM tool-calling workflow with CrewAI agents, tools exposed through our own MCP server, and LangGraph controlling the overall planning process.

Keep the existing user input flow: the user enters travel requirements and clicks **Start Planning**.

## Agreed responsibilities

| Component | Responsibility |
| --- | --- |
| LangGraph | Control step order, hold shared trip information, and route revisions |
| CrewAI | Run the research, itinerary, and review agents |
| MCP server | Expose the existing project services as tools |
| Python validation | Check structured outputs and references to research |
| Python budget calculation | Calculate costs and compare them with the user's budget |
| Existing interface | Collect requirements and display results |

## Execution flow

```text
User clicks Start Planning
          |
Validate requirements and prepare trip context
          |
Research agent calls MCP tools
          |
Itinerary agent creates the complete trip plan
          |
Python validates the plan and calculates its budget
          |
Review agent checks requirements, research, plan, and calculation results
          |
LangGraph checks the review result
          |
          +-- Approved --------------------------> Finalize and display
          |
          +-- Needs revision, attempts remain --> Itinerary agent revises
          |                                         |
          |                           Validate, calculate, and review again
          |
          +-- Two revisions already used -------> Return available plan
                                                  with unresolved issues
```

There is one initial plan and at most two revisions. Research runs once initially. Revisions reuse the saved research and review feedback.

## How LangGraph and CrewAI work together

Use separate LangGraph steps for research, itinerary generation, and review so LangGraph can control the revision loop.

Each agent step runs a CrewAI task through a small crew execution. It returns a structured result that is saved in LangGraph state. The next step receives that saved result explicitly as input.

This means the entire process is not hidden inside one sequential crew execution. LangGraph can send work back to the itinerary agent without restarting research.

## LangGraph nodes

| Node | What it does |
| --- | --- |
| `prepare_trip` | Validate requirements; prepare dates, nights, travel legs, and stay periods |
| `research_trip` | Run the research agent with MCP tools and save its findings |
| `create_itinerary` | Run the itinerary agent using requirements, research, and any review feedback |
| `validate_and_price` | Validate the itinerary and calculate the budget using Python |
| `review_itinerary` | Run the review agent and save its decision and issues |
| `finalize_trip` | Produce the response for the interface, including unresolved issues |

After `review_itinerary`, a conditional edge chooses `create_itinerary` or `finalize_trip`. Increment the revision count only when routing back for another attempt.

## Agent roles and handoffs

### Research agent

Inputs: validated user requirements and trip context.

Actions: call MCP tools for relevant weather, transport, accommodation, attractions, and food. Reuse transport and accommodation results across applicable days.

Output: structured findings with IDs, sources, dates, prices and their provenance, and unavailable information.

### Itinerary agent

Inputs: user requirements, saved research, and review feedback when revising.

Actions: organize the complete trip into daily morning, afternoon, and evening schedules. Reference research IDs for factual selections. Revise the previous itinerary when feedback exists.

Output: a structured itinerary. The agent must not invent missing prices or provider information.

### Review agent

Inputs: requirements, research, itinerary, Python validation issues, and budget results.

Actions: assess requirement coverage, use of researched information, obvious schedule conflicts, and whether unavailable information is disclosed.

Output: `APPROVED` or `NEEDS_REVISION`, with specific issues and suggested fixes.

Python validation failures must prevent approval even if the review agent approves. The reviewer evaluates plausibility; it cannot guarantee opening hours or availability absent supporting data.

## MCP server

Build our own MCP server around existing services rather than rewriting their provider integrations.

| MCP tool | Existing implementation |
| --- | --- |
| Weather | `services/weather_service.py` |
| Flight search | `services/flight_service.py` |
| Train estimates | `tools/estimators.py` |
| Hotel search | `services/hotel_service.py` |
| Attractions and food | `services/wikipedia_service.py` |

Use a locally launched stdio MCP server for the initial implementation. Keep connections scoped to research execution and close them reliably afterward. Only the research agent needs MCP tools initially.

Validate tool inputs on the server. Preserve the current restrictions on travel legs, dates, estimate provenance, and unavailable results. Keep API credentials in the server environment, outside agent prompts and returned results.

## Shared LangGraph state

- Validated user requirements.
- Trip dates, travel legs, and stay periods.
- Research findings and source registry.
- Current itinerary.
- Python validation issues.
- Calculated budget and completeness status.
- Review decision and feedback.
- Revision count, starting at zero.
- Tool activity, warnings, and final trip result.

## Proposed files

```text
graph.py                  LangGraph nodes and routing
agents/
  researcher.py           Research agent configuration
  itinerary.py            Itinerary agent configuration
  reviewer.py             Review agent configuration
  tasks.py                Task definitions and execution helpers
mcp_tools/
  server.py               MCP wrappers around existing services
  client.py               CrewAI MCP connection lifecycle
schemas/
  travel.py               Existing request and response models
  research.py             Research findings and source references
  review.py               Review decision and issues
services/                 Existing provider integrations
utils/budget.py           Existing deterministic calculations
tests/                    Workflow and integration checks
```

Keep graph nodes small. Put tool adapters, output parsing, and agent setup in their own modules.

## Implementation steps

1. Inspect current schemas, service contracts, budget logic, and tests. Identify the existing behavior that must remain supported.
2. Verify compatible CrewAI, MCP, and LangGraph dependencies and the configured Groq model's supported integration. Update dependencies and `.env.example` as needed.
3. Define research and review schemas and align the itinerary output with the existing `TripPlan` response.
4. Implement the MCP server wrappers and the connection adapter used by CrewAI.
5. Implement the three agents and their tasks with structured outputs and explicit inputs.
6. Replace the current graph with the agreed nodes, shared state, and bounded revision routing.
7. Adapt the existing budget and reference validation logic to the new research output.
8. Preserve the current API endpoints and response contract where possible. Update interface activity labels to show research, itinerary generation, review, and revision.
9. Update tests and README to describe the implemented architecture and startup process.

## Failure handling

- Invalid requirements: return validation errors before starting agents.
- Provider failure: record unavailable information and continue where useful.
- MCP connection failure: report the failure without generating unsupported research.
- Invalid agent output: record the failure; do not treat malformed output as an approved plan.
- Missing costs: show a partial budget rather than claiming the trip fits the budget.
- Issues after two revisions: return a partial result with remaining issues clearly listed.
- No usable itinerary: return a failed planning result rather than an empty successful plan.

## Verification

- Check each MCP wrapper against its existing service contract.
- Confirm the itinerary agent receives the saved research and user requirements.
- Confirm the reviewer receives the itinerary, research, requirements, and Python checks.
- Test approval on the initial attempt, approval after revision, and termination after two unsuccessful revisions.
- Confirm revisions do not rerun research and include the previous review feedback.
- Check exact day dates, transport and stay reuse, factual references, and budget arithmetic.
- Check unavailable providers, missing costs, invalid model output, and MCP cleanup.
- Run an end-to-end API test with mocked providers and agents, then a configured live smoke check when credentials are available.

## Completion criteria

The user can click Start Planning and receive a researched itinerary produced by CrewAI, checked by Python and a review agent, with LangGraph managing no more than two revisions. Research tools run through our MCP server, and the interface clearly displays missing information and unresolved issues.

## Implementation notes

- Hotel research now uses Makcorps instead of StayingAPI, as requested during implementation.
- The duplicate Streamlit interface and direct LangChain/Groq agent loop have been removed.
- React now displays streamed workflow progress, day cards, travel/stays, review issues, and budget details.
- CrewAI task outputs are validated against Pydantic schemas after JSON generation. This avoids Groq's incompatible forced-tool structured-output conversion.
- A narrow provider compatibility adapter removes unsupported prompt-cache message fields before Groq requests.
- Makcorps city quotes do not document a nightly/stay-total basis. Unconfirmed quote totals are excluded from arithmetic and disclosed to users.
- Following the output review, the interface now uses day-level highlights, sourced places with reasons to visit and practical suggestions, and descriptions of local foods. Time-of-day blocks remain only as legacy response fields.
- Wikipedia results are checked against destination evidence and article type. Generic tourism pages, biographies, films, and unrelated geography are rejected.
- Place/food research is shared across applicable days. Weather stays date-specific. Stable candidate IDs and strict writing schemas reduce unsupported references.
- Writing runs one day per CrewAI task, excluding already-used attractions and preferring different foods. LangGraph still controls the whole trip and review loop.
- Missing provider prices are informational. The planning budget uses editable food, activity, and accommodation allowances, separately labelled from live prices and configured train fares.
- When model wording fails or references cannot be verified, a labelled guide can be built from the verified source pool. A missing AI review is never represented as approval.
