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
    # Test across multiple seeds to trigger different templates
    for seed in [1, 2, 3, 4, 10, 42, 88]:
        prob = gen.generate(seed=seed, difficulty=1)
        assert prob.dimension == "concurrency"
        assert len(prob.metadata["class_name"]) > 0

        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True
        assert res.score == 1.0


@pytest.mark.asyncio
async def test_concurrency_templates_explicit():
    from twoma_bench.generators.concurrency_code import ConcurrencyBugTemplates
    gen = ConcurrencyGenerator()

    # Test deadlock template
    deadlock_prob = ConcurrencyBugTemplates.get_deadlock_problem(seed=42, difficulty=1)
    prob_obj = gen.generate(seed=42, difficulty=1)
    prob_obj.ground_truth = deadlock_prob["oracle_code"]
    prob_obj.metadata = {
        "class_name": deadlock_prob["class_name"],
        "test_harness": deadlock_prob["test_harness"],
    }
    res = await gen.verify(prob_obj, f"```python\n{deadlock_prob['oracle_code']}\n```")
    assert res.passed is True

    # Test atomic counter template
    counter_prob = ConcurrencyBugTemplates.get_atomic_counter_problem(seed=99, difficulty=1)
    prob_obj.ground_truth = counter_prob["oracle_code"]
    prob_obj.metadata = {
        "class_name": counter_prob["class_name"],
        "test_harness": counter_prob["test_harness"],
    }
    res = await gen.verify(prob_obj, f"```python\n{counter_prob['oracle_code']}\n```")
    assert res.passed is True


@pytest.mark.asyncio
async def test_state_machine_difficulty_tiers():
    gen = StateMachineGenerator()
    for diff in [1, 2, 3]:
        prob = gen.generate(seed=42, difficulty=diff)
        oracle = gen.get_oracle_solution(prob)
        res = await gen.verify(prob, oracle)
        assert res.passed is True
        assert res.score == 1.0


@pytest.mark.asyncio
async def test_epistemic_trap_generator():
    gen = EpistemicTrapGenerator()
    for seed in [3, 42, 105, 777, 888, 999]:
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


def test_suite_generation_multisample():
    suite_1 = generate_benchmark_suite(seed=42, difficulty=1, samples_per_dimension=1)
    assert len(suite_1) == 5

    suite_3 = generate_benchmark_suite(seed=42, difficulty=1, samples_per_dimension=3)
    assert len(suite_3) == 15
    dim_counts = {}
    for p in suite_3:
        dim_counts[p.dimension] = dim_counts.get(p.dimension, 0) + 1
    assert all(count == 3 for count in dim_counts.values())

