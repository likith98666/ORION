from uuid import UUID

from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.repository import VerificationRepository


class VerificationService:
    def __init__(
        self,
        repository: VerificationRepository,
    ) -> None:
        self._repository = repository

    def record(
        self,
        execution_id: UUID,
        verification_type: VerificationType,
        status: VerificationStatus,
        reason: str,
        metadata: dict | None = None,
    ) -> VerificationResult:
        result = VerificationResult.create(
            execution_id=execution_id,
            verification_type=verification_type,
            status=status,
            reason=reason,
            metadata=metadata,
        )

        self._repository.save(result)

        return result

    def get(
        self,
        result_id: UUID,
    ) -> VerificationResult | None:
        return self._repository.get(result_id)

    def list_for_execution(
        self,
        execution_id: UUID,
    ) -> list[VerificationResult]:
        return self._repository.list_for_execution(execution_id)

    def list_by_status(
        self,
        status: VerificationStatus,
    ) -> list[VerificationResult]:
        return self._repository.list_by_status(status)

    def list_by_type(
        self,
        verification_type: VerificationType,
    ) -> list[VerificationResult]:
        return self._repository.list_by_type(verification_type)

    def list_all(self) -> list[VerificationResult]:
        return self._repository.list_all()
