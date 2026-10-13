"""
Automated unit tests for EvaluationEngine concurrency, multi-sampling, and telemetry.
"""

import pytest
from twoma_bench.client.base import ClientConfig
from twoma_bench.client.mock_client import MockClient
from twoma_bench.generators import get_generator, generate_benchmark_suite
from twoma_bench.evaluator.engine import EvaluationConfig, EvaluationEngine


@pytest.mark.asyncio
async def test_engine_multisample_concurrency():
    config = ClientConfig(provider="mock", model="mock-oracle")
    seed = 42
    difficulty = 1
    samples_per_dim = 2

    # Wire oracle solver for all problems
    problems = generate_benchmark_suite(
        seed=seed,
        difficulty=difficulty,
        samples_per_dimension=samples_per_dim,
    )
    assert len(problems) == 10

    def oracle_solver(prompt: str) -> str:
        for p in problems:
            if p.prompt.strip() == prompt.strip():
                return get_generator(p.dimension).get_oracle_solution(p)
        return '{"solvable": false}'

    client = MockClient(config, oracle_solver=oracle_solver, mock_mode="oracle")

    events = []

    async def callback(ev):
        events.append(ev)

    eval_config = EvaluationConfig(
        seed=seed,
        difficulty=difficulty,
        samples_per_dimension=samples_per_dim,
        max_concurrency=3,
    )

    summary = await EvaluationEngine.run(
        client, eval_config, run_id="test_run_concur", event_callback=callback
    )

    assert summary.total_problems == 10
    assert summary.passed_count == 10
    assert summary.overall_score == 100.0
    assert summary.overall_accuracy == 100.0
    assert len(events) >= 12  # run_started, 10 started, 10 completed, run_completed
    assert summary.failure_taxonomy.get("PASSED") == 10
