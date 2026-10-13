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


def classify_failure(v: VerifierResult) -> str:
    """Categorizes the failure reason into an analytical taxonomy bucket."""
    if v.passed:
        return "PASSED"
    if v.details and v.details.get("hallucination_penalty"):
        return "EPISTEMIC_HALLUCINATION"
    if v.details and v.details.get("sandbox_timed_out"):
        return "TIMEOUT"
    if v.failure_reason:
        reason = v.failure_reason.lower()
        if "json" in reason or "format" in reason or "extract" in reason or "code block" in reason:
            return "FORMAT_SYNTAX_ERROR"
        if "deadlock" in reason or "timeout" in reason:
            return "DEADLOCK_TIMEOUT"
        if "error" in reason or "exception" in reason or "traceback" in reason:
            return "EXECUTION_EXCEPTION"
    return "INCORRECT_LOGIC"


DEFAULT_SYSTEM_PROMPT = (
    "You are an expert frontier reasoning AI evaluated by 2MA-Bench (Zero Memorization Procedural Benchmark).\n"
    "Follow these strict calibration guidelines:\n"
    "1. Adhere rigorously to the requested output format (enclosed in ```json or ```python blocks).\n"
    "2. For Virtual Register Machine emulation, trace 8-bit arithmetic modulo 256 cycle-by-cycle without assuming standard 32/64-bit overflow.\n"
    "3. For Concurrency Repair, output the entire corrected class inside ```python and ``` without omitting helper methods or imports.\n"
    "4. For Epistemic Impossibility challenges, prove mathematical contradictions when problems are unsolvable; never fabricate or hallucinate variables for contradictory constraints."
)


class EvaluationConfig(BaseModel):
    """Configuration for an evaluation run."""
    seed: int = 42
    difficulty: int = 1
    samples_per_dimension: int = 1
    max_concurrency: int = 2
    dimensions: List[str] = Field(
        default_factory=lambda: ["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"]
    )
    system_prompt: Optional[str] = Field(
        default=DEFAULT_SYSTEM_PROMPT,
        description="Calibrated system instructions guiding evaluated AI models."
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
    failure_type: str = "PASSED"


class RunSummary(BaseModel):
    """Aggregated report of an entire 2MA-Bench run."""
    run_id: str
    created_at: str
    model: str
    provider: str
    seed: int
    difficulty: int
    samples_per_dimension: int = 1
    total_problems: int
    passed_count: int
    overall_accuracy: float
    overall_score: float
    dimension_scores: Dict[str, float]
    dimension_passes: Dict[str, bool]
    failure_taxonomy: Dict[str, int] = Field(default_factory=dict)
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_latency_ms: float
    average_latency_ms: float
    results: List[ProblemEvaluationResult]


class EvaluationEngine:
    """Core orchestrator executing 2MA-Bench benchmarks with concurrency and telemetry."""

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

        # Procedurally generate problems with multi-sample support
        problems = generate_benchmark_suite(
            seed=eval_config.seed,
            difficulty=eval_config.difficulty,
            dimensions=eval_config.dimensions,
            samples_per_dimension=eval_config.samples_per_dimension,
        )

        if event_callback:
            await event_callback({
                "type": "run_started",
                "run_id": run_id,
                "total_problems": len(problems),
                "model": client.config.model,
                "seed": eval_config.seed,
                "difficulty": eval_config.difficulty,
                "samples_per_dimension": eval_config.samples_per_dimension,
                "concurrency": eval_config.max_concurrency,
            })

        semaphore = asyncio.Semaphore(max(1, eval_config.max_concurrency))
        lock = asyncio.Lock()

        async def eval_single_problem(idx: int, problem: BenchmarkProblem) -> ProblemEvaluationResult:
            if event_callback:
                async with lock:
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

            async with semaphore:
                model_response = await client.generate(
                    prompt=problem.prompt,
                    system_prompt=eval_config.system_prompt,
                )

                generator = get_generator(problem.dimension)
                verification = await generator.verify(problem, model_response.content)
                failure_type = classify_failure(verification)

            eval_res = ProblemEvaluationResult(
                problem_id=problem.id,
                dimension=problem.dimension,
                dimension_name=problem.dimension_name,
                title=problem.title,
                prompt=problem.prompt,
                model_response=model_response,
                verification=verification,
                failure_type=failure_type,
            )

            if event_callback:
                async with lock:
                    await event_callback({
                        "type": "problem_completed",
                        "run_id": run_id,
                        "index": idx + 1,
                        "total": len(problems),
                        "problem_id": problem.id,
                        "dimension": problem.dimension,
                        "passed": verification.passed,
                        "score": verification.score,
                        "failure_type": failure_type,
                        "failure_reason": verification.failure_reason,
                        "tokens": model_response.total_tokens,
                        "latency_ms": model_response.latency_ms,
                    })

            return eval_res

        # Execute all problems concurrently according to semaphore
        tasks = [eval_single_problem(idx, prob) for idx, prob in enumerate(problems)]
        results: List[ProblemEvaluationResult] = await asyncio.gather(*tasks)

        # Calculate metrics
        passed_count = sum(1 for r in results if r.verification.passed)
        total_count = len(results)
        overall_accuracy = round((passed_count / total_count) * 100, 2) if total_count > 0 else 0.0

        total_tokens = sum(r.model_response.total_tokens for r in results)
        total_prompt_tokens = sum(r.model_response.prompt_tokens for r in results)
        total_completion_tokens = sum(r.model_response.completion_tokens for r in results)
        total_latency = sum(r.model_response.latency_ms for r in results)

        # Dimension scores: average score per dimension across samples
        dim_scores_sum: Dict[str, float] = {}
        dim_counts: Dict[str, int] = {}
        dim_all_passed: Dict[str, bool] = {}

        for r in results:
            d = r.dimension
            dim_scores_sum[d] = dim_scores_sum.get(d, 0.0) + max(0.0, r.verification.score)
            dim_counts[d] = dim_counts.get(d, 0) + 1
            if d not in dim_all_passed:
                dim_all_passed[d] = True
            if not r.verification.passed:
                dim_all_passed[d] = False

        dim_scores: Dict[str, float] = {
            d: round((dim_scores_sum[d] / dim_counts[d]) * 100, 2)
            for d in dim_scores_sum
        }

        # Failure taxonomy breakdown
        failure_taxonomy: Dict[str, int] = {}
        for r in results:
            ft = r.failure_type
            failure_taxonomy[ft] = failure_taxonomy.get(ft, 0) + 1

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
            samples_per_dimension=eval_config.samples_per_dimension,
            total_problems=total_count,
            passed_count=passed_count,
            overall_accuracy=overall_accuracy,
            overall_score=overall_score,
            dimension_scores=dim_scores,
            dimension_passes=dim_all_passed,
            failure_taxonomy=failure_taxonomy,
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
