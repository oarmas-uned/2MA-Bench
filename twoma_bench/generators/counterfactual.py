"""
Dimension 3: Counterfactual Axiomatic Logic.
Procedurally generates formal deductive systems with counter-intuitive axioms
that violate real-world physical and algebraic priors.
Forces the model to adhere strictly to novel symbolic axioms.
"""

import json
import random
import re
from typing import Dict, List, Tuple, Any
from .base import BaseGenerator, BenchmarkProblem, VerifierResult


class CounterfactualGenerator(BaseGenerator):
    """Generates synthetic axiomatic formal systems with non-standard operations."""

    @property
    def dimension_id(self) -> str:
        return "counterfactual"

    @property
    def dimension_name(self) -> str:
        return "Counterfactual Axiomatic Logic"

    def generate(self, seed: int, difficulty: int = 1) -> BenchmarkProblem:
        rng = random.Random(seed)
        modulus = rng.choice([17, 23, 29, 31, 37])
        
        c1 = rng.randint(2, 7)
        c2 = rng.randint(1, 9)
        c3 = rng.randint(2, 5)

        fields = ["Flux", "Resonance", "Chroma", "Entropy"]
        if difficulty >= 2:
            fields.append("Vorticity")

        # Initial values
        state = {f: rng.randint(1, modulus - 1) for f in fields}
        initial_state = dict(state)

        # Axiom rules
        # Operator 1: Pulse Theta(x) = (c1 * x + c2) % modulus
        # Operator 2: Collision a @ b = (a * b - c3) % modulus
        # Operator 3: Phase Shift Psi(x) = (x^2 + 1) % modulus
        
        events: List[str] = []
        num_steps = 5 + difficulty * 2

        for step in range(num_steps):
            action_type = rng.choice(["pulse", "collision", "phase_shift", "swap_decay"])
            if action_type == "pulse":
                target = rng.choice(fields)
                state[target] = (c1 * state[target] + c2) % modulus
                events.append(f"Step {step+1}: Apply Pulse Theta to '{target}'.")
            elif action_type == "collision":
                f1 = rng.choice(fields)
                f2 = rng.choice([f for f in fields if f != f1])
                new_val = (state[f1] * state[f2] - c3) % modulus
                state[f1] = new_val
                events.append(f"Step {step+1}: Fuse '{f1}' with '{f2}' via Collision Operator. Value of '{f1}' becomes ('{f1}' Collision '{f2}').")
            elif action_type == "phase_shift":
                target = rng.choice(fields)
                state[target] = (pow(state[target], 2, modulus) + 1) % modulus
                events.append(f"Step {step+1}: Apply Phase Shift Psi to '{target}'.")
            elif action_type == "swap_decay":
                f1 = rng.choice(fields)
                f2 = rng.choice([f for f in fields if f != f1])
                diff = abs(state[f1] - state[f2]) % modulus
                state[f1] = (state[f1] + diff) % modulus
                state[f2] = (state[f2] - diff + modulus) % modulus
                events.append(f"Step {step+1}: Harmonic Exchange between '{f1}' and '{f2}'.")

        axioms_text = [
            f"All values exist strictly within the finite field Z_{modulus} (integers modulo {modulus}, range 0 to {modulus-1}).",
            f"Axiom 1 (Pulse Theta): For any scalar x, Theta(x) = ({c1} * x + {c2}) mod {modulus}.",
            f"Axiom 2 (Collision Operator): For two scalars a and b, (a Collision b) = (a * b - {c3}) mod {modulus}.",
            f"Axiom 3 (Phase Shift Psi): For any scalar x, Psi(x) = (x^2 + 1) mod {modulus}.",
            f"Axiom 4 (Harmonic Exchange): For elements a and b, let diff = |a - b| mod {modulus}. Then a becomes (a + diff) mod {modulus}, and b becomes (b - diff) mod {modulus}."
        ]

        init_text = ", ".join(f"{f} = {val}" for f, val in initial_state.items())

        prompt = (
            f"Deduce the final state of the synthetic physical system governed strictly by the following counterfactual axioms.\n"
            f"WARNING: Standard physical or mathematical conventions do not apply. You must compute each step strictly using the given axioms.\n\n"
            f"System Axioms:\n"
            + "\n".join(f"- {a}" for a in axioms_text)
            + f"\n\nInitial State (at Step 0):\n{init_text}\n\n"
            f"Sequence of Transformations:\n"
            + "\n".join(events)
            + "\n\nCompute the EXACT state of each field at the end of the sequence.\n"
            f"Output your final answer as a valid JSON block enclosed in ```json and ```:\n"
            f"```json\n"
            f"{{\n"
            + ",\n".join(f'  "{f}": <int>' for f in fields)
            + "\n}\n```"
        )

        return BenchmarkProblem(
            id=f"2ma_cf_{seed}_{difficulty}",
            dimension=self.dimension_id,
            dimension_name=self.dimension_name,
            seed=seed,
            difficulty=difficulty,
            title=f"Counterfactual Axiomatic Deduction (Z_{modulus}, {num_steps} steps)",
            prompt=prompt,
            expected_format='JSON: {"Field": int, ...}',
            ground_truth=state,
            metadata={"modulus": modulus, "initial_state": initial_state, "steps": num_steps},
        )

    async def verify(self, problem: BenchmarkProblem, model_output: str) -> VerifierResult:
        ground_truth: Dict[str, int] = problem.ground_truth
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", model_output, re.DOTALL)
        
        extracted_data = None
        if json_match:
            try:
                extracted_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        if not extracted_data:
            first_field = list(ground_truth.keys())[0]
            raw_match = re.search(rf"\{{\s*\"{first_field}\".*?\}}", model_output, re.DOTALL)
            if raw_match:
                try:
                    extracted_data = json.loads(raw_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not extracted_data or not isinstance(extracted_data, dict):
            return VerifierResult(
                problem_id=problem.id,
                dimension=self.dimension_id,
                passed=False,
                score=0.0,
                ground_truth=ground_truth,
                failure_reason="Could not extract valid JSON state dictionary.",
            )

        correct_count = 0
        total_fields = len(ground_truth)
        mismatches = {}

        for f, true_val in ground_truth.items():
            user_val = extracted_data.get(f)
            try:
                user_val_int = int(user_val) if user_val is not None else None
            except (ValueError, TypeError):
                user_val_int = None

            if user_val_int == true_val:
                correct_count += 1
            else:
                mismatches[f] = {"expected": true_val, "got": user_val}

        passed = (correct_count == total_fields)
        score = round(correct_count / total_fields, 3)

        return VerifierResult(
            problem_id=problem.id,
            dimension=self.dimension_id,
            passed=passed,
            score=score,
            extracted_answer=extracted_data,
            ground_truth=ground_truth,
            failure_reason=None if passed else f"Field state mismatches: {mismatches}",
            details={"correct_fields": correct_count, "total_fields": total_fields, "mismatches": mismatches},
        )

    def get_oracle_solution(self, problem: BenchmarkProblem) -> str:
        return f"```json\n{json.dumps(problem.ground_truth, indent=2)}\n```"
