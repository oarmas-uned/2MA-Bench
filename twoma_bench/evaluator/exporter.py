"""
Unified benchmark exporter for 2MA-Bench.
Generates comprehensive Markdown, JSON, and CSV reports.
"""

import csv
import io
import json
from typing import Dict, Any
from .engine import RunSummary


class BenchmarkExporter:
    """Exports RunSummary into Markdown, CSV, and JSON formats."""

    @staticmethod
    def to_markdown(summary: RunSummary) -> str:
        lines = [
            f"# 2M AI Bench (2MA-Bench) Evaluation Report",
            f"**Run ID**: `{summary.run_id}`  ",
            f"**Timestamp**: {summary.created_at}  ",
            f"**Model**: `{summary.model}` ({summary.provider})  ",
            f"**Parameters**: Seed={summary.seed} | Difficulty=Tier {summary.difficulty} | Samples/Dimension={summary.samples_per_dimension}  ",
            f"\n---\n",
            f"## 🏆 Executive Scorecard",
            f"- **Overall Hardness Score**: **{summary.overall_score}%**",
            f"- **Benchmark Pass Rate**: {summary.passed_count} / {summary.total_problems} ({summary.overall_accuracy}%)",
            f"- **Total Token Footprint**: {summary.total_tokens:,} ({summary.total_prompt_tokens:,} prompt / {summary.total_completion_tokens:,} completion)",
            f"- **Average Inference Latency**: {summary.average_latency_ms} ms",
            f"\n### 📊 Dimension Capability Breakdown",
            f"| Dimension | Hardness Score | Status |",
            f"| :--- | :--- | :--- |",
        ]

        for dim, score in summary.dimension_scores.items():
            status = "PASSED" if summary.dimension_passes.get(dim) else "FAILED"
            lines.append(f"| `{dim}` | **{score}%** | {status} |")

        if summary.failure_taxonomy:
            lines.extend([
                f"\n### 🔍 Failure Taxonomy Breakdown",
                f"| Category | Occurrences |",
                f"| :--- | :--- |",
            ])
            for cat, count in sorted(summary.failure_taxonomy.items()):
                lines.append(f"| `{cat}` | {count} |")

        lines.append("\n### 🔬 Detailed Challenge Telemetry\n")
        for idx, r in enumerate(summary.results, 1):
            status_tag = "✅ PASSED" if r.verification.passed else "❌ FAILED"
            lines.append(f"#### #{idx} [{r.dimension}] {r.title}")
            lines.append(f"- **Verdict**: {status_tag} (Score: {round(r.verification.score * 100, 1)}%)")
            lines.append(f"- **Classification**: `{r.failure_type}`")
            lines.append(f"- **Latency**: {round(r.model_response.latency_ms, 1)} ms | **Tokens**: {r.model_response.total_tokens}")
            if r.verification.failure_reason:
                lines.append(f"- **Failure Analysis**: `{r.verification.failure_reason}`")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_json(summary: RunSummary) -> str:
        return json.dumps(summary.model_dump(), indent=2)

    @staticmethod
    def to_csv(summary: RunSummary) -> str:
        output = io.StringIO()
        fieldnames = [
            "run_id",
            "model",
            "problem_id",
            "dimension",
            "title",
            "passed",
            "score",
            "failure_type",
            "failure_reason",
            "latency_ms",
            "total_tokens",
            "prompt_tokens",
            "completion_tokens",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for r in summary.results:
            writer.writerow({
                "run_id": summary.run_id,
                "model": summary.model,
                "problem_id": r.problem_id,
                "dimension": r.dimension,
                "title": r.title,
                "passed": r.verification.passed,
                "score": r.verification.score,
                "failure_type": r.failure_type,
                "failure_reason": r.verification.failure_reason or "",
                "latency_ms": round(r.model_response.latency_ms, 1),
                "total_tokens": r.model_response.total_tokens,
                "prompt_tokens": r.model_response.prompt_tokens,
                "completion_tokens": r.model_response.completion_tokens,
            })

        return output.getvalue()
