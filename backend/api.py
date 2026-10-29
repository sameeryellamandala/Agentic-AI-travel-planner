"""FastAPI entry point for the existing Travel Planner."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import os
from functools import lru_cache
import requests
from graph import graph
from schemas.travel import TravelRequest, APIResponse

app = FastAPI(title="Voyage Travel Planner", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/inspiration")
@lru_cache(maxsize=1)
def inspiration():
    if not os.getenv("PEXELS_API_KEY"):
        return {}
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            params={
                "query": "coastal landscape",
                "orientation": "landscape",
                "per_page": 1,
            },
            headers={"Authorization": os.environ["PEXELS_API_KEY"]},
            timeout=8,
        )
        response.raise_for_status()
        photo = response.json()["photos"][0]
        return {
            "url": photo["src"]["large2x"],
            "photographer": photo["photographer"],
            "photographer_url": photo["photographer_url"],
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return {}


@app.post("/api/plan/stream")
def stream_plan(request: TravelRequest):
    def events():
        try:
            yield json.dumps({"type": "stage", "stage": "prepare_trip"}) + "\n"
            for update in graph.stream(
                {"user_requirements": request.model_dump(mode="json")},
                config={"recursion_limit": 40},
            ):
                for node, values in update.items():
                    if node == "finalize_trip":
                        yield (
                            json.dumps({"type": "result", "data": values["trip_plan"]})
                            + "\n"
                        )
                    else:
                        yield (
                            json.dumps(
                                {
                                    "type": "stage",
                                    "completed": node,
                                    "revision_count": values.get("revision_count"),
                                }
                            )
                            + "\n"
                        )
        except Exception:
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "message": "Planning could not finish. Check the backend configuration and try again.",
                    }
                )
                + "\n"
            )

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def root():
    return {"message": "Travel Planner running; API documentation at /docs"}


@app.post("/plan-trip", response_model=APIResponse)
@app.post("/api/plan", response_model=APIResponse)
def plan_trip(request: TravelRequest):
    try:
        result = graph.invoke(
            {"user_requirements": request.model_dump(mode="json")},
            config={"recursion_limit": 1000},
        )
        return {"status": "success", "data": result["trip_plan"]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Planning failed; check backend logs and configuration",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8080)
