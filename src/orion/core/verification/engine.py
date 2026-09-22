from uuid import UUID

from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)
from orion.core.verification.service import VerificationService


class VerificationEngine:
    def __init__(
        self,
        verification_service: VerificationService,
    ) -> None:
        self._verification_service = verification_service

    def verify_output(
        self,
        execution_id: UUID,
        output: str | None,
        expected_requirements: list[str],
    ) -> VerificationResult:
        if output is None or not output.strip():
            return self._verification_service.record(
                execution_id=execution_id,
                verification_type=VerificationType.OUTPUT,
                status=VerificationStatus.FAILED,
                reason="Execution produced no output.",
            )

        normalized_output = output.casefold()

        missing_requirements = [
            requirement
            for requirement in expected_requirements
            if requirement.strip().casefold() not in normalized_output
        ]

        if missing_requirements:
            return self._verification_service.record(
                execution_id=execution_id,
                verification_type=VerificationType.OUTPUT,
                status=VerificationStatus.FAILED,
                reason="Output is missing required content.",
                metadata={
                    "missing_requirements": missing_requirements,
                },
            )

        return self._verification_service.record(
            execution_id=execution_id,
            verification_type=VerificationType.OUTPUT,
            status=VerificationStatus.PASSED,
            reason="Output satisfies all required content.",
            metadata={
                "requirements_checked": len(expected_requirements),
            },
        )
