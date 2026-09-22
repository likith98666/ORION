from uuid import uuid4

import pytest

from orion.core.recovery.failures import FailureType
from orion.core.verification.failure_adapter import (
    VerificationFailureAdapter,
)
from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
    VerificationType,
)


def test_failed_verification_converts_to_recovery_failure():
    result = VerificationResult.create(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.FAILED,
        reason="Required output content was missing.",
        metadata={
            "missing_requirements": [
                "final recommendation",
            ]
        },
    )

    failure = VerificationFailureAdapter.to_failure(result)

    assert failure.failure_type == FailureType.VERIFICATION_FAILURE
    assert "Verification failed" in failure.message
    assert "Required output content was missing." in failure.message


def test_passed_verification_cannot_become_failure():
    result = VerificationResult.create(
        execution_id=uuid4(),
        verification_type=VerificationType.OUTPUT,
        status=VerificationStatus.PASSED,
        reason="All requirements were satisfied.",
    )

    with pytest.raises(
        ValueError,
        match="Only failed verification results can become failures",
    ):
        VerificationFailureAdapter.to_failure(result)


def test_invalid_verification_result_is_rejected():
    with pytest.raises(
        TypeError,
        match="VerificationResult instance",
    ):
        VerificationFailureAdapter.to_failure(None)
