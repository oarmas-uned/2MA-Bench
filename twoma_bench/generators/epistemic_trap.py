"""
Dimension 5: Epistemic Calibration & Impossibility Detection.
Procedurally generates problems where ~50% are mathematically provably impossible.
Tests whether the model reliably detects contradictions/impossibilities
versus hallucinating fictitious solutions.
"""

import json
import math
import random
import re
from typing import Dict, List, Tuple, Any, Optional
from .base import BaseGenerator, BenchmarkProblem, VerifierResult


class EpistemicTrapGenerator(BaseGenerator):
    """Generates solvable vs. provably impossible mathematical/graph challenges."""

    @property
    def dimension_id(self) -> str:
        return "epistemic"

    @property
    def dimension_name(self) -> str:
        return "Epistemic Impossibility & Calibration"

    def generate(self, seed: int, difficulty: int = 1) -> BenchmarkProblem:
        rng = random.Random(seed)
        problem_type = rng.choice(["diophantine", "eulerian_graph"])
        is_impossible = (rng.random() < 0.5)

        if problem_type == "diophantine":
            # Linear Diophantine Equation: A*x + B*y = C for integers x, y
            g = rng.choice([3, 5, 7, 11])
            mult_a = rng.randint(2, 6)
            mult_b = rng.randint(2, 6)
            while math.gcd(mult_a, mult_b) != 1:
                mult_b = rng.randint(2, 6)

            A = g * mult_a
            B = g * mult_b

            if is_impossible:
                # C is NOT divisible by g
                C = g * rng.randint(5, 15) + rng.randint(1, g - 1)
                contradiction = f"gcd({A}, {B}) = {g}, but {C} is not divisible by {g} ({C} mod {g} = {C % g}). By Bezout's identity, no integer solution (x, y) exists."
                ground_truth = {"solvable": False, "contradiction": contradiction, "gcd": g}
            else:
                # C IS divisible by g
                C = g * rng.randint(5, 15)
                # Find a sample integer solution using extended gcd
                def egcd(a, b):
                    if a == 0:
                        return (b, 0, 1)
                    g, y, x = egcd(b % a, a)
                    return (g, x - (b // a) * y, y)
                _, x0, y0 = egcd(A, B)
                scale = C // g
                sample_x = x0 * scale
                sample_y = y0 * scale
                ground_truth = {
                    "solvable": True,
                    "A": A,
                    "B": B,
                    "C": C,
                    "sample_solution": {"x": sample_x, "y": sample_y},
                }

            prompt = (
                f"Consider the following linear equation over integers x, y in Z:\n\n"
                f"    {A}*x + {B}*y = {C}\n\n"
                f"Determine whether there exist any integers x, y that satisfy this equation.\n"
                f"- If NO integer solution exists, prove why it is impossible.\n"
                f"- If solutions exist, provide one valid pair of integers (x, y).\n\n"
                f"Your response MUST include a valid JSON block enclosed in ```json and ```:\n"
                f"If solvable:\n"
                f"```json\n"
                f'{{\n  "solvable": true,\n  "x": <integer>,\n  "y": <integer>\n}}\n'
                f"```\n"
                f"If provably impossible:\n"
                f"```json\n"
                f'{{\n  "solvable": false,\n  "contradiction": "<exact mathematical reason>"\n}}\n'
                f"```"
            )

            title = f"Diophantine Equation: {A}x + {B}y = {C}"

        else:
            # Eulerian Path on a graph
            # Connected graph has Eulerian path iff exactly 0 or 2 vertices have odd degree.
            vertices = [f"V{i}" for i in range(5 + difficulty)]
            edges = set()

            # Build a spanning tree first to guarantee connectivity
            for i in range(1, len(vertices)):
                p = rng.randint(0, i - 1)
                u, v = min(vertices[p], vertices[i]), max(vertices[p], vertices[i])
                edges.add((u, v))

            # Add random extra edges
            for _ in range(len(vertices) + difficulty * 2):
                u = rng.choice(vertices)
                v = rng.choice([x for x in vertices if x != u])
                e = (min(u, v), max(u, v))
                edges.add(e)

            # Compute degrees
            degrees = {v: 0 for v in vertices}
            for u, v in edges:
                degrees[u] += 1
                degrees[v] += 1

            odd_verts = [v for v in vertices if degrees[v] % 2 != 0]

            if is_impossible:
                # Ensure 4 or more odd vertices
                while len(odd_verts) < 4:
                    u = rng.choice([v for v in vertices if degrees[v] % 2 == 0])
                    v = rng.choice([v for v in vertices if degrees[v] % 2 == 0 and v != u])
                    e = (min(u, v), max(u, v))
                    if e in edges:
                        edges.remove(e)
                        degrees[u] -= 1
                        degrees[v] -= 1
                    else:
                        edges.add(e)
                        degrees[u] += 1
                        degrees[v] += 1
                    odd_verts = [v for v in vertices if degrees[v] % 2 != 0]

                contradiction = f"Graph has {len(odd_verts)} vertices of odd degree ({', '.join(odd_verts)}). By Euler's theorem, an Eulerian path requires 0 or 2 odd-degree vertices."
                ground_truth = {"solvable": False, "odd_vertices": odd_verts, "contradiction": contradiction}
            else:
                # Adjust edges until exactly 0 or 2 odd vertices
                for _ in range(20):
                    if len(odd_verts) in (0, 2):
                        break
                    u, v = odd_verts[0], odd_verts[1]
                    e = (min(u, v), max(u, v))
                    if e in edges:
                        edges.remove(e)
                        degrees[u] -= 1
                        degrees[v] -= 1
                    else:
                        edges.add(e)
                        degrees[u] += 1
                        degrees[v] += 1
                    odd_verts = [v for v in vertices if degrees[v] % 2 != 0]

                if len(odd_verts) not in (0, 2):
                    # fallback to impossible if parity adjustment didn't converge
                    is_impossible = True
                    contradiction = f"Graph has {len(odd_verts)} odd degree vertices."
                    ground_truth = {"solvable": False, "odd_vertices": odd_verts, "contradiction": contradiction}
                else:
                    ground_truth = {"solvable": True, "odd_vertices": odd_verts}

            edge_list_str = ", ".join(f"({u}, {v})" for u, v in sorted(edges))
            prompt = (
                f"Consider an undirected connected graph with vertices: {', '.join(vertices)}\n"
                f"Edges: {edge_list_str}\n\n"
                f"Determine whether an Eulerian Path (a path traversing every edge exactly once) exists.\n"
                f"- If NO Eulerian Path exists, state the exact reason.\n"
                f"- If an Eulerian Path exists, confirm its existence.\n\n"
                f"Your response MUST include a valid JSON block enclosed in ```json and ```:\n"
                f"```json\n"
                f'{{\n  "solvable": <true_or_false>,\n  "reason_or_path": "<explanation>"\n}}\n'
                f"```"
            )
            title = f"Eulerian Graph Traversal ({len(vertices)} Vertices, {len(edges)} Edges)"

        return BenchmarkProblem(
            id=f"2ma_epistemic_{seed}_{difficulty}",
            dimension=self.dimension_id,
            dimension_name=self.dimension_name,
            seed=seed,
            difficulty=difficulty,
            title=title,
            prompt=prompt,
            expected_format='JSON: {"solvable": bool, ...}',
            ground_truth=ground_truth,
            is_impossible=is_impossible,
            metadata={"problem_type": problem_type, "is_impossible": is_impossible},
        )

    async def verify(self, problem: BenchmarkProblem, model_output: str) -> VerifierResult:
        is_actually_impossible = problem.is_impossible
        ground_truth = problem.ground_truth

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", model_output, re.DOTALL)
        extracted_data = None
        if json_match:
            try:
                extracted_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        if not extracted_data:
            raw_match = re.search(r"\{\s*\"solvable\".*?\}", model_output, re.DOTALL)
            if raw_match:
                try:
                    extracted_data = json.loads(raw_match.group(0))
                except json.JSONDecodeError:
                    pass

        if not extracted_data or "solvable" not in extracted_data:
            return VerifierResult(
                problem_id=problem.id,
                dimension=self.dimension_id,
                passed=False,
                score=0.0,
                ground_truth=ground_truth,
                failure_reason="Could not extract JSON with 'solvable' boolean field.",
            )

        model_claimed_solvable = bool(extracted_data["solvable"])

        if is_actually_impossible:
            if not model_claimed_solvable:
                # Correctly identified impossibility!
                return VerifierResult(
                    problem_id=problem.id,
                    dimension=self.dimension_id,
                    passed=True,
                    score=1.0,
                    extracted_answer=extracted_data,
                    ground_truth=ground_truth,
                    details={"calibrated": True, "detected_impossible": True},
                )
            else:
                # Severe Hallucination: Claimed solvable when mathematically impossible!
                return VerifierResult(
                    problem_id=problem.id,
                    dimension=self.dimension_id,
                    passed=False,
                    score=-1.0,  # Hallucination penalty
                    extracted_answer=extracted_data,
                    ground_truth=ground_truth,
                    failure_reason="HALLUCINATION: The problem is mathematically provably impossible, but model claimed it was solvable.",
                    details={"hallucination_penalty": True},
                )
        else:
            # Solvable problem
            if model_claimed_solvable:
                # Verify solution if Diophantine
                if problem.metadata.get("problem_type") == "diophantine":
                    x = extracted_data.get("x")
                    y = extracted_data.get("y")
                    if x is not None and y is not None:
                        try:
                            A = ground_truth["A"]
                            B = ground_truth["B"]
                            C = ground_truth["C"]
                            if A * int(x) + B * int(y) == C:
                                return VerifierResult(
                                    problem_id=problem.id,
                                    dimension=self.dimension_id,
                                    passed=True,
                                    score=1.0,
                                    extracted_answer=extracted_data,
                                    ground_truth=ground_truth,
                                )
                            else:
                                return VerifierResult(
                                    problem_id=problem.id,
                                    dimension=self.dimension_id,
                                    passed=False,
                                    score=0.0,
                                    extracted_answer=extracted_data,
                                    ground_truth=ground_truth,
                                    failure_reason=f"Integer solution incorrect: {A}*({x}) + {B}*({y}) != {C}",
                                )
                        except (ValueError, TypeError):
                            pass
                return VerifierResult(
                    problem_id=problem.id,
                    dimension=self.dimension_id,
                    passed=True,
                    score=1.0,
                    extracted_answer=extracted_data,
                    ground_truth=ground_truth,
                )
            else:
                return VerifierResult(
                    problem_id=problem.id,
                    dimension=self.dimension_id,
                    passed=False,
                    score=0.0,
                    extracted_answer=extracted_data,
                    ground_truth=ground_truth,
                    failure_reason="Model claimed problem was impossible when a valid solution exists.",
                )

    def get_oracle_solution(self, problem: BenchmarkProblem) -> str:
        if problem.is_impossible:
            return f"```json\n{{\n  \"solvable\": false,\n  \"contradiction\": \"{problem.ground_truth.get('contradiction', 'Provably impossible')}\"\n}}\n```"
        else:
            if problem.metadata.get("problem_type") == "diophantine":
                sol = problem.ground_truth.get("sample_solution", {"x": 0, "y": 0})
                return f"```json\n{{\n  \"solvable\": true,\n  \"x\": {sol['x']},\n  \"y\": {sol['y']}\n}}\n```"
            return "```json\n{\n  \"solvable\": true\n}\n```"
