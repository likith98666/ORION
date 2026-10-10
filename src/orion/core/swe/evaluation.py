from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from orion.core.swe.evidence import (
    EvidenceCategory,
    EvidenceLedger,
    EvidenceLevel,
)
from orion.core.swe.stages import SWETaskStage


class EvaluationStatus(str, Enum):
    """Overall outcome evaluation of an autonomous software engineering mission."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class EvaluationMetrics:
    """Measurable metrics derived strictly from actual execution and evidence data."""

    tests_passed: int
    tests_failed: int
    verification_passed: int
    verification_failed: int
    files_changed: int
    recovery_attempts: int
    stages_completed: int

    def __post_init__(self) -> None:
        for field_name in (
            "tests_passed",
            "tests_failed",
            "verification_passed",
            "verification_failed",
            "files_changed",
            "recovery_attempts",
            "stages_completed",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"{field_name} must be a non-negative integer.")

    def to_dict(self) -> dict[str, int]:
        """Convert metrics to dictionary."""
        return {
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "verification_passed": self.verification_passed,
            "verification_failed": self.verification_failed,
            "files_changed": self.files_changed,
            "recovery_attempts": self.recovery_attempts,
            "stages_completed": self.stages_completed,
        }


@dataclass(frozen=True)
class EvaluationCriteriaResult:
    """Detailed boolean evaluation against the 6 core SWE mission criteria."""

    workflow_completed: bool
    test_passed: bool
    verification_passed: bool
    evidence_complete: bool
    changes_traceable: bool
    recovery_transparent: bool
    details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert criteria results to dictionary."""
        return {
            "workflow_completed": self.workflow_completed,
            "test_passed": self.test_passed,
            "verification_passed": self.verification_passed,
            "evidence_complete": self.evidence_complete,
            "changes_traceable": self.changes_traceable,
            "recovery_transparent": self.recovery_transparent,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class MissionEvaluation:
    """Deterministic, structured evaluation result for an SWE mission."""

    status: EvaluationStatus
    metrics: EvaluationMetrics
    criteria: EvaluationCriteriaResult
    summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvaluationStatus):
            raise TypeError("status must be an EvaluationStatus instance.")
        if not isinstance(self.metrics, EvaluationMetrics):
            raise TypeError("metrics must be an EvaluationMetrics instance.")
        if not isinstance(self.criteria, EvaluationCriteriaResult):
            raise TypeError("criteria must be an EvaluationCriteriaResult instance.")
        if not self.summary or not self.summary.strip():
            raise ValueError("summary cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        """Convert evaluation to serializable dictionary."""
        return {
            "status": self.status.value,
            "metrics": self.metrics.to_dict(),
            "criteria": self.criteria.to_dict(),
            "summary": self.summary,
        }


CANONICAL_REQUIRED_STAGES: tuple[SWETaskStage, ...] = (
    SWETaskStage.INSPECT_REPOSITORY,
    SWETaskStage.ANALYZE_FAILURE,
    SWETaskStage.FORMULATE_FIX,
    SWETaskStage.IMPLEMENT_CHANGE,
    SWETaskStage.RUN_TESTS,
    SWETaskStage.VERIFY,
)

CANONICAL_REQUIRED_CATEGORIES: tuple[EvidenceCategory, ...] = (
    EvidenceCategory.REPOSITORY_STATE,
    EvidenceCategory.DIAGNOSTIC_RESULT,
    EvidenceCategory.PROPOSED_CHANGE,
    EvidenceCategory.FILE_CHANGE,
    EvidenceCategory.TEST_RESULT,
    EvidenceCategory.VERIFICATION_RESULT,
)


class SWEEvaluator:
    """Deterministic, rule-based evaluator for Autonomous Software Engineering missions."""

    def evaluate(
        self,
        ledger: EvidenceLedger,
        completed_stages: Sequence[SWETaskStage],
        required_stages: Sequence[SWETaskStage] | None = None,
        required_categories: Sequence[EvidenceCategory] | None = None,
    ) -> MissionEvaluation:
        """Evaluate an SWE mission using measurable criteria derived strictly from evidence."""
        if not isinstance(ledger, EvidenceLedger):
            raise TypeError("ledger must be an EvidenceLedger instance.")

        expected_stages = tuple(required_stages or CANONICAL_REQUIRED_STAGES)
        completed_set = set(completed_stages)

        details: list[str] = []

        # 1. Workflow completion
        missing_stages = [stage.value for stage in expected_stages if stage not in completed_set]
        workflow_completed = len(missing_stages) == 0
        if workflow_completed:
            details.append("Workflow completed: all required stages were executed.")
        else:
            details.append(f"Workflow incomplete: missing stages [{', '.join(missing_stages)}].")

        # 2. Test outcomes
        test_items = ledger.get_items(category=EvidenceCategory.TEST_RESULT)
        validation_tests = [
            item
            for item in test_items
            if item.stage in (SWETaskStage.RUN_TESTS, SWETaskStage.VERIFY)
        ]

        tests_passed_count = sum(
            1
            for item in test_items
            if item.metadata.get("exit_code") == 0 or item.metadata.get("status") == "passed"
        )
        tests_failed_count = sum(
            1
            for item in test_items
            if (
                item.metadata.get("exit_code") not in (0, None)
                or item.metadata.get("status") == "failed"
            )
        )

        test_passed = False
        if validation_tests:
            latest_val_test = validation_tests[-1]
            if (
                latest_val_test.metadata.get("exit_code") == 0
                or latest_val_test.metadata.get("status") == "passed"
            ):
                test_passed = True
                details.append("Test outcome: validation test execution succeeded.")
            else:
                details.append("Test outcome: validation test execution failed.")
        elif test_items:
            latest_test = test_items[-1]
            if (
                latest_test.metadata.get("exit_code") == 0
                or latest_test.metadata.get("status") == "passed"
            ):
                test_passed = True
                details.append("Test outcome: latest test execution succeeded.")
            else:
                details.append("Test outcome: test execution failed.")
        else:
            # If no tests executed, mark true only if verification engine directly verified
            verif_passed_check = ledger.has_verified(SWETaskStage.VERIFY)
            test_passed = verif_passed_check
            if verif_passed_check:
                details.append("Test outcome: verified via direct verification.")
            else:
                details.append("Test outcome: no test execution evidence recorded.")

        # 3. Verification outcomes
        verif_items = ledger.get_items(category=EvidenceCategory.VERIFICATION_RESULT)
        verification_passed_count = sum(
            1 for item in verif_items if item.level == EvidenceLevel.VERIFIED
        )
        verification_failed_count = sum(
            1
            for item in verif_items
            if item.level == EvidenceLevel.OBSERVED and "FAILED" in item.content
        )

        verification_passed = False
        if verif_items:
            latest_verif = verif_items[-1]
            if latest_verif.level == EvidenceLevel.VERIFIED:
                verification_passed = True
                details.append("Verification outcome: authoritative verification passed.")
            else:
                details.append("Verification outcome: authoritative verification failed.")
        else:
            details.append("Verification outcome: no verification evidence recorded.")

        # 4. Changes and traceability
        change_items = ledger.get_items(category=EvidenceCategory.FILE_CHANGE)
        unique_files: set[str] = set()
        changes_traceable = True

        for item in change_items:
            path = item.metadata.get("path")
            if path and isinstance(path, str):
                unique_files.add(path)
            else:
                changes_traceable = False

        if change_items:
            if changes_traceable:
                details.append(
                    f"Change traceability: {len(unique_files)} file(s) modified with "
                    "traceable paths."
                )
            else:
                details.append(
                    "Change traceability: untraceable file change detected (missing path metadata)."
                )
        else:
            details.append("Change traceability: no file changes recorded.")

        files_changed_count = len(unique_files)

        # 5. Recovery transparency
        recovery_items = ledger.get_items(category=EvidenceCategory.RECOVERY_EVENT)
        recovery_attempts_count = len(recovery_items)

        recovery_transparent = True
        # If verification failed previously before succeeding, recovery events must exist
        if verification_failed_count > 0 and verification_passed:
            if recovery_attempts_count == 0:
                recovery_transparent = False
                details.append(
                    "Recovery transparency: verification failed previously but no recovery event "
                    "was logged."
                )
            else:
                details.append(
                    f"Recovery transparency: {recovery_attempts_count} recovery attempt(s) "
                    "preserved in audit."
                )
        elif recovery_attempts_count > 0:
            details.append(
                f"Recovery transparency: {recovery_attempts_count} recovery attempt(s) "
                "preserved in audit."
            )
        else:
            details.append("Recovery transparency: no recovery events required or logged.")

        # 6. Evidence completeness check
        has_verified_verif = verification_passed_count > 0

        missing_categories: list[str] = []
        if required_categories is not None:
            for cat in required_categories:
                if not ledger.get_items(category=cat):
                    missing_categories.append(cat.value)

        categories_satisfied = len(missing_categories) == 0

        # Evidence completeness requires verified evidence, traceable changes,
        # transparent recovery, and any specified required categories
        evidence_complete = (
            has_verified_verif
            and changes_traceable
            and recovery_transparent
            and categories_satisfied
        )
        if evidence_complete:
            details.append(
                "Evidence completeness: verified outcome and required supporting evidence present."
            )
        else:
            if not has_verified_verif:
                details.append("Evidence completeness: missing authoritative VERIFIED evidence.")
            if missing_categories:
                cats_str = ", ".join(missing_categories)
                details.append(
                    f"Evidence completeness: missing required evidence categories [{cats_str}]."
                )
            if not changes_traceable:
                details.append("Evidence completeness: changes are not traceable.")
            if not recovery_transparent:
                details.append("Evidence completeness: recovery attempts are not transparent.")

        # Compile metrics
        metrics = EvaluationMetrics(
            tests_passed=tests_passed_count,
            tests_failed=tests_failed_count,
            verification_passed=verification_passed_count,
            verification_failed=verification_failed_count,
            files_changed=files_changed_count,
            recovery_attempts=recovery_attempts_count,
            stages_completed=len(completed_stages),
        )

        criteria = EvaluationCriteriaResult(
            workflow_completed=workflow_completed,
            test_passed=test_passed,
            verification_passed=verification_passed,
            evidence_complete=evidence_complete,
            changes_traceable=changes_traceable,
            recovery_transparent=recovery_transparent,
            details=tuple(details),
        )

        # Status resolution
        if (
            workflow_completed
            and test_passed
            and verification_passed
            and evidence_complete
            and changes_traceable
            and recovery_transparent
        ):
            status = EvaluationStatus.PASS
            summary = (
                "Mission evaluation passed: workflow completed, tests passed, and outcome verified."
            )
        elif (verification_failed_count > 0 and not verification_passed) or (
            test_items and not test_passed
        ):
            status = EvaluationStatus.FAIL
            summary = "Mission evaluation failed: unrecovered test or verification failure."
        else:
            status = EvaluationStatus.INCONCLUSIVE
            summary = (
                "Mission evaluation inconclusive: incomplete workflow or missing verification."
            )

        return MissionEvaluation(
            status=status,
            metrics=metrics,
            criteria=criteria,
            summary=summary,
        )
