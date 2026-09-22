from uuid import uuid4

import pytest

from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)


def test_create_verification_result() -> None:
    execution_id = uuid4()

    result = VerificationResult.create(
        execution_id=execution_id,
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="Output satisfies the expected requirements.",
        metadata={"score": 1.0},
    )

    assert result.execution_id == execution_id
    assert result.verification_type == VerificationType.OUTPUT
    assert result.status == VerificationStatus.PASSED
    assert result.reason == "Output satisfies the expected requirements."
    assert result.metadata == {"score": 1.0}


def test_verification_result_strips_reason() -> None:
    result = VerificationResult.create(
        execution_id=uuid4(),
        verification_type=VerificationType.SCHEMA,
        status=VerificationStatus.PASSED,
        reason="  Valid schema  ",
    )

    assert result.reason == "Valid schema"


def test_verification_result_rejects_empty_reason() -> None:
    with pytest.raises(
        ValueError,
        match="Verification reason cannot be empty.",
    ):
        VerificationResult.create(
            execution_id=uuid4(),
            verification_type=VerificationType.OUTPUT,
            status=VerificationStatus.FAILED,
            reason="   ",
        )


def test_verification_result_rejects_long_reason() -> None:
    with pytest.raises(
        ValueError,
        match="Verification reason cannot exceed 5,000 characters.",
    ):
        VerificationResult.create(
            execution_id=uuid4(),
            verification_type=VerificationType.OUTPUT,
            status=VerificationStatus.FAILED,
            reason="x" * 5_001,
        )


def test_verification_result_copies_metadata() -> None:
    metadata = {"source": "test"}

    result = VerificationResult.create(
        execution_id=uuid4(),
        verification_type=VerificationType.FACTUAL,
        status=VerificationStatus.PENDING,
        reason="Verification is pending.",
        metadata=metadata,
    )

    metadata["changed"] = True

    assert result.metadata == {"source": "test"}


def test_verification_types_are_supported() -> None:
    assert {
        VerificationType.OUTPUT,
        VerificationType.FACTUAL,
        VerificationType.SCHEMA,
        VerificationType.POLICY,
    } == set(VerificationType)


def test_verification_statuses_are_supported() -> None:
    assert {
        VerificationStatus.PENDING,
        VerificationStatus.PASSED,
        VerificationStatus.FAILED,
    } == set(VerificationStatus)
