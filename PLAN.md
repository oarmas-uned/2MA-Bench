# 2M AI Bench (2MA-Bench) - Project Implementation Plan

**2M AI Bench** (short: **2MA-Bench**) is the frontier AI benchmark platform engineered for extreme hardness, zero memorization/pretraining leakage, and deterministic ground-truth verification.

Users can bring their own API keys, base URLs, and models (`OpenAI-compatible` or `Anthropic Claude`) to test capabilities across 5 purely procedural, seeded hardness dimensions.

---

## 1. Core Principles

1. **100% Dynamic & Seeded Procedural Generation**:
   - Zero static question datasets.
   - Every problem instance is generated on the fly using a random seed.
   - Topologies, variable names, non-standard axioms, logic relations, and concurrency bugs are generated dynamically alongside their deterministic ground truth.
   - Pre-training data memorization is mathematically impossible.

2. **Universal Bring-Your-Own-Model (BYOM)**:
   - **OpenAI Compatible Protocol**: Works with OpenAI (`o1`, `o3-mini`, `gpt-4o`), DeepSeek (`r1`, `v3`), vLLM, Ollama, OpenRouter, Groq, Together AI, Mistral. Supports custom `base_url`, `api_key`, `model`, extra headers, and reasoning effort (`thinking`).
   - **Anthropic Claude Protocol**: Native Messages API adapter (`claude-3-7-sonnet`, `claude-3-5-sonnet`, etc.).

3. **Dual Interface**:
   - **Web Dashboard**: High-tech cyber dark-mode UI with real-time Server-Sent Events (SSE) streaming reasoning tokens, live execution steps, capability radar charts, failure taxonomy, and JSON/CSV/Markdown report exports.
   - **Terminal CLI**: `2ma-bench run --base-url ... --api-key ... --model ...` with rich terminal progress tables and CI/CD exit codes.

4. **Deterministic Programmatic Verification**:
   - No subjective LLM-as-a-judge.
   - Verification via SMT/backtracking logic checkers, virtual machine state interpreters, deductive formal rule verifiers, and subprocess sandboxes with stress testing.

---

## 2. The 5 Procedural Hardness Dimensions

```
+---------------------------------------------------------------------------------------------------+
|                                   2MA-Bench Seeded Generator Engine                               |
+--------------------+---------------------+--------------------+--------------------+--------------+
| Dimension 1        | Dimension 2         | Dimension 3        | Dimension 4        | Dimension 5  |
| Dynamic SMT/Logic  | Virtual Register VM | Counterfactual     | Sandboxed Python   | Epistemic    |
| Constraints        | Emulation           | Axiomatic Logic    | Concurrency Fix    | Impossibility|
+--------------------+---------------------+--------------------+--------------------+--------------+
| Verifier:          | Verifier:           | Verifier:          | Verifier:          | Verifier:    |
| SMT / Backtracking | Step VM Interpreter | Deductive Engine   | Subprocess Sandbox | Proof Engine |
+--------------------+---------------------+--------------------+--------------------+--------------+
```

### Dimension 1: Dynamic Constraint Satisfaction & SMT
- Procedurally generated $N$-entity, $M$-relation constraint satisfaction problems (complex scheduling, graph coloring, non-linear arithmetic inequalities, logic grids) with randomized names and edge constraints.
- Verified deterministically with an internal SMT/constraint-propagation solver.

### Dimension 2: Procedural State Machine & Virtual Machine Emulation
- Synthesizes a unique dynamic register machine / pseudo-assembly with randomized opcodes, memory cells, branching conditions, and execution limits.
- The model must trace and output the exact register state after simulated execution.
- Verified by a deterministic virtual machine interpreter.

### Dimension 3: Counterfactual Axiomatic Logic
- Synthesizes formal deductive worlds with non-standard axioms that contradict real-world priors (e.g. inverted physics, non-standard propositional logic rules).
- Tests symbolic reasoning and premise adherence while neutralizing web-training memorization.

### Dimension 4: Sandboxed Concurrent Code Synthesis & Race Condition Repair
- Procedurally generates concurrent Python code (multi-threaded queues, asyncio race conditions, distributed locks, deadlock scenarios) containing subtle timing bugs.
- The model must write the fix.
- Evaluated in an isolated subprocess running 50+ concurrent stress iterations under strict resource limits.

### Dimension 5: Epistemic Calibration & Impossibility Detection
- Procedurally generates problems where ~35% are mathematically provably impossible (contradictory constraints, non-hamiltonian paths, unsatisfiable equations).
- Tests whether the model identifies the exact contradiction or hallucinates a false solution. Heavily penalizes confident hallucinations.

---

## 3. Architecture & File Structure

```
/root/aibm/
├── pyproject.toml
├── README.md
├── PLAN.md                      <-- This implementation plan
├── twoma_bench/
│   ├── __init__.py
│   ├── client/
│   │   ├── __init__.py
│   │   ├── base.py              # LLM Client protocol & response schema
│   │   ├── openai_client.py     # OpenAI-compatible client (vLLM, Ollama, DeepSeek, Groq, OpenAI)
│   │   └── anthropic_client.py  # Anthropic Claude Messages API client
│   ├── generators/              # 100% Procedural & Seeded Problem Generators
│   │   ├── __init__.py
│   │   ├── base.py              # BaseGenerator, BenchmarkProblem, VerifierResult
│   │   ├── constraint_sat.py    # Dimension 1: Dynamic logic & constraint satisfaction
│   │   ├── state_machine.py     # Dimension 2: Virtual register machine emulation
│   │   ├── counterfactual.py    # Dimension 3: Alternate axiomatic deductive logic
│   │   ├── concurrency_code.py  # Dimension 4: Sandboxed race condition & concurrency fixes
│   │   └── epistemic_trap.py    # Dimension 5: Provably impossible & contradiction detection
│   ├── evaluator/
│   │   ├── __init__.py
│   │   ├── sandbox.py           # Subprocess isolation, timeouts, memory guards
│   │   ├── verifier.py          # Ground truth verification & AST/math checks
│   │   └── engine.py            # Async evaluation orchestrator, rate limits, metrics
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI server, REST endpoints & SSE streaming
│   │   └── static/
│   │       ├── index.html       # Cyber dark-mode dashboard
│   │       ├── app.js           # Live SSE stream, charts, interactive test runner
│   │       └── style.css        # Premium typography & design
│   └── cli.py                   # Scriptable CLI runner with rich terminal output
└── tests/
    ├── test_generators.py       # Validates that all generators produce solvable/verifiable problems
    ├── test_verifiers.py        # Verifies sandbox & deterministic solvers
    └── test_client.py           # Mock client integration tests
```

---

## 4. Implementation Phases

### Phase 1: Environment & Project Setup
- `pyproject.toml` with dependencies (`fastapi`, `uvicorn`, `httpx`, `pydantic>=2`, `rich`, `pytest`).
- Initialize package `twoma_bench`.

### Phase 2: BYOM LLM Client Engine
- Support for OpenAI-compatible endpoints (`base_url`, `api_key`, `model_name`).
- Support for Anthropic Claude Messages API.
- Streaming responses, token/latency metrics, retry backoff, and reasoning effort controls.

### Phase 3: The 5 Procedural Seeded Generators & Verifiers
- Implement `BaseGenerator` and `BenchmarkProblem` data contracts.
- Implement Dimension 1 (Constraint Satisfaction).
- Implement Dimension 2 (Register Machine Emulation).
- Implement Dimension 3 (Counterfactual Axiomatic Logic).
- Implement Dimension 4 (Concurrent Python Bug Repair with Subprocess Sandbox).
- Implement Dimension 5 (Epistemic Impossibility & Calibration).

### Phase 4: Sandboxed Execution & Verification Engine
- Subprocess sandbox execution with resource isolation (CPU timeouts, memory guards).
- Deterministic verification engine and scoring algorithms (Accuracy, Hardness Index, Calibration Brier Score, Speed/Efficiency).

### Phase 5: Modern Web Dashboard (FastAPI + SSE + Real-Time UI)
- REST API: Connection verification, run creation, test history, export.
- SSE Stream: Real-time event pipe streaming reasoning tokens, test execution logs, and live radar charts.
- Dark-mode, responsive Web UI with interactive model test inputs and exportable reports (JSON/Markdown).

### Phase 6: Terminal CLI Runner
- `2ma-bench run ...` command with live rich tables, difficulty tier selectors, and CI/CD status codes.

### Phase 7: Verification & Testing
- Automated unit and integration tests across generators, verifiers, sandbox, and clients.
- End-to-end execution with mock provider.

---

## 5. Verification Plan

1. **Automated Tests**:
   - `pytest tests/test_generators.py -v`: Tests multiple seeds per dimension, verifying that generated problems are valid and deterministically verifiable.
   - `pytest tests/test_verifiers.py -v`: Tests sandbox timeout guards, memory limits, and malicious payload isolation.
   - `pytest tests/test_client.py -v`: Tests HTTP client protocol adapters with mock endpoints.
2. **Manual & End-to-End Verification**:
   - Start the web dashboard: `python -m twoma_bench.web.app --port 8088` (never 8000).
   - Test model configuration, run live benchmark suite, check live streaming SSE, view radar chart, and export report.
   - Run CLI: `python -m twoma_bench.cli run --provider mock`.
