"""Deterministic failure classification for ORION self-healing recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from orion.core.recovery.failures import Failure
from orion.core.swe.execution.contracts import (
    ControlledTestResult,
    PatchApplicationResult,
    PostApplyIntegrityResult,
)
from orion.core.swe.execution.errors import (
    ApprovalIntegrityError,
    RevokedApprovalError,
    StaleApprovalError,
    UnapprovedPatchError,
    WorkspaceLockedError,
)
from orion.core.verification.models import VerificationResult, VerificationStatus


class FailureCategory(str, Enum):
    """Authoritative deterministic failure classifications."""

    TEST_FAILURE = "TEST_FAILURE"
    PATCH_APPLICATION_FAILURE = "PATCH_APPLICATION_FAILURE"
    STALE_STATE = "STALE_STATE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    TIMEOUT = "TIMEOUT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    WORKSPACE_INTEGRITY_FAILURE = "WORKSPACE_INTEGRITY_FAILURE"
    APPROVAL_FAILURE = "APPROVAL_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


@dataclass(frozen=True)
class FailureClassification:
    """Authoritative classification of an SWE failure with root cause reasoning."""

    failure_id: UUID
    category: FailureCategory
    message: str
    root_causes: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)
    claimed_diagnosis: str | None = None
    model_diagnosis_matched: bool = False
    classified_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_recoverable(self) -> bool:
        return self.category not in (
            FailureCategory.APPROVAL_FAILURE,
            FailureCategory.WORKSPACE_INTEGRITY_FAILURE,
            FailureCategory.DEPENDENCY_FAILURE,
            FailureCategory.UNKNOWN_FAILURE,
        )

    @property
    def claimed_category(self) -> str | None:
        """Alias for claimed_diagnosis for API compatibility."""
        return self.claimed_diagnosis

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": str(self.failure_id),
            "category": self.category.value,
            "message": self.message,
            "root_causes": list(self.root_causes),
            "details": self.details,
            "claimed_diagnosis": self.claimed_diagnosis,
            "model_diagnosis_matched": self.model_diagnosis_matched,
            "is_recoverable": self.is_recoverable,
            "classified_at": self.classified_at.isoformat(),
        }


class FailureClassifier:
    """Deterministic classifier mapping structured errors and results to categories."""

    def classify(
        self,
        failure: Failure | Exception | str | None = None,
        application_result: PatchApplicationResult | None = None,
        test_result: ControlledTestResult | None = None,
        verification_result: VerificationResult | None = None,
        integrity_result: PostApplyIntegrityResult | None = None,
        claimed_diagnosis: str | None = None,
    ) -> FailureClassification:
        """Classify failure deterministically based on structured evidence."""
        failure_id = uuid4()
        root_causes: list[str] = []
        details: dict[str, Any] = {}
        category: FailureCategory | None = None
        message: str = ""

        # Unpack structured results passed directly as failure
        if isinstance(failure, ControlledTestResult) and test_result is None:
            test_result = failure
        elif isinstance(failure, VerificationResult) and verification_result is None:
            verification_result = failure
        elif isinstance(failure, PatchApplicationResult) and application_result is None:
            application_result = failure
        elif isinstance(failure, PostApplyIntegrityResult) and integrity_result is None:
            integrity_result = failure

        # Extract text from failure parameter if present
        fail_msg = ""
        if isinstance(failure, Failure):
            fail_msg = failure.message
            details["failure_type"] = failure.failure_type.value
        elif isinstance(failure, Exception):
            fail_msg = f"{type(failure).__name__}: {failure}"
            details["exception_type"] = type(failure).__name__
        elif isinstance(failure, str):
            fail_msg = failure
        elif test_result is not None:
            fail_msg = f"{test_result.stdout}\n{test_result.stderr}".strip()
        elif verification_result is not None:
            fail_msg = verification_result.reason
        elif application_result is not None:
            fail_msg = application_result.error or "Patch application failed"
        elif integrity_result is not None:
            fail_msg = "; ".join(integrity_result.details) or "Integrity violation"

        fail_msg_lower = fail_msg.lower()

        # 1. Approval and authorization failures
        if (
            isinstance(
                failure,
                (
                    UnapprovedPatchError,
                    RevokedApprovalError,
                    StaleApprovalError,
                    ApprovalIntegrityError,
                ),
            )
            or "unapproved" in fail_msg_lower
            or "denied" in fail_msg_lower
            or "deny" in fail_msg_lower
            or "revoked" in fail_msg_lower
            or "approval" in fail_msg_lower
            or "rejected" in fail_msg_lower
            or "reject" in fail_msg_lower
        ):
            category = FailureCategory.APPROVAL_FAILURE
            root_causes.append("Approval requirement unfulfilled or revoked")
            message = fail_msg or "Approval failed or was denied"

        # 2. Workspace integrity failures
        elif (
            (integrity_result is not None and not integrity_result.valid)
            or "workspace boundary" in fail_msg_lower
            or "traversal" in fail_msg_lower
            or "protected file" in fail_msg_lower
            or "integrity" in fail_msg_lower
            or "sha-256" in fail_msg_lower
            or "sha256" in fail_msg_lower
            or "after patch write" in fail_msg_lower
            or "post-apply" in fail_msg_lower
        ):
            category = FailureCategory.WORKSPACE_INTEGRITY_FAILURE
            root_causes.append(
                "Workspace boundary, protected file, or post-apply integrity violation"
            )
            if integrity_result and integrity_result.details:
                details["integrity_discrepancies"] = list(integrity_result.details)
            message = fail_msg or "Workspace integrity invariant violated"

        # 3. Stale workspace state / concurrency collisions
        elif (
            isinstance(failure, WorkspaceLockedError)
            or (application_result and "stale hash" in (application_result.error or "").lower())
            or "stale hash" in fail_msg_lower
            or "locked by execution" in fail_msg_lower
            or "lock collision" in fail_msg_lower
            or "workspace lock" in fail_msg_lower
            or "stale state" in fail_msg_lower
            or "stale workspace" in fail_msg_lower
        ):
            category = FailureCategory.STALE_STATE
            root_causes.append("Workspace state changed concurrently or expected hash is stale")
            message = fail_msg or "Stale workspace state detected"

        # 4. Patch application failures (syntax, file missing, disk error)
        elif (
            (application_result is not None and not application_result.is_applied)
            or "patch application" in fail_msg_lower
            or "patch apply" in fail_msg_lower
            or "not found on disk" in fail_msg_lower
            or "failed writing" in fail_msg_lower
            or "syntax error in patch" in fail_msg_lower
        ):
            category = FailureCategory.PATCH_APPLICATION_FAILURE
            root_causes.append(
                application_result.error
                if application_result and application_result.error
                else "Patch application mutation failed"
            )
            app_err = (
                application_result.error
                if application_result and application_result.error
                else "Patch application failed"
            )
            message = fail_msg or app_err

        # 5. Test execution timeouts
        elif (
            (
                test_result is not None
                and (
                    test_result.timed_out
                    or test_result.status == "timeout"
                    or test_result.exit_code == -1
                )
            )
            or "timed out" in fail_msg_lower
            or "timeoutexpired" in fail_msg_lower
        ):
            category = FailureCategory.TIMEOUT
            duration = test_result.duration_seconds if test_result else "unknown"
            root_causes.append(f"Test subprocess timed out after {duration}s")
            message = fail_msg or "Test execution exceeded timeout bound"

        # 6. Dependency failures
        elif (
            (
                test_result is not None
                and (
                    "modulenotfounderror" in test_result.stderr.lower()
                    or "no module named" in test_result.stderr.lower()
                )
            )
            or "modulenotfounderror" in fail_msg_lower
            or "importerror" in fail_msg_lower
        ):
            category = FailureCategory.DEPENDENCY_FAILURE
            root_causes.append("Required module or dependency missing from test environment")
            message = fail_msg or "Dependency failure in test environment"

        # 7. Environment failures
        elif (
            (
                test_result is not None
                and (
                    "permissionerror" in test_result.stderr.lower()
                    or "command not found" in test_result.stderr.lower()
                )
            )
            or "permissionerror" in fail_msg_lower
            or "oserror" in fail_msg_lower
        ):
            category = FailureCategory.ENVIRONMENT_FAILURE
            root_causes.append("Operating environment or permissions error encountered")
            message = fail_msg or "Environment error during execution"

        # 8. Verification failures (VerificationEngine rejected output)
        elif (
            (
                verification_result is not None
                and verification_result.status != VerificationStatus.PASSED
            )
            or "verification failed" in fail_msg_lower
            or "verification requirement" in fail_msg_lower
            or "verification failure" in fail_msg_lower
            or "not met in output" in fail_msg_lower
        ):
            category = FailureCategory.VERIFICATION_FAILURE
            reason = (
                verification_result.reason
                if verification_result
                else fail_msg or "Output verification unsatisfied"
            )
            root_causes.append(reason)
            message = fail_msg or f"VerificationEngine rejected output: {reason}"

        # 9. Test failures (exit code non-zero, assertions failed)
        elif (
            (test_result is not None and not test_result.passed)
            or (test_result is not None and test_result.exit_code != 0)
            or "assertionerror" in fail_msg_lower
            or "assertion" in fail_msg_lower
            or "failed tests" in fail_msg_lower
            or "test failure" in fail_msg_lower
            or "test failed" in fail_msg_lower
        ):
            category = FailureCategory.TEST_FAILURE
            exit_code = test_result.exit_code if test_result else "unknown"
            extracted_cause: str | None = None
            if test_result is not None and (test_result.stdout or test_result.stderr):
                for line in (test_result.stdout + "\n" + test_result.stderr).splitlines():
                    if "assertionerror" in line.lower() or "assertion" in line.lower():
                        extracted_cause = line.strip()
                        break
            if extracted_cause is None and "assertionerror" in fail_msg_lower:
                for line in fail_msg.splitlines():
                    if "assertionerror" in line.lower():
                        extracted_cause = line.strip()
                        break
            if extracted_cause:
                root_causes.append(extracted_cause)
            root_causes.append(f"Automated test suite failed with exit code {exit_code}")
            message = fail_msg or f"Test suite failed with exit code {exit_code}"

        # 10. Fallback: Unknown failure
        else:
            category = FailureCategory.UNKNOWN_FAILURE
            root_causes.append(
                "Failure details could not be mapped to a known deterministic category"
            )
            message = fail_msg or "Unknown unclassified failure"

        # Check whether claimed model diagnosis matched authoritative category
        model_matched = False
        if claimed_diagnosis:
            claimed_lower = claimed_diagnosis.lower()
            cat_keywords = {
                FailureCategory.TEST_FAILURE: ["test", "assert", "fail"],
                FailureCategory.PATCH_APPLICATION_FAILURE: ["patch", "apply", "syntax", "write"],
                FailureCategory.STALE_STATE: ["stale", "hash", "concurr", "lock"],
                FailureCategory.VERIFICATION_FAILURE: ["verif", "spec", "expect"],
                FailureCategory.TIMEOUT: ["timeout", "timed out", "slow"],
                FailureCategory.DEPENDENCY_FAILURE: ["depend", "import", "module"],
                FailureCategory.ENVIRONMENT_FAILURE: ["env", "os", "perm"],
                FailureCategory.WORKSPACE_INTEGRITY_FAILURE: ["integ", "travers", "protect"],
                FailureCategory.APPROVAL_FAILURE: ["approv", "authoriz", "deni"],
            }
            keywords = cat_keywords.get(category, [])
            model_matched = any(kw in claimed_lower for kw in keywords)

        return FailureClassification(
            failure_id=failure_id,
            category=category,
            message=message,
            root_causes=tuple(root_causes),
            details=details,
            claimed_diagnosis=claimed_diagnosis,
            model_diagnosis_matched=model_matched,
        )
