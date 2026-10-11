"""
Evaluation orchestrator and scoring engine for 2MA-Bench.
Coordinates problem generation, model queries, verification, and metric aggregation.
"""

import asyncio
import datetime
import time
import uuid
from typing import Dict, List, Optional, Callable, Any
from pydantic import BaseModel, Field

from ..client.base import BaseLLMClient, ClientConfig, ModelResponse
from ..generators.base import BenchmarkProblem, VerifierResult


class EvaluationConfig(BaseModel):
    """Configuration for an evaluation run."""
    seed: int = 42
    difficulty: int = 1
    dimensions: List[str] = Field(default_factory=lambda: ["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"])
    system_prompt: Optional[str] = Field(
        default="You are an expert frontier reasoning AI. Think carefully step-by-step and strictly adhere to the requested output format.",
        description="Optional system prompt to prepend."
    )


class ProblemEvaluationResult(BaseModel):
    """Result of evaluating a model on a single benchmark problem."""
    problem_id: str
    dimension: str
    dimension_name: str
    title: str
    prompt: str
    model_response: ModelResponse
    verification: VerifierResult


class RunSummary(BaseModel):
    """Aggregated report of an entire 2MA-Bench run."""
    run_id: str
    created_at: str
    model: str
    provider: str
    seed: int
    difficulty: int
    total_problems: int
    passed_count: int
    overall_accuracy: float
    overall_score: float
    dimension_scores: Dict[str, float]
    dimension_passes: Dict[str, bool]
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_latency_ms: float
    average_latency_ms: float
    results: List[ProblemEvaluationResult]


class EvaluationEngine:
    """Core orchestrator executing 2MA-Bench benchmarks."""

    @classmethod
    async def run(
        cls,
        client: BaseLLMClient,
        eval_config: EvaluationConfig,
        run_id: Optional[str] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> RunSummary:
        from ..generators import get_generator, generate_benchmark_suite
        run_id = run_id or f"2ma_{uuid.uuid4().hex[:8]}"
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Procedurally generate problems
        problems = generate_benchmark_suite(
            seed=eval_config.seed,
            difficulty=eval_config.difficulty,
            dimensions=eval_config.dimensions,
        )

        if event_callback:
            await event_callback({
                "type": "run_started",
                "run_id": run_id,
                "total_problems": len(problems),
                "model": client.config.model,
                "seed": eval_config.seed,
                "difficulty": eval_config.difficulty,
            })

        results: List[ProblemEvaluationResult] = []
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_latency = 0.0

        for idx, problem in enumerate(problems):
            if event_callback:
                await event_callback({
                    "type": "problem_started",
                    "run_id": run_id,
                    "index": idx + 1,
                    "total": len(problems),
                    "problem_id": problem.id,
                    "dimension": problem.dimension,
                    "dimension_name": problem.dimension_name,
                    "title": problem.title,
                })

            # Execute generation
            model_response = await client.generate(
                prompt=problem.prompt,
                system_prompt=eval_config.system_prompt,
            )

            total_tokens += model_response.total_tokens
            total_prompt_tokens += model_response.prompt_tokens
            total_completion_tokens += model_response.completion_tokens
            total_latency += model_response.latency_ms

            # Verify response deterministically
            generator = get_generator(problem.dimension)
            verification = await generator.verify(problem, model_response.content)

            eval_res = ProblemEvaluationResult(
                problem_id=problem.id,
                dimension=problem.dimension,
                dimension_name=problem.dimension_name,
                title=problem.title,
                prompt=problem.prompt,
                model_response=model_response,
                verification=verification,
            )
            results.append(eval_res)

            if event_callback:
                await event_callback({
                    "type": "problem_completed",
                    "run_id": run_id,
                    "index": idx + 1,
                    "total": len(problems),
                    "problem_id": problem.id,
                    "dimension": problem.dimension,
                    "passed": verification.passed,
                    "score": verification.score,
                    "failure_reason": verification.failure_reason,
                    "tokens": model_response.total_tokens,
                    "latency_ms": model_response.latency_ms,
                })

        # Calculate metrics
        passed_count = sum(1 for r in results if r.verification.passed)
        total_count = len(results)
        overall_accuracy = round((passed_count / total_count) * 100, 2) if total_count > 0 else 0.0

        # Dimension scores
        dim_scores: Dict[str, float] = {}
        dim_passes: Dict[str, bool] = {}
        for r in results:
            dim_scores[r.dimension] = max(0.0, r.verification.score * 100)
            dim_passes[r.dimension] = r.verification.passed

        total_score_sum = sum(max(0.0, r.verification.score) for r in results)
        overall_score = round((total_score_sum / total_count) * 100, 2) if total_count > 0 else 0.0
        avg_latency = round(total_latency / total_count, 2) if total_count > 0 else 0.0

        summary = RunSummary(
            run_id=run_id,
            created_at=created_at,
            model=client.config.model,
            provider=client.config.provider,
            seed=eval_config.seed,
            difficulty=eval_config.difficulty,
            total_problems=total_count,
            passed_count=passed_count,
            overall_accuracy=overall_accuracy,
            overall_score=overall_score,
            dimension_scores=dim_scores,
            dimension_passes=dim_passes,
            total_tokens=total_tokens,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_latency_ms=round(total_latency, 2),
            average_latency_ms=avg_latency,
            results=results,
        )

        if event_callback:
            await event_callback({
                "type": "run_completed",
                "run_id": run_id,
                "summary": summary.model_dump(),
            })

        return summary
