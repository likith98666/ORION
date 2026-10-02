from uuid import uuid4

import pytest

from orion.core.swe.errors import FormulationIncompleteError, UnverifiedSuccessError
from orion.core.swe.evidence import (
    EvidenceLedger,
    EvidenceLevel,
    SWEReport,
)
from orion.core.swe.formulation import ProposedFixPlan
from orion.core.swe.stages import SWETaskStage


def test_evidence_levels_are_distinct():
    """Verify CLAIMED, OBSERVED, and VERIFIED are distinct enum levels."""
    assert EvidenceLevel.CLAIMED != EvidenceLevel.OBSERVED
    assert EvidenceLevel.OBSERVED != EvidenceLevel.VERIFIED
    assert EvidenceLevel.CLAIMED != EvidenceLevel.VERIFIED

    assert EvidenceLevel.CLAIMED.value == "claimed"
    assert EvidenceLevel.OBSERVED.value == "observed"
    assert EvidenceLevel.VERIFIED.value == "verified"


def test_evidence_ledger_records_and_filters():
    """Verify EvidenceLedger correctly records and filters entries across levels and stages."""
    ledger = EvidenceLedger()

    item1 = ledger.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent:debugger",
        content="Bug is likely off-by-one error in loop index.",
    )
    assert item1.level == EvidenceLevel.CLAIMED
    assert item1.stage == SWETaskStage.ANALYZE_FAILURE

    item2 = ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="pytest failed with exit code 1",
        metadata={"exit_code": 1},
    )
    assert item2.level == EvidenceLevel.OBSERVED
    assert item2.stage == SWETaskStage.RUN_TESTS

    item3 = ledger.record_verified(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Output satisfied all required verification assertions.",
    )
    assert item3.level == EvidenceLevel.VERIFIED

    # Check queries
    assert len(ledger.get_items()) == 3
    assert len(ledger.get_items(level=EvidenceLevel.CLAIMED)) == 1
    assert len(ledger.get_items(level=EvidenceLevel.OBSERVED)) == 1
    assert len(ledger.get_items(level=EvidenceLevel.VERIFIED)) == 1

    assert ledger.has_claimed() is True
    assert ledger.has_observed() is True
    assert ledger.has_verified() is True
    assert ledger.has_verified(stage=SWETaskStage.VERIFY) is True
    assert ledger.has_verified(stage=SWETaskStage.ANALYZE_FAILURE) is False


def test_swe_report_rejects_verified_success_without_verified_evidence():
    """Verify critical invariant: cannot claim verified_success without VERIFIED evidence."""
    mission_id = uuid4()
    task_id = uuid4()
    workspace_root = "/workspace/repo"

    ledger = EvidenceLedger()
    ledger.record_claimed(
        stage=SWETaskStage.FORMULATE_FIX,
        source="agent",
        content="Agent claims fix is complete",
    )
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Test command completed with exit code 0",
    )

    # Attempting to build a report with status 'verified_success' without verified evidence must fail
    with pytest.raises(UnverifiedSuccessError) as exc_info:
        SWEReport.create(
            mission_id=mission_id,
            task_id=task_id,
            workspace_root=workspace_root,
            ledger=ledger,
            status="verified_success",
        )
    assert "without VERIFIED evidence" in str(exc_info.value)


def test_swe_report_allows_verified_success_when_verified_evidence_exists():
    """Verify SWEReport successfully validates verified_success when VERIFIED evidence is recorded."""
    mission_id = uuid4()
    task_id = uuid4()
    workspace_root = "/workspace/repo"

    ledger = EvidenceLedger()
    ledger.record_claimed(
        stage=SWETaskStage.FORMULATE_FIX,
        source="agent",
        content="Agent claims fix is complete",
    )
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="pytest finished: 5 passed",
    )
    ledger.record_verified(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification PASSED: Output satisfies all required content.",
    )

    report = SWEReport.create(
        mission_id=mission_id,
        task_id=task_id,
        workspace_root=workspace_root,
        ledger=ledger,
        status="verified_success",
    )

    assert report.status == "verified_success"
    assert len(report.claimed_evidence) == 1
    assert len(report.observed_evidence) == 1
    assert len(report.verified_evidence) == 1


def test_proposed_fix_plan_validation():
    """Verify ProposedFixPlan requires complete formulation fields."""
    with pytest.raises(FormulationIncompleteError):
        ProposedFixPlan(
            target_files=(),
            intended_modification="Fix null check",
            expected_behavior="Do not crash on None",
            validation_strategy="Run unit tests",
        )

    with pytest.raises(FormulationIncompleteError):
        ProposedFixPlan(
            target_files=("src/app.py",),
            intended_modification="",
            expected_behavior="Do not crash",
            validation_strategy="Run unit tests",
        )

    plan = ProposedFixPlan(
        target_files=("src/app.py",),
        intended_modification="Add if val is None guard",
        expected_behavior="Returns False on None",
        validation_strategy="pytest tests/test_app.py",
        constraints=("Keep backwards compatibility",),
    )
    assert plan.target_files == ("src/app.py",)
    data = plan.to_dict()
    reconstructed = ProposedFixPlan.from_dict(data)
    assert reconstructed == plan
