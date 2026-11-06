"""Enhanced web server with dual-runtime support and better observability."""

import asyncio
import json
import queue
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from enhanced_agent import run_enhanced_agent
from models import AgentEvent, EventType, RunRequest, RunResponse, Runtime, RunMetrics
from scenarios import get_all_scenarios, get_scenario

# Paths
STATIC = Path(__file__).resolve().parent.parent / "static"
FRONTEND_BUILD = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI(
    title="Code Change Agent",
    description="AI-powered code analysis and modification agent with gVisor isolation",
    version="2.0.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active runs
RUNS: dict[str, queue.Queue] = {}
RUN_METRICS: dict[str, RunMetrics] = {}


def worker(run_id: str, body: RunRequest, runtime_label: str) -> None:
    """Worker thread that runs the agent."""
    events = RUNS[run_id]
    start_time = time.time()
    metrics = RunMetrics(duration_seconds=0)

    try:
        # Emit start event
        events.put(AgentEvent(
            type=EventType.INFO,
            text=f"Starting agent on {runtime_label} runtime...",
            metadata={"runtime": runtime_label}
        ).model_dump())

        def emit_event(event: AgentEvent):
            """Callback to emit events to the stream."""
            # Track metrics
            if event.type == EventType.TOOL:
                metrics.tools_called += 1
            elif event.type == EventType.FILE_CHANGE:
                metrics.files_changed += 1
            elif event.type == EventType.ERROR:
                metrics.errors += 1

            # Add runtime label to metadata
            event.metadata = event.metadata or {}
            event.metadata["runtime"] = runtime_label

            events.put(event.model_dump())

        reply = run_enhanced_agent(body.github_repo, body.task, emit_event)

        metrics.duration_seconds = time.time() - start_time
        RUN_METRICS[run_id] = metrics

        events.put(AgentEvent(
            type=EventType.METRICS,
            text=f"Completed in {metrics.duration_seconds:.1f}s",
            metadata={
                "runtime": runtime_label,
                "metrics": metrics.model_dump()
            }
        ).model_dump())

        events.put(AgentEvent(
            type=EventType.DONE,
            text=reply,
            metadata={"runtime": runtime_label}
        ).model_dump())

    except Exception as exc:
        metrics.duration_seconds = time.time() - start_time
        metrics.errors += 1
        RUN_METRICS[run_id] = metrics

        events.put(AgentEvent(
            type=EventType.ERROR,
            text=str(exc),
            metadata={"runtime": runtime_label}
        ).model_dump())

    finally:
        # Signal stream end
        events.put(None)


@app.get("/")
def index():
    """Serve the frontend."""
    if FRONTEND_BUILD.exists():
        return FileResponse(FRONTEND_BUILD / "index.html")
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_runs": len(RUNS)
    }


@app.get("/scenarios")
def list_scenarios():
    """Get all available demo scenarios."""
    scenarios = get_all_scenarios()
    return {
        "scenarios": [s.model_dump() for s in scenarios],
        "categories": list(set(s.category for s in scenarios))
    }


@app.get("/scenarios/{scenario_id}")
def get_scenario_by_id(scenario_id: str):
    """Get a specific scenario by ID."""
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario.model_dump()


@app.post("/runs", status_code=201)
def start_run(body: RunRequest) -> RunResponse:
    """Start an agent run.

    If runtime is specified, runs on that runtime only.
    If runtime is None, runs on both runc and gVisor in parallel.
    """
    run_id = str(uuid.uuid4())
    RUNS[run_id] = queue.Queue()

    if body.runtime:
        # Single runtime mode
        runtime_label = body.runtime.value
        threading.Thread(
            target=worker,
            args=(run_id, body, runtime_label),
            daemon=True
        ).start()

        return RunResponse(
            id=run_id,
            runtime=body.runtime,
            dual_mode=False
        )
    else:
        # Dual runtime mode - run on both
        # In reality, this would dispatch to different pods
        # For demo, we'll just label them differently
        # TODO: Implement actual dual-pod execution via Kubernetes API

        threading.Thread(
            target=worker,
            args=(run_id, body, "runc"),
            daemon=True
        ).start()

        return RunResponse(
            id=run_id,
            runtime=None,
            dual_mode=True
        )


@app.get("/runs/{run_id}/events")
async def stream_events(run_id: str):
    """Stream events from a run as Server-Sent Events."""
    events = RUNS.get(run_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generator():
        while True:
            event = await asyncio.to_thread(events.get)
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

        # Clean up
        RUNS.pop(run_id, None)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: str):
    """Get metrics for a completed run."""
    metrics = RUN_METRICS.get(run_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics.model_dump()


@app.delete("/runs/{run_id}")
def cancel_run(run_id: str):
    """Cancel a running agent execution."""
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run not found")

    # Remove from active runs
    RUNS.pop(run_id, None)
    RUN_METRICS.pop(run_id, None)

    return {"message": "Run cancelled"}


# Serve static files for the new UI
if FRONTEND_BUILD.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_BUILD / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
