"""
Automated unit tests for 2MA-Bench procedural generators and deterministic verifiers.
"""

import pytest
from twoma_bench.generators import (
    ConstraintSatisfactionGenerator,
    StateMachineGenerator,
    CounterfactualGenerator,
    ConcurrencyGenerator,
    EpistemicTrapGenerator,
    generate_benchmark_suite,
)


@pytest.mark.asyncio
async def test_constraint_sat_generator():
    gen = ConstraintSatisfactionGenerator()
    for seed in [10, 42, 99]:
        prob = gen.generate(seed=seed, difficulty=1)
        assert prob.dimension == "smt_logic"
        assert len(prob.ground_truth) >= 5

        # Oracle solution must pass verification
        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True
        assert res.score == 1.0

        # Wrong solution must fail
        wrong = "```json\n{\"assignment\": {\"invalid\": 999}}\n```"
        wrong_res = await gen.verify(prob, wrong)
        assert wrong_res.passed is False


@pytest.mark.asyncio
async def test_state_machine_generator():
    gen = StateMachineGenerator()
    for seed in [7, 42, 123]:
        prob = gen.generate(seed=seed, difficulty=1)
        assert prob.dimension == "vm_emulation"
        assert "R0" in prob.ground_truth

        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True
        assert res.score == 1.0


@pytest.mark.asyncio
async def test_counterfactual_generator():
    gen = CounterfactualGenerator()
    for seed in [15, 42, 888]:
        prob = gen.generate(seed=seed, difficulty=1)
        assert prob.dimension == "counterfactual"
        assert "Flux" in prob.ground_truth

        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True
        assert res.score == 1.0


@pytest.mark.asyncio
async def test_concurrency_generator():
    gen = ConcurrencyGenerator()
    for seed in [21, 42]:
        prob = gen.generate(seed=seed, difficulty=1)
        assert prob.dimension == "concurrency"
        assert len(prob.metadata["class_name"]) > 0

        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True
        assert res.score == 1.0

        # Buggy code should fail stress test
        buggy_res = await gen.verify(prob, f"```python\n{prob.metadata['test_harness']}\n```")
        assert buggy_res.passed is False


@pytest.mark.asyncio
async def test_epistemic_trap_generator():
    gen = EpistemicTrapGenerator()
    for seed in [3, 42, 105, 777]:
        prob = gen.generate(seed=seed, difficulty=1)
        assert prob.dimension == "epistemic"
        assert "solvable" in prob.ground_truth

        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True

        # Hallucination test on impossible problems
        if prob.is_impossible:
            hallucinated = "```json\n{\"solvable\": true, \"x\": 100, \"y\": 200}\n```"
            h_res = await gen.verify(prob, hallucinated)
            assert h_res.passed is False
            assert h_res.score == -1.0  # Penalized!


def test_suite_generation():
    suite = generate_benchmark_suite(seed=42, difficulty=1)
    assert len(suite) == 5
    dimensions = {p.dimension for p in suite}
    assert dimensions == {"smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"}
