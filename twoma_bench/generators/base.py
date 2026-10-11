"""
Base classes and contracts for 2MA-Bench procedural generators.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field


class BenchmarkProblem(BaseModel):
    """An individual procedurally generated benchmark problem instance."""
    id: str
    dimension: str
    dimension_name: str
    seed: int
    difficulty: int = 1
    title: str
    prompt: str
    system_prompt: Optional[str] = None
    expected_format: str
    ground_truth: Any
    is_impossible: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifierResult(BaseModel):
    """Deterministic result of verifying a model's response."""
    problem_id: str
    dimension: str
    passed: bool
    score: float = 0.0  # Normalized 0.0 to 1.0 (or negative for epistemic hallucination penalties)
    extracted_answer: Any = None
    ground_truth: Any = None
    failure_reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class BaseGenerator(ABC):
    """Abstract base generator for a 2MA-Bench hardness dimension."""

    @property
    @abstractmethod
    def dimension_id(self) -> str:
        """Machine identifier, e.g. 'smt_logic'."""
        pass

    @property
    @abstractmethod
    def dimension_name(self) -> str:
        """Human readable title, e.g. 'Dynamic Constraint Satisfaction (SMT)'."""
        pass

    @abstractmethod
    def generate(self, seed: int, difficulty: int = 1) -> BenchmarkProblem:
        """Procedurally generate a problem instance given a random seed and difficulty."""
        pass

    @abstractmethod
    async def verify(self, problem: BenchmarkProblem, model_output: str) -> VerifierResult:
        """Deterministically verify the model's output against the problem's ground truth."""
        pass

    def get_oracle_solution(self, problem: BenchmarkProblem) -> str:
        """Return the ideal ground-truth formatted solution (used by mock client / verification)."""
        return str(problem.ground_truth)
