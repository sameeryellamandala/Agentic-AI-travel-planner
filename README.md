# Voyage Travel Planner

A React travel planner backed by LangGraph, three CrewAI agent roles, and a local MCP server.

## How planning works

1. LangGraph validates the request and prepares dates, journeys, and stay periods.
2. The research agent calls our MCP tools for weather, transport, hotels, attractions, and food.
3. Actual tool responses are saved in a research ledger; the agent cannot substitute invented findings.
4. The itinerary agent turns sourced candidate IDs into a day-by-day guide: highlights, places worth visiting, why they are special, suggested activities, and local foods to try. Days are not split into morning, afternoon, and evening slots.
5. Python validates dates and references and calculates the known budget.
6. The review agent checks the plan. LangGraph routes content problems back for at most two revisions. Missing provider prices are informational and cannot cause a revision loop by themselves.
7. The API returns the available plan with missing information and unresolved issues clearly marked.

Each role runs a CrewAI task in its own execution boundary. LangGraph passes structured state between them and controls revisions without rerunning research.

Within itinerary generation, the writer handles one day per task and carries already-used attractions and foods forward. This keeps prompts small and prevents the same attraction being scheduled again. GPT-OSS writing tasks use a strict JSON schema with the actual allowed candidate IDs. `GROQ_WRITER_MODEL` and `GROQ_REVIEW_MODEL` can be configured separately from the research model.

If model wording fails or contains invalid references, a clearly labelled source guide is built from the verified destination pool. It still includes daily highlights, practical suggestions, and dishes; it does not invent missing attractions, prices, or a successful AI review.

## Run locally

Use Python 3.10–3.13 and Node.js 20.19+ or 22.12+.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Fill in `backend/.env` locally. `GROQ_API_KEY` is required for agents. Configure `GROQ_MODEL` with a tool-capable model available to your account. Weather, flights, and hotels use `OPENWEATHER_API_KEY`, `IGNAV_API_KEY`, and `MAKCORPS_API_KEY`. Wikipedia does not require a key. `PEXELS_API_KEY` is optional and provides the inspiration photo; otherwise an illustrated landscape appears.

Do not overwrite an existing `backend/.env` when updating the project. Credentials stay on the backend and `backend/.env` is ignored by Git.

Start the backend:

```powershell
.venv/Scripts/python -m uvicorn --app-dir backend api:app --host 127.0.0.1 --port 8080
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend. The MCP subprocess starts and stops automatically during research; no separate server command is required.

## API

- `POST /api/plan` and `POST /plan-trip`: complete structured trip response.
- `POST /api/plan/stream`: newline-delimited JSON stage updates followed by the trip result.
- `GET /api/inspiration`: optional photo and photographer attribution; no API key is returned.
- `/docs`: interactive backend API documentation.

The React screen shows real completed-step updates, review and revision activity, daily highlights, travel/stays, and a compact planning budget. Spending allowances can be edited in the form. Plans can be downloaded as JSON.

## Data limits

- Train requests require the user’s one-way railway distance. Fares are configured estimates, not live ticket availability. Only outward and return intercity legs are priced.
- Weather uses the precise day/location. Dates outside the provider forecast window may be unavailable.
- Makcorps uses `/mapping` to resolve a city and `/city` for dated vendor quotes. Quotes with an unspecified nightly/stay-total basis are displayed separately and excluded from budget totals. Star preferences cannot be verified when the provider omits star classification. One room is requested for the specified adults; providers may reject large groups.
- Wikipedia research starts from the destination article and its attraction links, checks local geography or nearby coordinates, and rejects people, films, and broad tourism articles. Food research uses dishes listed in the body of the destination's cuisine article, excluding unrelated navigation-template links.
- Wikipedia supplies background knowledge, not opening hours, restaurant bookings, current prices, or live availability.
- The planning total combines known costs with user-editable allowances: initially INR 600 per person/day for food, INR 300 per person/day for activities, and INR 2,500 per room/night for stays without confirmed prices. These are planning choices, not factual price claims or Wikipedia prices. Actual quotes and allowances remain separate in the response.
- Missing hotel data does not block the itinerary or trigger revisions by itself. The budget shows the hotel allowance and makes clear that accommodation is not booked or confirmed.
- The reviewer assesses plausibility; it does not guarantee route optimization or real-world availability.
- Up to three itinerary versions are generated: the initial plan plus two revisions. Provider/model failure returns a partial or failed result, never an unreviewed success.
- `random_seed`, `randomization`, and legacy morning/afternoon/evening fields remain in the API for compatibility. The current agent and interface use day-level highlights and visits instead.

## Project layout

```text
backend/
  agents/              CrewAI roles and tasks
  mcp_tools/           MCP server and client
  schemas/             Request and response models
  services/            Weather, hotels, flights, and Wikipedia
  tools/               Train fare estimates
  utils/               Trip context, validation, and budget logic
  config/              Fare configuration
  tests/               Backend tests
  api.py               FastAPI endpoints
  graph.py             LangGraph workflow
  requirements.txt     Python dependencies
  pytest.ini           Test configuration
  .env.example         Blank API key template
frontend/
  src/                 React screens and styles
  public/              Public assets
  package.json         Frontend dependencies and commands
docs/                  Implementation plan, verification, and previews
README.md              Setup instructions
.gitignore             Local files excluded from Git
```

The duplicate Streamlit UI and direct LangChain/Groq orchestration were removed. LangGraph still installs its own LangChain Core dependency.

## Checks

```powershell
.venv/Scripts/python -m pytest backend
.venv/Scripts/python -m pip check
cd frontend
npm run build
npm run lint
npm audit
```

Live provider tests are opt-in: set `RUN_LIVE_TESTS=1` and run `.venv/Scripts/python -m pytest backend -m integration`. They consume provider requests and require working credentials.

Provider references: [CrewAI tasks](https://docs.crewai.com/en/concepts/tasks), [MCP stdio](https://modelcontextprotocol.io/docs/develop/build-server), [Makcorps documentation](https://www.makcorps.com/documentation/).
