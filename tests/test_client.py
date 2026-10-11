"""
Tests for LLM clients and end-to-end evaluation engine.
"""

import pytest
from twoma_bench.client.base import ClientConfig
from twoma_bench.client import create_client, MockClient, OpenAIClient, AnthropicClient
from twoma_bench.evaluator.engine import EvaluationConfig, EvaluationEngine
from twoma_bench.generators import get_generator


@pytest.mark.asyncio
async def test_client_factory():
    cfg_oai = ClientConfig(provider="openai", base_url="https://api.openai.com/v1", model="gpt-4o")
    client_oai = create_client(cfg_oai)
    assert isinstance(client_oai, OpenAIClient)

    cfg_ant = ClientConfig(provider="anthropic", model="claude-3-7-sonnet")
    client_ant = create_client(cfg_ant)
    assert isinstance(client_ant, AnthropicClient)

    cfg_mock = ClientConfig(provider="mock")
    client_mock = create_client(cfg_mock)
    assert isinstance(client_mock, MockClient)


@pytest.mark.asyncio
async def test_mock_client_oracle():
    cfg = ClientConfig(provider="mock")
    oracle = lambda prompt: '{"assignment": {"A": 1}}'
    client = MockClient(cfg, oracle_solver=oracle, mock_mode="oracle")

    resp = await client.generate("test prompt")
    assert resp.success is True
    assert "assignment" in resp.content
    assert resp.prompt_tokens > 0


@pytest.mark.asyncio
async def test_end_to_end_engine_run():
    cfg = ClientConfig(provider="mock")
    seed = 42

    def oracle_solver(prompt: str) -> str:
        for d in ["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"]:
            gen = get_generator(d)
            prob = gen.generate(seed, difficulty=1)
            if prob.prompt[:30] in prompt[:30]:
                return gen.get_oracle_solution(prob)
        return "{\"solvable\": false}"

    client = MockClient(cfg, oracle_solver=oracle_solver, mock_mode="oracle")
    eval_config = EvaluationConfig(
        seed=seed,
        difficulty=1,
        dimensions=["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"],
    )

    events_received = []

    async def callback(evt):
        events_received.append(evt["type"])

    summary = await EvaluationEngine.run(client, eval_config, event_callback=callback)

    assert summary.total_problems == 5
    assert summary.passed_count == 5
    assert summary.overall_accuracy == 100.0
    assert summary.overall_score == 100.0
    assert "run_started" in events_received
    assert "run_completed" in events_received
