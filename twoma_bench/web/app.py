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

from ..client.base import ClientConfig, PROVIDER_PRESETS
from ..client import create_client, MockClient
from ..generators import list_dimensions, get_generator, generate_benchmark_suite
from ..evaluator.engine import EvaluationConfig, EvaluationEngine, RunSummary
from ..evaluator.exporter import BenchmarkExporter

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="2M AI Bench (2MA-Bench)",
    description="The Frontier Procedural Hardness AI Benchmark Dashboard",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    max_tokens: int = 8192
    seed: int = 42
    difficulty: int = 1
    samples_per_dimension: int = 1
    max_concurrency: int = 2
    dimensions: list[str] = Field(default_factory=lambda: ["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"])


@app.get("/api/dimensions")
async def api_dimensions():
    return list_dimensions()


@app.get("/api/presets")
async def api_presets():
    return PROVIDER_PRESETS


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
        samples_per_dimension=req.samples_per_dimension,
        max_concurrency=req.max_concurrency,
        dimensions=req.dimensions,
    )

    client = create_client(config)
    
    # If mock provider and oracle needed, wire oracle generator with exact prompt matching
    if req.provider == "mock":
        generated_problems = generate_benchmark_suite(
            seed=req.seed,
            difficulty=req.difficulty,
            dimensions=req.dimensions,
            samples_per_dimension=req.samples_per_dimension,
        )

        def oracle_solver(prompt: str) -> str:
            for prob in generated_problems:
                if prob.prompt.strip() == prompt.strip():
                    gen = get_generator(prob.dimension)
                    return gen.get_oracle_solution(prob)
            return '{"solvable": false}'

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
    return BenchmarkExporter.to_markdown(summary)


@app.get("/api/export/{run_id}/csv", response_class=PlainTextResponse)
async def api_export_csv(run_id: str):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    summary = _RUNS[run_id]
    csv_content = BenchmarkExporter.to_csv(summary)
    return PlainTextResponse(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={run_id}_report.csv"},
    )


@app.get("/api/runs")
async def api_list_runs():
    """Return summary list of all completed runs for history and comparison."""
    return [
        {
            "run_id": s.run_id,
            "created_at": s.created_at,
            "model": s.model,
            "provider": s.provider,
            "overall_score": s.overall_score,
            "passed_count": s.passed_count,
            "total_problems": s.total_problems,
            "average_latency_ms": s.average_latency_ms,
            "total_tokens": s.total_tokens,
            "dimension_scores": s.dimension_scores,
        }
        for s in _RUNS.values()
    ]


@app.get("/api/compare")
async def api_compare_runs(run_a: str, run_b: str):
    """Compare two completed runs side-by-side."""
    if run_a not in _RUNS or run_b not in _RUNS:
        raise HTTPException(status_code=404, detail="One or both runs not found")
    
    a = _RUNS[run_a]
    b = _RUNS[run_b]

    dimensions = list(set(list(a.dimension_scores.keys()) + list(b.dimension_scores.keys())))
    dim_comparison = []
    for d in dimensions:
        score_a = a.dimension_scores.get(d, 0.0)
        score_b = b.dimension_scores.get(d, 0.0)
        dim_comparison.append({
            "dimension": d,
            "model_a_score": score_a,
            "model_b_score": score_b,
            "diff": round(score_b - score_a, 1),
        })

    return {
        "run_a": {
            "run_id": a.run_id,
            "model": a.model,
            "provider": a.provider,
            "overall_score": a.overall_score,
            "total_tokens": a.total_tokens,
            "average_latency_ms": a.average_latency_ms,
        },
        "run_b": {
            "run_id": b.run_id,
            "model": b.model,
            "provider": b.provider,
            "overall_score": b.overall_score,
            "total_tokens": b.total_tokens,
            "average_latency_ms": b.average_latency_ms,
        },
        "score_diff": round(b.overall_score - a.overall_score, 1),
        "dimensions": dim_comparison,
    }


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
