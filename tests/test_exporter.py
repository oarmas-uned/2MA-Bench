"""
Unit tests for BenchmarkExporter (Markdown, JSON, CSV).
"""

import csv
import io
import json
import pytest
from twoma_bench.evaluator.exporter import BenchmarkExporter
from twoma_bench.evaluator.engine import RunSummary, ProblemEvaluationResult
from twoma_bench.generators.base import VerifierResult
from twoma_bench.client.base import ModelResponse


@pytest.fixture
def sample_summary() -> RunSummary:
    verification = VerifierResult(
        problem_id="prob_1",
        dimension="smt_logic",
        passed=True,
        score=1.0,
    )
    model_response = ModelResponse(
        content='{"assignment": {"A": 1}}',
        prompt_tokens=150,
        completion_tokens=25,
        total_tokens=175,
        latency_ms=120.5,
    )
    result = ProblemEvaluationResult(
        problem_id="prob_1",
        dimension="smt_logic",
        dimension_name="Dynamic Constraint Satisfaction & SMT",
        title="Dynamic SMT Constraint Grid",
        prompt="Solve problem...",
        model_response=model_response,
        verification=verification,
        failure_type="PASSED",
    )
    return RunSummary(
        run_id="2ma_test123",
        created_at="2026-10-13T12:00:00Z",
        model="gpt-4o",
        provider="openai",
        seed=42,
        difficulty=1,
        samples_per_dimension=1,
        total_problems=1,
        passed_count=1,
        overall_accuracy=100.0,
        overall_score=100.0,
        dimension_scores={"smt_logic": 100.0},
        dimension_passes={"smt_logic": True},
        failure_taxonomy={"PASSED": 1},
        total_tokens=175,
        total_prompt_tokens=150,
        total_completion_tokens=25,
        total_latency_ms=120.5,
        average_latency_ms=120.5,
        results=[result],
    )


def test_export_markdown(sample_summary):
    md = BenchmarkExporter.to_markdown(sample_summary)
    assert "# 2M AI Bench (2MA-Bench) Evaluation Report" in md
    assert "2ma_test123" in md
    assert "gpt-4o" in md
    assert "100.0%" in md


def test_export_json(sample_summary):
    json_str = BenchmarkExporter.to_json(sample_summary)
    data = json.loads(json_str)
    assert data["run_id"] == "2ma_test123"
    assert data["model"] == "gpt-4o"
    assert len(data["results"]) == 1


def test_export_csv(sample_summary):
    csv_str = BenchmarkExporter.to_csv(sample_summary)
    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "2ma_test123"
    assert rows[0]["dimension"] == "smt_logic"
    assert rows[0]["passed"] == "True"
    assert rows[0]["score"] == "1.0"
    assert rows[0]["failure_type"] == "PASSED"
