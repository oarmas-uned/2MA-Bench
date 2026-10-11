# ⚡ 2M AI Bench (2MA-Bench)

> **The Frontier Procedural Hardness AI Benchmark**  
> *Zero Memorization • 100% Deterministic Programmatic Verifiers • Bring Your Own Model (BYOM)*

---

## 🌟 Why 2M AI Bench?

Current frontier AI benchmarks (MMLU, GSM8K, HumanEval, GPQA) suffer from severe flaws:
1. **Data Contamination & Memorization**: Static questions leak into pre-training corpora.
2. **Subjective LLM Judges**: Non-deterministic LLM-as-a-judge grades hallucinate and fluctuate.
3. **Superficial Horizons**: Models exploit surface-level statistical patterns rather than conducting multi-step formal reasoning.

**2M AI Bench (2MA-Bench)** solves this by being **100% Procedural & Seeded**:
- Every test problem is synthesized dynamically at runtime using random seeds.
- Non-standard axioms, synthetic register architectures, and concurrency bugs are generated on the fly alongside mathematical ground-truth solvers.
- Zero memorization is possible: pretraining on the web gives models no prior advantage.

---

## 🔬 The 5 Frontier Hardness Dimensions

| # | Dimension | Core Challenge | Deterministic Verifier |
|---|---|---|---|
| **1** | **Dynamic SMT Constraint Satisfaction** | Procedural $N$-variable, $M$-constraint logic grids with complex implications & parity rules. | Finite-domain backtracking constraint solver / SMT logic engine |
| **2** | **Virtual Register Machine Emulation** | Tracing a synthetic 8-bit register machine with loops, bitwise manipulations, and branching. | Deterministic virtual machine cycle emulator |
| **3** | **Counterfactual Axiomatic Logic** | Formal worlds with non-standard physical/algebraic axioms that violate real-world training priors. | Exact modular algebraic state evaluator |
| **4** | **Sandboxed Concurrency Bug Repair** | Diagnosing and fixing race conditions, atomicity bugs, and deadlocks in multi-threaded Python code. | Subprocess isolation sandbox running 50+ concurrent stress test iterations |
| **5** | **Epistemic Impossibility & Calibration** | Identifying provably impossible mathematical/graph problems vs. solvable instances (penalizes hallucinations). | Bézout Diophantine & Eulerian graph contradiction proof engine |

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone <repo-url>
cd aibm
pip install -e .
```

### 2. Launch the Web Dashboard

```bash
2ma-bench serve --host 0.0.0.0 --port 8088
```
Open your browser at `http://localhost:8088`.

### 3. Run via CLI

#### Test any OpenAI-Compatible Endpoint (OpenAI, DeepSeek, vLLM, Ollama, OpenRouter, Groq):
```bash
2ma-bench run \
  --provider openai \
  --base-url https://api.openai.com/v1 \
  --api-key "sk-..." \
  --model "gpt-4o" \
  --seed 42 \
  --difficulty 1 \
  --export report.json
```

#### Test Local Models (Ollama / vLLM):
```bash
2ma-bench run \
  --provider openai \
  --base-url http://localhost:11434/v1 \
  --model "llama3:70b" \
  --seed 101
```

#### Test Anthropic Claude Models:
```bash
2ma-bench run \
  --provider anthropic \
  --api-key "sk-ant-..." \
  --model "claude-3-7-sonnet" \
  --seed 42
```

#### Test in Offline Mock Mode (Zero API Key Needed):
```bash
2ma-bench run --provider mock
```

---

## 📊 Scorecard & Metrics

2MA-Bench generates a comprehensive executive scorecard:
- **Overall Hardness Score (%)**: Weighted accuracy across all selected dimensions.
- **Epistemic Calibration Penalty**: Models that hallucinate solutions on provably impossible problems are penalized (-1.0) rather than receiving partial credit.
- **Token Efficiency & Latency Profiling**: Measures reasoning tokens, total token footprint, and inference latency.
- **Capability Radar Chart**: Visualizes model strengths across Symbolic Logic, State Tracking, Axiomatic Deduction, Systems Engineering, and Epistemic Calibration.
- **Export Formats**: Full JSON telemetry and printable Markdown summary reports.

---

## 🧪 Running Automated Tests

```bash
pytest -v
```

All 15 unit and integration tests verify:
- Constraint satisfaction solver uniqueness
- Virtual machine step interpreter fidelity
- Subprocess sandbox execution and infinite loop timeout kills
- Provider protocol client adapters
- FastAPI REST endpoints and Server-Sent Events (SSE) streaming

---

## 📄 License

Apache 2.0. Built for the frontier AI evaluation community.
