"""
Registry and discovery for 2MA-Bench procedural generators.
"""

from typing import Dict, List, Optional
from .base import BaseGenerator, BenchmarkProblem, VerifierResult
from .constraint_sat import ConstraintSatisfactionGenerator
from .state_machine import StateMachineGenerator
from .counterfactual import CounterfactualGenerator
from .concurrency_code import ConcurrencyGenerator
from .epistemic_trap import EpistemicTrapGenerator

_REGISTRY: Dict[str, BaseGenerator] = {
    "smt_logic": ConstraintSatisfactionGenerator(),
    "vm_emulation": StateMachineGenerator(),
    "counterfactual": CounterfactualGenerator(),
    "concurrency": ConcurrencyGenerator(),
    "epistemic": EpistemicTrapGenerator(),
}


def get_generator(dimension_id: str) -> BaseGenerator:
    """Retrieve generator instance by dimension id."""
    if dimension_id not in _REGISTRY:
        raise KeyError(f"Unknown 2MA-Bench dimension: '{dimension_id}'. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[dimension_id]


def list_dimensions() -> List[Dict[str, str]]:
    """List all registered benchmark dimensions."""
    return [
        {"id": k, "name": gen.dimension_name}
        for k, gen in _REGISTRY.items()
    ]


def generate_benchmark_suite(
    seed: int, difficulty: int = 1, dimensions: Optional[List[str]] = None
) -> List[BenchmarkProblem]:
    """Generates a complete or subset test suite with the given seed and difficulty."""
    dims = dimensions or list(_REGISTRY.keys())
    problems: List[BenchmarkProblem] = []
    for dim_id in dims:
        if dim_id in _REGISTRY:
            problems.append(_REGISTRY[dim_id].generate(seed, difficulty))
    return problems


__all__ = [
    "BaseGenerator",
    "BenchmarkProblem",
    "VerifierResult",
    "ConstraintSatisfactionGenerator",
    "StateMachineGenerator",
    "CounterfactualGenerator",
    "ConcurrencyGenerator",
    "EpistemicTrapGenerator",
    "get_generator",
    "list_dimensions",
    "generate_benchmark_suite",
]
