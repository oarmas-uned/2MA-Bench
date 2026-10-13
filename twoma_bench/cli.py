"""
Command-line interface (CLI) for 2M AI Bench (2MA-Bench).
Allows running automated headless benchmarks in CI/CD and launching the Web UI.
"""

import argparse
import asyncio
import os
import sys
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .client.base import ClientConfig, PROVIDER_PRESETS
from .client import create_client, MockClient
from .generators import list_dimensions, get_generator, generate_benchmark_suite
from .evaluator.engine import EvaluationConfig, EvaluationEngine, RunSummary
from .evaluator.exporter import BenchmarkExporter

console = Console()


def print_banner():
    banner = Text()
    banner.append("⚡ 2M AI BENCH (2MA-BENCH) ⚡\n", style="bold cyan")
    banner.append("Frontier Procedural Hardness AI Benchmark\n", style="bold white")
    banner.append("Zero Contamination • 100% Deterministic Programmatic Verifiers", style="dim")
    console.print(Panel(banner, border_style="cyan"))


async def run_benchmark_cli(args):
    print_banner()

    api_key = (
        args.api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or ""
    )
    
    if args.provider != "mock" and not api_key:
        console.print("[yellow]Warning: No API key provided via --api-key or environment variables. Proceeding anyway...[/yellow]")

    client_config = ClientConfig(
        provider=args.provider,
        base_url=args.base_url,
        api_key=api_key,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    client = create_client(client_config)

    dimensions = (
        [d.strip() for d in args.dimensions.split(",")]
        if args.dimensions != "all"
        else ["smt_logic", "vm_emulation", "counterfactual", "concurrency", "epistemic"]
    )

    # Handle mock client oracle wiring if needed
    if args.provider == "mock":
        generated_problems = generate_benchmark_suite(
            seed=args.seed,
            difficulty=args.difficulty,
            dimensions=dimensions,
            samples_per_dimension=args.samples_per_dim,
        )

        def oracle_solver(prompt: str) -> str:
            for prob in generated_problems:
                if prob.prompt.strip() == prompt.strip():
                    gen = get_generator(prob.dimension)
                    return gen.get_oracle_solution(prob)
            return '{"solvable": false}'

        client = MockClient(client_config, oracle_solver=oracle_solver, mock_mode="oracle")

    eval_config = EvaluationConfig(
        seed=args.seed,
        difficulty=args.difficulty,
        samples_per_dimension=args.samples_per_dim,
        max_concurrency=args.concurrency,
        dimensions=dimensions,
    )

    console.print(f"[cyan]Target Model:[/cyan] [bold]{args.model}[/bold] ({args.provider})")
    console.print(f"[cyan]Endpoint:[/cyan] {client_config.base_url}")
    console.print(f"[cyan]Seed:[/cyan] {args.seed} | [cyan]Difficulty:[/cyan] Tier {args.difficulty} | [cyan]Samples/Dim:[/cyan] {args.samples_per_dim} | [cyan]Concurrency:[/cyan] {args.concurrency}")
    console.print(f"[cyan]Dimensions:[/cyan] {', '.join(dimensions)}\n")

    with console.status("[bold green]Executing procedural challenges...", spinner="dots"):
        summary = await EvaluationEngine.run(client, eval_config)

    # Render results table
    table = Table(title="2MA-Bench Executive Scorecard", border_style="cyan")
    table.add_column("Dimension", style="bold")
    table.add_column("Title")
    table.add_column("Score", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Result", justify="center")

    for r in summary.results:
        res_style = "bold green" if r.verification.passed else "bold red"
        res_text = "PASS" if r.verification.passed else "FAIL"
        score_val = f"{round(r.verification.score * 100, 1)}%"
        table.add_row(
            r.dimension_name,
            r.title,
            score_val,
            str(r.model_response.total_tokens),
            f"{round(r.model_response.latency_ms)}ms",
            f"[{res_style}]{res_text}[/{res_style}]",
        )

    console.print(table)

    # Metrics summary panel
    score_style = "bold green" if summary.overall_score >= 80 else ("bold yellow" if summary.overall_score >= 50 else "bold red")
    summary_text = (
        f"Overall Score: [{score_style}]{summary.overall_score}%[/{score_style}]\n"
        f"Passed: {summary.passed_count} / {summary.total_problems} ({summary.overall_accuracy}%)\n"
        f"Total Tokens: {summary.total_tokens:,}\n"
        f"Average Latency: {summary.average_latency_ms} ms"
    )
    console.print(Panel(summary_text, title="Summary Metrics", border_style="cyan"))

    # Failure Taxonomy table if any failed
    if summary.passed_count < summary.total_problems and summary.failure_taxonomy:
        fail_table = Table(title="Failure Taxonomy Breakdown", border_style="red")
        fail_table.add_column("Category", style="bold red")
        fail_table.add_column("Count", justify="right")
        for cat, cnt in summary.failure_taxonomy.items():
            if cat != "PASSED":
                fail_table.add_row(cat, str(cnt))
        console.print(fail_table)

    if args.export:
        if args.export.endswith(".json"):
            with open(args.export, "w", encoding="utf-8") as f:
                f.write(BenchmarkExporter.to_json(summary))
            console.print(f"[green]Saved JSON report to {args.export}[/green]")
        elif args.export.endswith(".csv"):
            with open(args.export, "w", encoding="utf-8") as f:
                f.write(BenchmarkExporter.to_csv(summary))
            console.print(f"[green]Saved CSV report to {args.export}[/green]")
        elif args.export.endswith(".md"):
            with open(args.export, "w", encoding="utf-8") as f:
                f.write(BenchmarkExporter.to_markdown(summary))
            console.print(f"[green]Saved Markdown report to {args.export}[/green]")

    if summary.passed_count < summary.total_problems:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="2ma-bench",
        description="2M AI Bench - The Frontier Procedural Hardness Benchmark CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run 2MA-Bench evaluation")
    run_parser.add_argument("--provider", default="openai", choices=["openai", "anthropic", "gemini", "mock"], help="Provider type")
    run_parser.add_argument("--base-url", default="https://api.openai.com/v1", help="API Base URL")
    run_parser.add_argument("--api-key", default="", help="API key")
    run_parser.add_argument("--model", default="gpt-4o", help="Target model identifier")
    run_parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    run_parser.add_argument("--max-tokens", type=int, default=8192, help="Maximum tokens for generation (default: 8192)")
    run_parser.add_argument("--seed", type=int, default=42, help="Procedural random seed")
    run_parser.add_argument("--difficulty", type=int, default=1, choices=[1, 2, 3], help="Difficulty tier")
    run_parser.add_argument("-n", "--samples-per-dim", type=int, default=1, help="Samples per dimension")
    run_parser.add_argument("-c", "--concurrency", type=int, default=2, help="Worker concurrency limit")
    run_parser.add_argument("--dimensions", default="all", help="Comma-separated dimensions or 'all'")
    run_parser.add_argument("--export", default=None, help="Path to export report (.json, .csv, or .md)")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch 2MA-Bench Web UI")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host interface")
    serve_parser.add_argument("--port", type=int, default=8088, help="Port to listen on (never 8000)")

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn
        console.print(f"[bold cyan]Launching 2M AI Bench Dashboard on http://{args.host}:{args.port}[/bold cyan]")
        uvicorn.run("twoma_bench.web.app:app", host=args.host, port=args.port)
    elif args.command == "run":
        asyncio.run(run_benchmark_cli(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
