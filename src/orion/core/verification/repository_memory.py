from uuid import UUID

from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.repository import VerificationRepository


class InMemoryVerificationRepository(VerificationRepository):
    def __init__(self) -> None:
        self._results: dict[UUID, VerificationResult] = {}

    def save(self, result: VerificationResult) -> None:
        self._results[result.id] = result

    def get(self, result_id: UUID) -> VerificationResult | None:
        return self._results.get(result_id)

    def list_for_execution(
        self,
        execution_id: UUID,
    ) -> list[VerificationResult]:
        return [
            result
            for result in self._results.values()
            if result.execution_id == execution_id
        ]

    def list_by_status(
        self,
        status: VerificationStatus,
    ) -> list[VerificationResult]:
        return [
            result
            for result in self._results.values()
            if result.status == status
        ]

    def list_by_type(
        self,
        verification_type: VerificationType,
    ) -> list[VerificationResult]:
        return [
            result
            for result in self._results.values()
            if result.verification_type == verification_type
        ]

    def list_all(self) -> list[VerificationResult]:
        return list(self._results.values())
