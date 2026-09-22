from abc import ABC, abstractmethod
from uuid import UUID

from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)


class VerificationRepository(ABC):
    @abstractmethod
    def save(self, result: VerificationResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, result_id: UUID) -> VerificationResult | None:
        raise NotImplementedError

    @abstractmethod
    def list_for_execution(
        self,
        execution_id: UUID,
    ) -> list[VerificationResult]:
        raise NotImplementedError

    @abstractmethod
    def list_by_status(
        self,
        status: VerificationStatus,
    ) -> list[VerificationResult]:
        raise NotImplementedError

    @abstractmethod
    def list_by_type(
        self,
        verification_type: VerificationType,
    ) -> list[VerificationResult]:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[VerificationResult]:
        raise NotImplementedError
