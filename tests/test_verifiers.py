"""
Tests for subprocess sandbox execution and timeout protection.
"""

import pytest
from twoma_bench.evaluator.sandbox import run_in_sandbox


@pytest.mark.asyncio
async def test_sandbox_normal_execution():
    code = "print('HELLO_2MA')\n"
    res = await run_in_sandbox(code, timeout_seconds=3.0)
    assert res.success is True
    assert "HELLO_2MA" in res.stdout
    assert res.timed_out is False


@pytest.mark.asyncio
async def test_sandbox_timeout_kill():
    # Infinite loop must be killed within timeout
    code = "import time\nwhile True:\n    time.sleep(0.1)\n"
    res = await run_in_sandbox(code, timeout_seconds=1.0)
    assert res.success is False
    assert res.timed_out is True
    assert res.return_code == -9


@pytest.mark.asyncio
async def test_sandbox_syntax_error():
    code = "def invalid_syntax(:\n"
    res = await run_in_sandbox(code, timeout_seconds=2.0)
    assert res.success is False
    assert "SyntaxError" in res.stderr
    assert res.timed_out is False


@pytest.mark.asyncio
async def test_state_machine_verifier_robust_extraction():
    from twoma_bench.generators.state_machine import StateMachineGenerator
    gen = StateMachineGenerator()
    problem = gen.generate(seed=42, difficulty=1)

    # Simulate realistic reasoning model output with intermediate traces and trailing commas
    noisy_reasoning_output = f"""
    <think>
    Cycle 1: SET R0, 4
    ```json
    {{"R0": 4}}
    ```
    Cycle 2: ADD R1, R2
    </think>
    After executing the assembly routine, the machine reaches HALT.
    Final register map:
    ```json
    {{
      "R0": {problem.ground_truth["R0"]}, // halted counter
      "R1": {problem.ground_truth["R1"]},
      "R2": {problem.ground_truth["R2"]},
      "R3": {problem.ground_truth["R3"]},
    }}
    ```
    """
    res = await gen.verify(problem, noisy_reasoning_output)
    assert res.passed is True
    assert res.score == 1.0


@pytest.mark.asyncio
async def test_counterfactual_verifier_robust_extraction():
    from twoma_bench.generators.counterfactual import CounterfactualGenerator
    gen = CounterfactualGenerator()
    problem = gen.generate(seed=42, difficulty=1)
    fields = list(problem.ground_truth.keys())

    # Simulate model producing plain text list without code blocks
    lines = "\n".join(f"- {f} = {problem.ground_truth[f]}" for f in fields)
    plain_text_output = f"Deduction complete.\nFinal state:\n{lines}\n"

    res = await gen.verify(problem, plain_text_output)
    assert res.passed is True
    assert res.score == 1.0


@pytest.mark.asyncio
async def test_constraint_sat_verifier_robust_extraction():
    from twoma_bench.generators.constraint_sat import ConstraintSatisfactionGenerator
    gen = ConstraintSatisfactionGenerator()
    problem = gen.generate(seed=42, difficulty=1)

    # Direct JSON dictionary without "assignment" wrapper
    direct_json = "```json\n" + "{\n" + ",\n".join(f'"{k}": {v}' for k, v in problem.ground_truth.items()) + "\n}\n```"
    res = await gen.verify(problem, direct_json)
    assert res.passed is True
    assert res.score == 1.0

