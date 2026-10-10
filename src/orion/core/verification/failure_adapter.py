from orion.core.recovery.failures import Failure, FailureType
from orion.core.verification.models import (
    VerificationResult,
    VerificationStatus,
)


class VerificationFailureAdapter:
    """Converts failed verification results into recovery failures."""

    @staticmethod
    def to_failure(
        verification_result: VerificationResult,
    ) -> Failure:
        """Convert a failed verification result into a structured Failure."""

        if not isinstance(
            verification_result,
            VerificationResult,
        ):
            raise TypeError("verification_result must be a VerificationResult instance.")

        if verification_result.status != VerificationStatus.FAILED:
            raise ValueError("Only failed verification results can become failures.")

        return Failure(
            failure_type=FailureType.VERIFICATION_FAILURE,
            message=(
                f"Verification failed "
                f"({verification_result.verification_type.value}): "
                f"{verification_result.reason}"
            ),
        )
