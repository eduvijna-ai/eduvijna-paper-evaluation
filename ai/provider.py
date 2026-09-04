"""Interfaces for the eleven operations in the AI provider contract."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

OperationInput = Mapping[str, Any]
OperationResult = Mapping[str, Any]


class AIProvider(ABC):
    """Provider-neutral operation boundary.

    Typed dataclasses will replace the temporary mapping aliases as each pipeline
    stage is implemented. Adapters must never publish scores directly.
    """

    @abstractmethod
    async def extract_student_identity(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def analyze_page(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def map_answer_regions(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def transcribe_answer(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def evaluate_rubric(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def verify_math(self, request: OperationInput) -> OperationResult:
        """Run the deterministic SymPy-backed verification operation."""
        raise NotImplementedError

    @abstractmethod
    async def classify_error(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_student_explanation(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_parent_summary(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_learning_plan(self, request: OperationInput) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_improvement_blueprint(
        self, request: OperationInput
    ) -> OperationResult:
        raise NotImplementedError
