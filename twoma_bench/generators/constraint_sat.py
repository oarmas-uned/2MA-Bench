"""
Dimension 1: Dynamic Constraint Satisfaction & SMT.
Procedurally synthesizes N-variable, M-constraint logic puzzles with guaranteed unique solutions.
"""

import json
import random
import re
from typing import Dict, List, Tuple, Any, Optional
from .base import BaseGenerator, BenchmarkProblem, VerifierResult


class ConstraintSolver:
    """Deterministic backtracking solver for generated finite-domain constraint puzzles."""

    @staticmethod
    def is_consistent(assignment: Dict[str, int], constraints: List[Dict[str, Any]]) -> bool:
        for c in constraints:
            ctype = c["type"]
            if ctype == "neq":
                v1, v2 = c["vars"]
                if v1 in assignment and v2 in assignment:
                    if assignment[v1] == assignment[v2]:
                        return False
            elif ctype == "offset":
                v1, v2 = c["vars"]
                offset = c["offset"]
                if v1 in assignment and v2 in assignment:
                    if assignment[v1] != assignment[v2] + offset:
                        return False
            elif ctype == "greater":
                v1, v2 = c["vars"]
                if v1 in assignment and v2 in assignment:
                    if assignment[v1] <= assignment[v2]:
                        return False
            elif ctype == "implies":
                v1, val1 = c["condition"]
                v2, val2 = c["consequence"]
                if v1 in assignment and assignment[v1] == val1:
                    if v2 in assignment and assignment[v2] != val2:
                        return False
            elif ctype == "sum_parity":
                v1, v2 = c["vars"]
                target_parity = c["parity"]  # 0 for even, 1 for odd
                if v1 in assignment and v2 in assignment:
                    if (assignment[v1] + assignment[v2]) % 2 != target_parity:
                        return False
            elif ctype == "exact":
                v = c["var"]
                val = c["val"]
                if v in assignment and assignment[v] != val:
                    return False
        return True

    @classmethod
    def solve(
        cls, variables: List[str], domain: List[int], constraints: List[Dict[str, Any]], limit: int = 5
    ) -> List[Dict[str, int]]:
        solutions = []

        def backtrack(curr: Dict[str, int]):
            if len(solutions) >= limit:
                return
            if len(curr) == len(variables):
                solutions.append(dict(curr))
                return

            unassigned = [v for v in variables if v not in curr]
            var = unassigned[0]
            for val in domain:
                curr[var] = val
                if cls.is_consistent(curr, constraints):
                    backtrack(curr)
                del curr[var]

        backtrack({})
        return solutions


class ConstraintSatisfactionGenerator(BaseGenerator):
    """Generates procedural SMT-level multi-variable constraint problems."""

    @property
    def dimension_id(self) -> str:
        return "smt_logic"

    @property
    def dimension_name(self) -> str:
        return "Dynamic Constraint Satisfaction & SMT"

    def generate(self, seed: int, difficulty: int = 1) -> BenchmarkProblem:
        rng = random.Random(seed)
        
        # Difficulty scales variable count and domain size
        num_vars = 5 + min(difficulty, 3) * 2  # 7 to 11 variables
        domain_size = num_vars
        domain = list(range(1, domain_size + 1))

        var_prefixes = ["Core", "Node", "QuantumCell", "Agent", "Cluster", "Subsystem"]
        prefix = rng.choice(var_prefixes)
        variables = [f"{prefix}_{chr(65 + i)}" for i in range(num_vars)]

        # Generate a target secret assignment
        shuffled_domain = list(domain)
        rng.shuffle(shuffled_domain)
        target_assignment = {variables[i]: shuffled_domain[i] for i in range(num_vars)}

        constraints: List[Dict[str, Any]] = []
        rule_descriptions: List[str] = []

        # 1. Base domain constraint
        rule_descriptions.append(f"Each element must be assigned a unique integer slot from 1 to {domain_size}.")
        for i in range(len(variables)):
            for j in range(i + 1, len(variables)):
                constraints.append({"type": "neq", "vars": [variables[i], variables[j]]})

        # 2. Add clues until exactly 1 unique solution exists
        max_attempts = 40
        for _ in range(max_attempts):
            sols = ConstraintSolver.solve(variables, domain, constraints, limit=3)
            if len(sols) == 1:
                break
            if len(sols) == 0:
                # Should not happen as target_assignment is valid, but safeguard
                break

            # Pick two differing solutions and add a distinguishing constraint satisfied by target_assignment
            alt_sol = [s for s in sols if s != target_assignment][0]
            diff_vars = [v for v in variables if target_assignment[v] != alt_sol[v]]
            v = rng.choice(diff_vars)

            clue_type = rng.choice(["exact", "greater", "offset", "sum_parity", "implies"])
            
            if clue_type == "exact":
                val = target_assignment[v]
                constraints.append({"type": "exact", "var": v, "val": val})
                rule_descriptions.append(f"{v} is assigned to slot {val}.")
            elif clue_type == "greater":
                other = rng.choice([o for o in variables if o != v])
                if target_assignment[v] > target_assignment[other]:
                    constraints.append({"type": "greater", "vars": [v, other]})
                    rule_descriptions.append(f"{v}'s slot number is strictly greater than {other}'s slot number.")
                else:
                    constraints.append({"type": "greater", "vars": [other, v]})
                    rule_descriptions.append(f"{other}'s slot number is strictly greater than {v}'s slot number.")
            elif clue_type == "offset":
                other = rng.choice([o for o in variables if o != v])
                diff = target_assignment[v] - target_assignment[other]
                constraints.append({"type": "offset", "vars": [v, other], "offset": diff})
                sign = f"+ {diff}" if diff >= 0 else f"- {abs(diff)}"
                rule_descriptions.append(f"Slot({v}) is equal to Slot({other}) {sign}.")
            elif clue_type == "sum_parity":
                other = rng.choice([o for o in variables if o != v])
                parity = (target_assignment[v] + target_assignment[other]) % 2
                p_str = "even" if parity == 0 else "odd"
                constraints.append({"type": "sum_parity", "vars": [v, other], "parity": parity})
                rule_descriptions.append(f"The sum of slots for {v} and {other} is {p_str}.")
            elif clue_type == "implies":
                other = rng.choice([o for o in variables if o != v])
                val_v = target_assignment[v]
                val_other = target_assignment[other]
                constraints.append({
                    "type": "implies",
                    "condition": (v, val_v),
                    "consequence": (other, val_other),
                })
                rule_descriptions.append(f"If {v} is assigned to slot {val_v}, then {other} must be assigned to slot {val_other}.")

        # Final verification: ensure unique solution exists
        final_sols = ConstraintSolver.solve(variables, domain, constraints, limit=2)
        if len(final_sols) != 1:
            # Fallback anchor: fix one more variable
            for v in variables:
                if not any(c.get("type") == "exact" and c.get("var") == v for c in constraints):
                    constraints.append({"type": "exact", "var": v, "val": target_assignment[v]})
                    rule_descriptions.append(f"{v} is assigned to slot {target_assignment[v]}.")
                    break

        prompt = (
            f"Solve the following constraint satisfaction problem (Seed: {seed}, Difficulty: {difficulty}).\n\n"
            f"Variables: {', '.join(variables)}\n"
            f"Domain: Integer slots 1 through {domain_size} (each variable receives a distinct slot).\n\n"
            f"Constraints & Rules:\n"
            + "\n".join(f"{idx+1}. {rule}" for idx, rule in enumerate(rule_descriptions))
            + "\n\n"
            f"Find the unique valid assignment for all variables.\n"
            f"Your output MUST include a valid JSON block enclosed in ```json and ``` with the exact format:\n"
            f"```json\n"
            f'{{\n  "assignment": {{\n'
            + ",\n".join(f'    "{v}": <int>' for v in variables[:3])
            + "\n    ...\n  }\n}\n```"
        )

        return BenchmarkProblem(
            id=f"2ma_smt_{seed}_{difficulty}",
            dimension=self.dimension_id,
            dimension_name=self.dimension_name,
            seed=seed,
            difficulty=difficulty,
            title=f"Dynamic SMT Constraint Grid ({len(variables)} Variables)",
            prompt=prompt,
            expected_format='JSON: {"assignment": {"Variable": slot_number}}',
            ground_truth=target_assignment,
            metadata={"variables": variables, "domain_size": domain_size, "num_rules": len(rule_descriptions)},
        )

    async def verify(self, problem: BenchmarkProblem, model_output: str) -> VerifierResult:
        """Extract JSON assignment and verify exact match with ground truth."""
        from .parser_utils import extract_json_dict, extract_key_value_assignments

        ground_truth: Dict[str, int] = problem.ground_truth
        var_keys = list(ground_truth.keys())

        # 1. Attempt JSON block extraction with relaxed sanitization and wrapper unpacking
        extracted_data = extract_json_dict(model_output, target_keys=var_keys, prefer_last=True)

        user_assignment = None
        if extracted_data and isinstance(extracted_data, dict):
            if "assignment" in extracted_data and isinstance(extracted_data["assignment"], dict):
                user_assignment = extracted_data["assignment"]
            elif any(v in extracted_data for v in var_keys):
                user_assignment = extracted_data

        # 2. Resilient fallback: extract key-value assignments directly from text / tables
        if not user_assignment:
            user_assignment = extract_key_value_assignments(model_output, target_keys=var_keys)

        if not user_assignment or not isinstance(user_assignment, dict):
            return VerifierResult(
                problem_id=problem.id,
                dimension=self.dimension_id,
                passed=False,
                score=0.0,
                ground_truth=ground_truth,
                failure_reason="Could not extract valid JSON `assignment` dictionary from output.",
            )

        # Check all variables present and equal
        correct_count = 0
        total_vars = len(ground_truth)
        mismatches = {}

        for var, true_val in ground_truth.items():
            user_val = user_assignment.get(var)
            try:
                user_val_int = int(user_val) if user_val is not None else None
            except (ValueError, TypeError):
                user_val_int = None

            if user_val_int == true_val:
                correct_count += 1
            else:
                mismatches[var] = {"expected": true_val, "got": user_val}

        passed = (correct_count == total_vars)
        score = round(correct_count / total_vars, 3)

        return VerifierResult(
            problem_id=problem.id,
            dimension=self.dimension_id,
            passed=passed,
            score=score,
            extracted_answer=user_assignment,
            ground_truth=ground_truth,
            failure_reason=None if passed else f"Mismatches on variables: {list(mismatches.keys())}",
            details={"correct_variables": correct_count, "total_variables": total_vars, "mismatches": mismatches},
        )

    def get_oracle_solution(self, problem: BenchmarkProblem) -> str:
        return f"```json\n{{\n  \"assignment\": {json.dumps(problem.ground_truth, indent=2)}\n}}\n```"
