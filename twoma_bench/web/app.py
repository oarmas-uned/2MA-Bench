"""
FastAPI Web Application & Real-Time SSE Server for 2MA-Bench.
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..client.base import ClientConfig
from ..client import create_client, MockClient
from ..generators import list_dimensions, get_generator
from ..evaluator.engine import EvaluationConfig, EvaluationEngine, RunSummary

app = FastAPI(
    title="2M AI Bench (2MA-Bench)",
    description="The Frontier Procedural Hardness AI Benchmark Dashboard",
    version="0.1.0",
)

# In-memory run store and event queues for SSE
_RUNS: Dict[str, RunSummary] = {}
_EVENT_QUEUES: Dict[str, asyncio.Queue] = {}

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)


class TestConnectionRequest(BaseModel):
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"


class LaunchRunRequest(BaseModel):
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    seed: int = 42
    difficulty: int = 1
    dimensions: list[str] = Field(default_factory=lambda: ["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"])


@app.get("/api/dimensions")
async def api_dimensions():
    return list_dimensions()


@app.post("/api/test-connection")
async def api_test_connection(req: TestConnectionRequest):
    config = ClientConfig(
        provider=req.provider,
        base_url=req.base_url,
        api_key=req.api_key,
        model=req.model,
    )
    client = create_client(config)
    success, msg = await client.test_connection()
    return {"success": success, "message": msg}


@app.post("/api/run")
async def api_launch_run(req: LaunchRunRequest):
    config = ClientConfig(
        provider=req.provider,
        base_url=req.base_url,
        api_key=req.api_key,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    eval_config = EvaluationConfig(
        seed=req.seed,
        difficulty=req.difficulty,
        dimensions=req.dimensions,
    )

    client = create_client(config)
    
    # If mock provider and oracle needed, wire oracle generator
    if req.provider == "mock":
        def oracle_solver(prompt: str) -> str:
            # Simple oracle responder for testing
            for dim in req.dimensions:
                gen = get_generator(dim)
                prob = gen.generate(req.seed, req.difficulty)
                if prob.prompt[:50] in prompt[:50]:
                    return gen.get_oracle_solution(prob)
            return "{\"solvable\": false}"
        client = MockClient(config, oracle_solver=oracle_solver, mock_mode="oracle")

    # Generate a run ticket
    import uuid
    run_id = f"2ma_{uuid.uuid4().hex[:8]}"
    queue = asyncio.Queue()
    _EVENT_QUEUES[run_id] = queue

    async def event_listener(event: Dict[str, Any]):
        event["run_id"] = run_id
        await queue.put(event)

    async def run_worker():
        try:
            summary = await EvaluationEngine.run(client, eval_config, run_id=run_id, event_callback=event_listener)
            _RUNS[run_id] = summary
        except Exception as e:
            await queue.put({"type": "run_error", "run_id": run_id, "error": str(e)})

    # Launch task in background
    asyncio.create_task(run_worker())

    return {"run_id": run_id, "status": "started"}


@app.get("/api/stream/{run_id}")
async def api_stream_events(run_id: str):
    if run_id not in _EVENT_QUEUES:
        raise HTTPException(status_code=404, detail="Run not found")

    queue = _EVENT_QUEUES[run_id]

    async def event_generator():
        while True:
            event = await queue.get()
            data_str = json.dumps(event)
            yield f"data: {data_str}\n\n"
            if event.get("type") in ("run_completed", "run_error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/results/{run_id}")
async def api_get_results(run_id: str):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run results not ready or run not found")
    return _RUNS[run_id]


@app.get("/api/export/{run_id}/markdown", response_class=PlainTextResponse)
async def api_export_markdown(run_id: str):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    
    summary = _RUNS[run_id]
    lines = [
        f"# 2M AI Bench (2MA-Bench) Evaluation Report",
        f"**Run ID**: `{summary.run_id}`  ",
        f"**Date**: {summary.created_at}  ",
        f"**Model**: `{summary.model}` ({summary.provider})  ",
        f"**Seed**: `{summary.seed}` | **Difficulty**: `{summary.difficulty}`  ",
        f"\n---\n",
        f"## Executive Scorecard",
        f"- **Overall Hardness Score**: **{summary.overall_score}%**",
        f"- **Pass Rate**: {summary.passed_count} / {summary.total_problems} ({summary.overall_accuracy}%)",
        f"- **Total Tokens Consumed**: {summary.total_tokens:,}",
        f"- **Average Latency**: {summary.average_latency_ms} ms",
        f"\n### Dimension Capability Breakdown",
        f"| Dimension | Hardness Score | Status |",
        f"| :--- | :--- | :--- |",
    ]

    for dim, score in summary.dimension_scores.items():
        status = "PASSED" if summary.dimension_passes.get(dim) else "FAILED"
        lines.append(f"| `{dim}` | {score}% | {status} |")

    lines.append("\n### Detailed Challenge Traces\n")
    for r in summary.results:
        lines.append(f"#### {r.dimension_name}: {r.title}")
        lines.append(f"- **Status**: {'PASSED' if r.verification.passed else 'FAILED'}")
        lines.append(f"- **Score**: {round(r.verification.score * 100, 1)}%")
        lines.append(f"- **Latency**: {round(r.model_response.latency_ms, 1)} ms | **Tokens**: {r.model_response.total_tokens}")
        if r.verification.failure_reason:
            lines.append(f"- **Failure Analysis**: `{r.verification.failure_reason}`")
        lines.append("")

    return "\n".join(lines)


# Mount static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>2M AI Bench Dashboard Loading...</h1>"


def main():
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser(description="2MA-Bench Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8088, help="Port (never 8000)")
    args = parser.parse_args()

    print(f"Starting 2M AI Bench (2MA-Bench) server at http://{args.host}:{args.port}")
    uvicorn.run("twoma_bench.web.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
