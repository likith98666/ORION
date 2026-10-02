from uuid import uuid4

import pytest

from orion.core.swe.errors import UnverifiedSuccessError
from orion.core.swe.evaluation import (
    EvaluationCriteriaResult,
    EvaluationMetrics,
    EvaluationStatus,
    MissionEvaluation,
    SWEEvaluator,
)
from orion.core.swe.evidence import (
    EvidenceCategory,
    EvidenceLedger,
    SWEReport,
)
from orion.core.swe.stages import SWETaskStage

ALL_STAGES = (
    SWETaskStage.INSPECT_REPOSITORY,
    SWETaskStage.ANALYZE_FAILURE,
    SWETaskStage.FORMULATE_FIX,
    SWETaskStage.IMPLEMENT_CHANGE,
    SWETaskStage.RUN_TESTS,
    SWETaskStage.VERIFY,
)


def _build_passing_ledger() -> EvidenceLedger:
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        source="tool:list_files",
        content="Files listed",
        category=EvidenceCategory.REPOSITORY_STATE,
        metadata={"path": "."},
    )
    ledger.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent:debugger",
        content="Diagnosed root cause",
        category=EvidenceCategory.DIAGNOSTIC_RESULT,
    )
    ledger.record_claimed(
        stage=SWETaskStage.FORMULATE_FIX,
        source="agent:formulator",
        content="Proposed fix",
        category=EvidenceCategory.PROPOSED_CHANGE,
    )
    ledger.record_observed(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        source="tool:write_file",
        content="File written",
        category=EvidenceCategory.FILE_CHANGE,
        metadata={"path": "src/fix.py"},
    )
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Tests executed: 1 passed",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"exit_code": 0, "status": "passed"},
    )
    ledger.record_verified(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification PASSED",
        category=EvidenceCategory.VERIFICATION_RESULT,
    )
    return ledger


def test_evaluation_pass_when_all_criteria_met():
    """Verify SWEEvaluator returns PASS when workflow, tests, and verification succeed."""
    ledger = _build_passing_ledger()
    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    assert evaluation.status == EvaluationStatus.PASS
    assert evaluation.criteria.workflow_completed is True
    assert evaluation.criteria.test_passed is True
    assert evaluation.criteria.verification_passed is True
    assert evaluation.criteria.evidence_complete is True
    assert evaluation.criteria.changes_traceable is True
    assert evaluation.criteria.recovery_transparent is True
    assert evaluation.metrics.verification_passed == 1
    assert evaluation.metrics.verification_failed == 0
    assert evaluation.metrics.files_changed == 1


def test_evaluation_fail_when_verification_fails():
    """Verify SWEEvaluator returns FAIL when verification fails."""
    ledger = _build_passing_ledger()
    # Add a failed verification at the end
    ledger.record_observed(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification FAILED: assertions failed",
        category=EvidenceCategory.VERIFICATION_RESULT,
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    assert evaluation.status == EvaluationStatus.FAIL
    assert evaluation.criteria.verification_passed is False
    assert evaluation.metrics.verification_failed >= 1


def test_evaluation_fail_when_validation_tests_fail():
    """Verify SWEEvaluator returns FAIL when validation tests fail."""
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="pytest failed with exit code 1",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"exit_code": 1, "status": "failed"},
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    assert evaluation.status == EvaluationStatus.FAIL
    assert evaluation.criteria.test_passed is False


def test_evaluation_inconclusive_when_workflow_incomplete():
    """Verify SWEEvaluator returns INCONCLUSIVE when workflow was aborted early."""
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        source="tool:list_files",
        content="Inspected",
        category=EvidenceCategory.REPOSITORY_STATE,
    )

    evaluator = SWEEvaluator()
    # Only completed stage 1
    evaluation = evaluator.evaluate(
        ledger=ledger,
        completed_stages=[SWETaskStage.INSPECT_REPOSITORY],
    )

    assert evaluation.status == EvaluationStatus.INCONCLUSIVE
    assert evaluation.criteria.workflow_completed is False


def test_evaluation_inconclusive_when_unverified():
    """Verify tests passing alone without verification results in INCONCLUSIVE, not PASS."""
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="All tests passed",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"exit_code": 0, "status": "passed"},
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    # Test completed != Fix verified
    assert evaluation.status == EvaluationStatus.INCONCLUSIVE
    assert evaluation.criteria.verification_passed is False


def test_evaluation_determinism():
    """Verify SWEEvaluator produces identical outputs given identical inputs."""
    ledger = _build_passing_ledger()
    evaluator = SWEEvaluator()

    runs = [evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES) for _ in range(5)]
    first_dict = runs[0].to_dict()

    for run in runs[1:]:
        assert run.to_dict() == first_dict


def test_change_traceability_requires_path():
    """Verify change traceability fails if file change metadata is missing path."""
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        source="tool:write_file",
        content="Modified file",
        category=EvidenceCategory.FILE_CHANGE,
        metadata={},  # Missing path
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    assert evaluation.criteria.changes_traceable is False


def test_recovery_transparency_preserves_attempts():
    """Verify prior failure accompanied by recovery event satisfies recovery transparency."""
    ledger = _build_passing_ledger()
    # Prior failed verification
    ledger.record_observed(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification FAILED: initial attempt",
        category=EvidenceCategory.VERIFICATION_RESULT,
    )
    # Recovery event logged
    ledger.record_observed(
        stage=SWETaskStage.VERIFY,
        source="RecoveryCoordinator",
        content="Action: retry_task",
        category=EvidenceCategory.RECOVERY_EVENT,
        metadata={"recovery_action": "retry_task", "recovery_strategy": "retry"},
    )
    # Passed verification
    ledger.record_verified(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification PASSED: retry attempt",
        category=EvidenceCategory.VERIFICATION_RESULT,
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    assert evaluation.criteria.recovery_transparent is True
    assert evaluation.metrics.recovery_attempts == 1


def test_swe_report_rejects_incompatible_evaluation_status():
    """Verify SWEReport raises UnverifiedSuccessError if status is verified_success but evaluation failed."""
    ledger = _build_passing_ledger()
    evaluator = SWEEvaluator()

    # Create failed evaluation
    failed_evaluation = MissionEvaluation(
        status=EvaluationStatus.FAIL,
        metrics=EvaluationMetrics(
            tests_passed=0,
            tests_failed=1,
            verification_passed=0,
            verification_failed=1,
            files_changed=1,
            recovery_attempts=0,
            stages_completed=6,
        ),
        criteria=EvaluationCriteriaResult(
            workflow_completed=True,
            test_passed=False,
            verification_passed=False,
            evidence_complete=False,
            changes_traceable=True,
            recovery_transparent=True,
        ),
        summary="Failed mission",
    )

    with pytest.raises(UnverifiedSuccessError) as exc_info:
        SWEReport.create(
            mission_id=uuid4(),
            task_id=uuid4(),
            workspace_root="/repo",
            ledger=ledger,
            status="verified_success",
            evaluation=failed_evaluation,
        )
    assert "Cannot mark SWE report as 'verified_success' when evaluation status is 'fail'" in str(exc_info.value)


def test_missing_required_evidence_prevents_verified_success():
    """Verify missing required evidence categories prevents EvaluationStatus.PASS and verified_success."""
    ledger = EvidenceLedger()
    # Record inspection, test, and verification, but OMIT PROPOSED_CHANGE and FILE_CHANGE
    ledger.record_observed(
        stage=SWETaskStage.INSPECT_REPOSITORY,
        source="tool:list_files",
        content="Inspected",
        category=EvidenceCategory.REPOSITORY_STATE,
    )
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Tests passed",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"exit_code": 0, "status": "passed"},
    )
    ledger.record_verified(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification PASSED",
        category=EvidenceCategory.VERIFICATION_RESULT,
    )

    evaluator = SWEEvaluator()
    # Specify that PROPOSED_CHANGE is strictly required for this mission
    evaluation = evaluator.evaluate(
        ledger=ledger,
        completed_stages=ALL_STAGES,
        required_categories=[EvidenceCategory.PROPOSED_CHANGE],
    )

    assert evaluation.criteria.evidence_complete is False
    assert evaluation.status == EvaluationStatus.INCONCLUSIVE
    assert "missing required evidence categories [proposed_change]" in " ".join(evaluation.criteria.details)

    with pytest.raises(UnverifiedSuccessError) as exc_info:
        SWEReport.create(
            mission_id=uuid4(),
            task_id=uuid4(),
            workspace_root="/repo",
            ledger=ledger,
            status="verified_success",
            evaluation=evaluation,
        )
    assert "when evaluation status is 'inconclusive'" in str(exc_info.value)


def test_failed_verification_cannot_evaluate_success():
    """Verify failed verification strictly resolves to FAIL and cannot produce verified_success."""
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Tests executed",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"exit_code": 0, "status": "passed"},
    )
    ledger.record_observed(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification FAILED: assertion mismatch",
        category=EvidenceCategory.VERIFICATION_RESULT,
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    assert evaluation.criteria.verification_passed is False
    assert evaluation.status == EvaluationStatus.FAIL
    assert evaluation.metrics.verification_failed >= 1

    with pytest.raises(UnverifiedSuccessError):
        SWEReport.create(
            mission_id=uuid4(),
            task_id=uuid4(),
            workspace_root="/repo",
            ledger=ledger,
            status="verified_success",
            evaluation=evaluation,
        )


def test_no_fabricated_metrics_and_metrics_validation():
    """Verify EvaluationMetrics rejects negative or non-integer values and validates strictly."""
    with pytest.raises(ValueError):
        EvaluationMetrics(
            tests_passed=-1,  # Negative
            tests_failed=0,
            verification_passed=1,
            verification_failed=0,
            files_changed=1,
            recovery_attempts=0,
            stages_completed=6,
        )

    with pytest.raises(ValueError):
        EvaluationMetrics(
            tests_passed=1,
            tests_failed=0,
            verification_passed=1,
            verification_failed=0,
            files_changed=1,
            recovery_attempts=0,
            stages_completed="six",  # type: ignore
        )

    metrics = EvaluationMetrics(
        tests_passed=3,
        tests_failed=1,
        verification_passed=1,
        verification_failed=1,
        files_changed=2,
        recovery_attempts=1,
        stages_completed=6,
    )
    data = metrics.to_dict()
    assert data["tests_passed"] == 3
    assert data["tests_failed"] == 1
    assert data["recovery_attempts"] == 1


def test_test_results_not_treated_as_verification():
    """Verify passing test results alone are not treated as verification and cannot pass evaluation."""
    ledger = EvidenceLedger()
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="All 25 tests passed successfully with 0 failures.",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"exit_code": 0, "status": "passed", "duration": 1.25},
    )

    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    # Invariant: tool test execution passed != outcome verified
    assert evaluation.criteria.test_passed is True
    assert evaluation.criteria.verification_passed is False
    assert evaluation.criteria.evidence_complete is False
    assert evaluation.status == EvaluationStatus.INCONCLUSIVE


def test_swe_report_structured_representation_and_helpers():
    """Verify SWEReport provides structured to_dict representation and query helpers."""
    ledger = _build_passing_ledger()
    evaluator = SWEEvaluator()
    evaluation = evaluator.evaluate(ledger=ledger, completed_stages=ALL_STAGES)

    mission_id = uuid4()
    task_id = uuid4()

    report = SWEReport.create(
        mission_id=mission_id,
        task_id=task_id,
        workspace_root="/workspaces/repo",
        ledger=ledger,
        status="verified_success",
        evaluation=evaluation,
        stages_completed=ALL_STAGES,
        files_modified=("src/fix.py",),
        summary="Mission succeeded with verified fix",
    )

    assert report.is_verified_success is True
    assert report.total_evidence_count == 6
    assert len(report.get_evidence_by_category(EvidenceCategory.TEST_RESULT)) == 1
    assert len(report.get_evidence_by_stage(SWETaskStage.VERIFY)) == 1

    report_dict = report.to_dict()
    assert report_dict["mission"]["mission_id"] == str(mission_id)
    assert report_dict["mission"]["task_id"] == str(task_id)
    assert report_dict["mission"]["status"] == "verified_success"
    assert report_dict["workspace"]["workspace_root"] == "/workspaces/repo"
    assert report_dict["stages"]["total_completed"] == len(ALL_STAGES)
    assert report_dict["changes"]["files_modified"] == ["src/fix.py"]
    assert report_dict["tests"]["tests_passed"] == 1
    assert report_dict["tests"]["outcome"] is True
    assert report_dict["verification"]["verification_passed"] == 1
    assert report_dict["verification"]["outcome"] is True
    assert report_dict["evidence_summary"]["total_items"] == 6
    assert report_dict["evaluation"]["status"] == "pass"
    assert report_dict["final_outcome"] == "verified_success"
