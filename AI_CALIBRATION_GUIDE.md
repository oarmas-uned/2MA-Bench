# 🧠 2MA-Bench: AI Calibration & In-Context Prompting Guide

> **Official In-Context Training Reference for Evaluated AI Models & Evaluator Harnesses**

2MA-Bench is a zero-contamination, procedural hardness benchmark. Because all test problems are synthesized dynamically at runtime using random seeds, pre-training memorization is impossible. 

This guide provides system prompt calibrations, in-context schemas, and dimension-by-dimension guidelines so evaluated models understand exactly how to structure their reasoning and output ground-truth verifiable answers.

---

## 🌟 Standard System Prompt Calibration

Prepend this calibrated system prompt to any model invocation (`OpenAI-compatible`, `Claude Messages API`, or `Google Gemini`):

```text
You are an expert frontier reasoning AI evaluated by 2MA-Bench (The Frontier Procedural Hardness Benchmark).
Strictly follow these response constraints:
1. Strict Output Formatting: Conclude your final response with the requested JSON block enclosed in ```json ... ``` or Python code in ```python ... ```. Ensure the JSON block is the very last element of your response.
2. 8-Bit Architecture: When tracing Virtual Machine assembly, all arithmetic and bitwise shifts operate strictly modulo 256 in [0, 255].
3. Concurrency Safety: When repairing concurrent code, maintain thread-safety under 50+ concurrent threads without deadlocks or race conditions. Preserve all original method signatures.
4. Epistemic Calibration: If a mathematical system or graph problem is provably impossible or contradictory, explicitly prove the contradiction. Never fabricate or hallucinate solutions for unsolvable problems.
```

---

## ⚡ Frontier Model Configuration & Token Budget Recommendations

Frontier reasoning models (e.g. OpenAI `o1`/`o3-mini`, Anthropic `Claude 3.7 Sonnet (Extended Thinking)`, DeepSeek `deepseek-reasoner / R1`, Google `Gemini 2.5 Pro`) utilize tokens for both internal chain-of-thought scratchpads and visible generation.

### Why Tests May Fail If `max_tokens` Is Too Low
- When evaluating complex dimensions like **Synthetic VM Register Emulation** (tracing loops of 50–100 cycles) or **Counterfactual Axiomatic Deductions** (10+ multi-step non-Euclidean state updates), reasoning models often generate 2,500–4,000 reasoning tokens before producing the final answer.
- If `max_tokens` is configured at the legacy default of `4096`, the model's response will be **truncated mid-generation**, cutting off closing JSON fences and causing extraction failures.
- **Recommended Configuration**:
  - Set `max_tokens: 8192` (default in 2MA-Bench v0.2.0) or `16384` for deep reasoning workloads.
  - In the CLI: `2ma-bench run --model deepseek-reasoner --max-tokens 8192`
  - In the Web UI: Select `8,192 (Rec.)` or `16,384` from the **Max Tokens** dropdown.

---

## 🔬 Dimension-by-Dimension Calibration

### Dimension 1: Dynamic SMT Constraint Satisfaction (`smt_logic`)
* **Objective**: Assign integer domain values to variables satisfying all relational inequalities, offsets, and parity rules.
* **Output Format**: Valid JSON object enclosed in ```` ```json ````:
  ```json
  {
    "assignment": {
      "Subsystem_A": 1,
      "Subsystem_B": 4,
      "Subsystem_C": 2
    }
  }
  ```
* **Common Pitfall**: Omitting transitive constraints or producing assignments outside the specified domain.

---

### Dimension 2: Synthetic Virtual Register Machine (`vm_emulation`)
* **Objective**: Trace a synthetic assembly program cycle-by-cycle and output the exact register values upon machine halt (`HALT`).
* **Opcode Rules**:
  * `SET Rx, val`: $R_x = \text{val} \pmod{256}$
  * `ADD Rx, Ry`: $R_x = (R_x + R_y) \pmod{256}$
  * `SUB Rx, Ry`: $R_x = (R_x - R_y) \pmod{256}$
  * `XOR Rx, Ry`: $R_x = (R_x \oplus R_y) \pmod{256}$
  * `SHL Rx`: $R_x = (R_x \ll 1) \pmod{256}$ (Logical shift left 1 bit)
  * `SHR Rx`: $R_x = (R_x \gg 1) \pmod{256}$ (Logical shift right 1 bit)
  * `SWP Rx, Ry`: Swap contents of $R_x$ and $R_y$
  * `JNZ Rx, target`: Jump to line `target` if $R_x \neq 0$
* **Output Format**:
  ```json
  {
    "R0": 0,
    "R1": 42,
    "R2": 115,
    "R3": 8
  }
  ```
* **Common Pitfall**: Forgetting modulo 256 overflow during arithmetic or shifts.

---

### Dimension 3: Counterfactual Axiomatic Logic (`counterfactual`)
* **Objective**: Deduce the final state of an axiomatic formal world governed by synthetic modular operators that violate earthly physics/algebra.
* **Output Format**:
  ```json
  {
    "Flux": 14,
    "Resonance": 7,
    "Chroma": 22,
    "Entropy": 3
  }
  ```
* **Common Pitfall**: Applying standard Newtonian or Pythagorean algebraic identities instead of the problem's explicit synthetic axioms.

---

### Dimension 4: Sandboxed Concurrency & Race Condition Repair (`concurrency`)
* **Objective**: Identify race conditions, check-then-act hazards, lock-inversion deadlocks, or spurious condition variable wakeups, and provide the repaired Python class.
* **Output Format**: Provide the full corrected class inside a single ```` ```python ```` block.
* **Key Patterns**:
  * **Spurious Wakeup / Condition Variable**: Replace `if` guards with `while` loops around `cond.wait()`.
  * **Check-Then-Act**: Acquire locks *before* reading state that dictates mutations.
  * **Deadlock Inversion (AB-BA)**: Impose consistent global lock ordering (e.g. `first, second = sorted_by_id(a, b)`).
  * **Read-Modify-Write**: Protect concurrent counter and dictionary mutations with a mutex.

---

### Dimension 5: Epistemic Impossibility & Calibration (`epistemic`)
* **Objective**: Correctly classify whether a challenge is solvable or mathematically provably impossible (traps penalize false positives at -1.0).
* **Output Format (If Solvable)**:
  ```json
  {
    "solvable": true,
    "x": 3,
    "y": -7
  }
  ```
* **Output Format (If Provably Impossible)**:
  ```json
  {
    "solvable": false,
    "contradiction": "gcd(21, 14) = 7, but 111 is not divisible by 7. By Bezout's identity, no integer solution exists."
  }
  ```
* **Trap Scenarios**:
  * **Diophantine Equations**: $A x + B y = C$ has no integer solution if $C \not\equiv 0 \pmod{\gcd(A, B)}$.
  * **Eulerian Graph Traversal**: An Eulerian path exists if and only if exactly 0 or 2 vertices have odd degree. If $\ge 4$ vertices have odd degree, it is provably impossible.
  * **Modular Congruence Systems**: $x \equiv a \pmod{m_1}$ and $x \equiv b \pmod{m_2}$ has no solution if $a \not\equiv b \pmod{\gcd(m_1, m_2)}$.
