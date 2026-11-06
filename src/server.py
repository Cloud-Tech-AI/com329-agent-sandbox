"""Small web server: start an agent run and stream its steps to the page."""

import asyncio
import json
import queue
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from agent import run_agent

STATIC = Path(__file__).resolve().parent.parent / "static"  # static/ sits next to src/
RUNS: dict[str, queue.Queue] = {}

app = FastAPI(title="Code Change Agent")


class RunIn(BaseModel):
    github_repo: str
    task: str


def worker(run_id: str, body: RunIn) -> None:
    events = RUNS[run_id]
    try:
        reply = run_agent(body.github_repo, body.task, events.put)
        events.put({"type": "done", "text": reply})
    except Exception as exc:
        events.put({"type": "error", "text": str(exc)})
    finally:
        events.put(None)  # tells the event stream to close


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/runs", status_code=201)
def start_run(body: RunIn):
    run_id = str(uuid.uuid4())
    RUNS[run_id] = queue.Queue()
    threading.Thread(target=worker, args=(run_id, body), daemon=True).start()
    return {"id": run_id}


@app.get("/runs/{run_id}/events")
async def stream_events(run_id: str):
    events = RUNS.get(run_id)
    if events is None:
        return {"detail": "Run not found"}

    async def generator():
        while True:
            event = await asyncio.to_thread(events.get)
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
        RUNS.pop(run_id, None)

    return StreamingResponse(generator(), media_type="text/event-stream")
