from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class VerificationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class VerificationType(str, Enum):
    OUTPUT = "output"
    FACTUAL = "factual"
    SCHEMA = "schema"
    POLICY = "policy"


@dataclass
class VerificationResult:
    id: UUID
    execution_id: UUID
    verification_type: VerificationType
    status: VerificationStatus
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        execution_id: UUID,
        verification_type: VerificationType,
        status: VerificationStatus,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> "VerificationResult":
        cleaned_reason = reason.strip()

        if not cleaned_reason:
            raise ValueError("Verification reason cannot be empty.")

        if len(cleaned_reason) > 5_000:
            raise ValueError(
                "Verification reason cannot exceed 5,000 characters."
            )

        return cls(
            id=uuid4(),
            execution_id=execution_id,
            verification_type=verification_type,
            status=status,
            reason=cleaned_reason,
            metadata=dict(metadata) if metadata is not None else {},
        )
