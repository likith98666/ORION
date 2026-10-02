"""Authoritative verification integration consuming concrete Phase 5 execution evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from orion.core.observability.context import TelemetryContext
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger
from orion.core.swe.execution.contracts import (
    ControlledTestResult,
    PatchApplicationResult,
    Phase5ExecutionOutcome,
    PostApplyIntegrityResult,
)
from orion.core.swe.execution.states import PatchExecutionState
from orion.core.swe.stages import SWETaskStage
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import VerificationResult, VerificationStatus, VerificationType


class PatchVerificationAuthority:
    """Sole authority certifying whether a patch execution satisfies verification criteria."""

    def __init__(
        self,
        verification_engine: VerificationEngine,
        recovery_coordinator: RecoveryCoordinator | None = None,
        ledger: EvidenceLedger | None = None,
        telemetry_context: TelemetryContext | None = None,
    ) -> None:
        if not isinstance(verification_engine, VerificationEngine):
            raise TypeError("verification_engine must be a VerificationEngine instance.")

        self._verification_engine = verification_engine
        self._recovery_coordinator = recovery_coordinator
        self._ledger = ledger
        self._telemetry_context = telemetry_context or TelemetryContext()

    @property
    def verification_engine(self) -> VerificationEngine:
        return self._verification_engine

    @property
    def recovery_coordinator(self) -> RecoveryCoordinator | None:
        return self._recovery_coordinator

    def verify_execution(
        self,
        application_result: PatchApplicationResult,
        test_result: ControlledTestResult | None,
        integrity_result: PostApplyIntegrityResult | None = None,
        expected_requirements: list[str] | None = None,
        execution_id: UUID | None = None,
    ) -> Phase5ExecutionOutcome:
        """Evaluate concrete evidence and decide whether the patch execution is VERIFIED."""
        effective_execution_id = execution_id or application_result.execution_id or uuid4()
        reqs = expected_requirements or []

        # 1. Inspect Application Result
        if not application_result.is_applied:
            fail_type = (
                FailureType.TOOL_FAILURE
                if application_result.status in (
                    PatchExecutionState.RECOVERED,
                    PatchExecutionState.RECOVERY_FAILED,
                    PatchExecutionState.PARTIALLY_APPLIED,
                )
                else FailureType.CONSTRAINT_VIOLATION
            )
            failure = Failure(
                failure_type=fail_type,
                message=f"Patch application was not successful: {application_result.error}",
            )
            v_result = VerificationResult.create(
                execution_id=effective_execution_id,
                verification_type=VerificationType.OUTPUT,
                status=VerificationStatus.FAILED,
                reason=f"Application failure: {application_result.error}",
                metadata={"application_status": application_result.status.value},
            )
            self._record_failure_evidence(
                effective_execution_id, application_result, failure, v_result
            )

            return Phase5ExecutionOutcome(
                patch_id=application_result.patch_id,
                task_id=application_result.task_id,
                execution_id=effective_execution_id,
                lifecycle_state=application_result.status,
                application_result=application_result,
                integrity_result=integrity_result,
                test_result=test_result,
                verification_result=v_result,
                is_verified=False,
                summary=(
                    f"Execution unverified due to application failure: {application_result.error}"
                ),
                completed_at=datetime.now(UTC),
            )

        # 2. Inspect Post-Apply Integrity Result
        if integrity_result is not None and not integrity_result.valid:
            failure = Failure(
                failure_type=FailureType.VERIFICATION_FAILURE,
                message=f"Post-apply integrity discrepancy: {integrity_result.details}",
            )
            v_result = VerificationResult.create(
                execution_id=effective_execution_id,
                verification_type=VerificationType.OUTPUT,
                status=VerificationStatus.FAILED,
                reason=f"Integrity check failed: {integrity_result.details}",
                metadata=integrity_result.to_dict(),
            )
            self._record_failure_evidence(
                effective_execution_id, application_result, failure, v_result
            )

            return Phase5ExecutionOutcome(
                patch_id=application_result.patch_id,
                task_id=application_result.task_id,
                execution_id=effective_execution_id,
                lifecycle_state=PatchExecutionState.FAILED,
                application_result=application_result,
                integrity_result=integrity_result,
                test_result=test_result,
                verification_result=v_result,
                is_verified=False,
                summary=f"Integrity verification failed: {integrity_result.details}",
                completed_at=datetime.now(UTC),
            )

        # 3. Inspect Test Result
        if test_result is None or not test_result.passed:
            fail_msg = (
                "Tests were not executed"
                if test_result is None
                else f"Tests failed with exit code {test_result.exit_code}: {test_result.status}"
            )
            fail_type = (
                FailureType.TIMEOUT
                if (test_result and test_result.timed_out)
                else FailureType.VERIFICATION_FAILURE
            )
            failure = Failure(failure_type=fail_type, message=fail_msg)
            v_result = VerificationResult.create(
                execution_id=effective_execution_id,
                verification_type=VerificationType.OUTPUT,
                status=VerificationStatus.FAILED,
                reason=fail_msg,
                metadata=test_result.to_dict() if test_result else {},
            )
            self._record_failure_evidence(
                effective_execution_id, application_result, failure, v_result
            )

            return Phase5ExecutionOutcome(
                patch_id=application_result.patch_id,
                task_id=application_result.task_id,
                execution_id=effective_execution_id,
                lifecycle_state=PatchExecutionState.FAILED,
                application_result=application_result,
                integrity_result=integrity_result,
                test_result=test_result,
                verification_result=v_result,
                is_verified=False,
                summary=f"Verification failed: {fail_msg}",
                completed_at=datetime.now(UTC),
            )

        # 4. Content verification against expected requirements
        combined_output = f"{test_result.stdout}\n{test_result.stderr}".strip()
        v_result = self._verification_engine.verify_output(
            execution_id=effective_execution_id,
            output=combined_output or "passed",
            expected_requirements=reqs,
        )

        is_verified = v_result.status == VerificationStatus.PASSED
        lifecycle_state = (
            PatchExecutionState.VERIFIED if is_verified else PatchExecutionState.FAILED
        )

        if is_verified:
            # ONLY VerificationEngine can authorize VERIFIED evidence
            if self._ledger is not None:
                self._ledger.record_verified(
                    stage=SWETaskStage.VERIFY,
                    source="VerificationEngine",
                    content=f"Verification PASSED: {v_result.reason}",
                    category=EvidenceCategory.VERIFICATION_RESULT,
                    summary="Authoritative verification passed for applied patch",
                    task_id=application_result.task_id,
                    execution_id=effective_execution_id,
                    request_id=self._telemetry_context.request_id,
                    trace_id=self._telemetry_context.trace_id,
                    metadata={
                        "patch_id": str(application_result.patch_id),
                        "verification_id": str(v_result.id),
                        "requirements": reqs,
                        "test_duration": test_result.duration_seconds,
                    },
                )
            summary = "Authoritative verification PASSED for applied patch."
        else:
            failure = Failure(
                failure_type=FailureType.VERIFICATION_FAILURE,
                message=f"Output verification failed: {v_result.reason}",
            )
            self._record_failure_evidence(
                effective_execution_id, application_result, failure, v_result
            )
            summary = f"Authoritative verification FAILED: {v_result.reason}"

        return Phase5ExecutionOutcome(
            patch_id=application_result.patch_id,
            task_id=application_result.task_id,
            execution_id=effective_execution_id,
            lifecycle_state=lifecycle_state,
            application_result=application_result,
            integrity_result=integrity_result,
            test_result=test_result,
            verification_result=v_result,
            is_verified=is_verified,
            summary=summary,
            completed_at=datetime.now(UTC),
        )

    def _record_failure_evidence(
        self,
        execution_id: UUID,
        application_result: PatchApplicationResult,
        failure: Failure,
        v_result: VerificationResult,
    ) -> None:
        """Record OBSERVED failure evidence in the ledger."""
        if self._ledger is not None:
            self._ledger.record_observed(
                stage=SWETaskStage.VERIFY,
                source="VerificationEngine",
                content=f"Verification FAILED: {failure.message}",
                category=EvidenceCategory.VERIFICATION_RESULT,
                summary=f"Verification failed: {failure.message[:100]}",
                task_id=application_result.task_id,
                execution_id=execution_id,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                metadata={
                    "failure_type": failure.failure_type.value,
                    "reason": v_result.reason,
                    "verification_id": str(v_result.id),
                },
            )
