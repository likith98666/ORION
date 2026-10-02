from uuid import uuid4

import pytest

from orion.core.swe.evidence import (
    MAX_EVIDENCE_CONTENT_LENGTH,
    EvidenceCategory,
    EvidenceItem,
    EvidenceLedger,
    EvidenceLevel,
    _sanitize_metadata,
)
from orion.core.swe.stages import SWETaskStage


def test_evidence_categories_taxonomy():
    """Verify all 11 canonical evidence categories exist in the taxonomy."""
    expected_categories = {
        "repository_state",
        "file_observation",
        "diagnostic_result",
        "proposed_change",
        "file_change",
        "command_result",
        "test_result",
        "diff_result",
        "verification_result",
        "recovery_event",
        "mission_outcome",
    }
    actual_categories = {cat.value for cat in EvidenceCategory}
    assert expected_categories == actual_categories


def test_evidence_item_provenance_fields():
    """Verify evidence item retains full execution provenance."""
    task_id = uuid4()
    exec_id = uuid4()
    trace_id = uuid4()
    req_id = uuid4()

    item = EvidenceItem(
        id=uuid4(),
        level=EvidenceLevel.OBSERVED,
        category=EvidenceCategory.REPOSITORY_STATE,
        stage=SWETaskStage.INSPECT_REPOSITORY,
        source="tool:list_files",
        content="Found 12 source files",
        summary="Inspection summary",
        task_id=task_id,
        execution_id=exec_id,
        tool_name="list_files",
        request_id=req_id,
        trace_id=trace_id,
        workspace_root="/workspaces/repo",
        metadata={"total_count": 12},
    )

    assert item.level == EvidenceLevel.OBSERVED
    assert item.category == EvidenceCategory.REPOSITORY_STATE
    assert item.task_id == task_id
    assert item.execution_id == exec_id
    assert item.tool_name == "list_files"
    assert item.request_id == req_id
    assert item.trace_id == trace_id
    assert item.workspace_root == "/workspaces/repo"


def test_evidence_content_bounding():
    """Verify oversized evidence content is safely bounded to prevent memory explosion."""
    huge_content = "X" * (MAX_EVIDENCE_CONTENT_LENGTH + 5000)

    item = EvidenceItem(
        id=uuid4(),
        level=EvidenceLevel.OBSERVED,
        category=EvidenceCategory.TEST_RESULT,
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content=huge_content,
    )

    assert len(item.content) <= MAX_EVIDENCE_CONTENT_LENGTH + 50
    assert "... [TRUNCATED]" in item.content


def test_metadata_sanitization_redacts_secrets():
    """Verify sensitive keys in metadata are automatically redacted."""
    raw_metadata = {
        "api_key": "sk-1234567890abcdef",
        "password": "super-secret-password",
        "auth_token": "Bearer abcdef12345",
        "safe_key": "safe_value",
        "nested": {
            "secret_key": "hidden_value",
            "normal_number": 42,
        },
    }

    sanitized = _sanitize_metadata(raw_metadata)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["safe_key"] == "safe_value"
    assert sanitized["nested"]["secret_key"] == "[REDACTED]"
    assert sanitized["nested"]["normal_number"] == 42


def test_evidence_ledger_filtering_by_provenance():
    """Verify EvidenceLedger can query items by level, category, stage, execution, and task."""
    ledger = EvidenceLedger()
    task_id_1 = uuid4()
    task_id_2 = uuid4()
    exec_id_1 = uuid4()
    exec_id_2 = uuid4()

    ledger.record(
        level=EvidenceLevel.CLAIMED,
        stage=SWETaskStage.FORMULATE_FIX,
        source="agent:formulator",
        content="Proposed patch",
        category=EvidenceCategory.PROPOSED_CHANGE,
        task_id=task_id_1,
        execution_id=exec_id_1,
    )
    ledger.record(
        level=EvidenceLevel.OBSERVED,
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        source="tool:write_file",
        content="Modified src/core.py",
        category=EvidenceCategory.FILE_CHANGE,
        task_id=task_id_1,
        execution_id=exec_id_1,
        metadata={"path": "src/core.py"},
    )
    ledger.record(
        level=EvidenceLevel.OBSERVED,
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Test run failed",
        category=EvidenceCategory.TEST_RESULT,
        task_id=task_id_1,
        execution_id=exec_id_1,
        metadata={"exit_code": 1},
    )
    ledger.record(
        level=EvidenceLevel.OBSERVED,
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Test run passed",
        category=EvidenceCategory.TEST_RESULT,
        task_id=task_id_2,
        execution_id=exec_id_2,
        metadata={"exit_code": 0},
    )
    ledger.record(
        level=EvidenceLevel.VERIFIED,
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verification PASSED",
        category=EvidenceCategory.VERIFICATION_RESULT,
        task_id=task_id_2,
        execution_id=exec_id_2,
    )

    # Filter by level
    assert len(ledger.get_items(level=EvidenceLevel.CLAIMED)) == 1
    assert len(ledger.get_items(level=EvidenceLevel.OBSERVED)) == 3
    assert len(ledger.get_items(level=EvidenceLevel.VERIFIED)) == 1

    # Filter by category
    assert len(ledger.get_items(category=EvidenceCategory.TEST_RESULT)) == 2
    assert len(ledger.get_items(category=EvidenceCategory.FILE_CHANGE)) == 1
    assert len(ledger.get_items(category=EvidenceCategory.PROPOSED_CHANGE)) == 1

    # Filter by execution_id
    assert len(ledger.get_items(execution_id=exec_id_1)) == 3
    assert len(ledger.get_items(execution_id=exec_id_2)) == 2

    # Filter by task_id
    assert len(ledger.get_items(task_id=task_id_1)) == 3
    assert len(ledger.get_items(task_id=task_id_2)) == 2


def test_evidence_ledger_clear():
    """Verify EvidenceLedger can be cleared cleanly."""
    ledger = EvidenceLedger()
    ledger.record_claimed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="agent",
        content="Claim",
    )
    assert len(ledger.get_items()) == 1
    ledger.clear()
    assert len(ledger.get_items()) == 0


def test_evidence_levels_strict_separation():
    """Verify CLAIMED, OBSERVED, and VERIFIED remain strictly separated across ledger operations."""
    ledger = EvidenceLedger()

    item_claimed = ledger.record_claimed(
        stage=SWETaskStage.FORMULATE_FIX,
        source="agent:formulator",
        content="Fix claim",
    )
    item_observed = ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Test observation",
    )
    item_verified = ledger.record_verified(
        stage=SWETaskStage.VERIFY,
        source="VerificationEngine",
        content="Verified result",
    )

    assert item_claimed.level == EvidenceLevel.CLAIMED
    assert item_observed.level == EvidenceLevel.OBSERVED
    assert item_verified.level == EvidenceLevel.VERIFIED

    # Assert ledger level queries strictly isolate levels
    claimed_items = ledger.get_items(level=EvidenceLevel.CLAIMED)
    observed_items = ledger.get_items(level=EvidenceLevel.OBSERVED)
    verified_items = ledger.get_items(level=EvidenceLevel.VERIFIED)

    assert len(claimed_items) == 1 and claimed_items[0] == item_claimed
    assert len(observed_items) == 1 and observed_items[0] == item_observed
    assert len(verified_items) == 1 and verified_items[0] == item_verified

    assert item_claimed not in observed_items
    assert item_claimed not in verified_items
    assert item_observed not in verified_items


def test_evidence_filtering_by_stage():
    """Verify evidence can be queried and filtered by stage."""
    ledger = EvidenceLedger()
    ledger.record_claimed(stage=SWETaskStage.ANALYZE_FAILURE, source="agent", content="Claim 1")
    ledger.record_claimed(stage=SWETaskStage.FORMULATE_FIX, source="agent", content="Claim 2")
    ledger.record_observed(stage=SWETaskStage.RUN_TESTS, source="tool", content="Test result")

    assert len(ledger.get_items(stage=SWETaskStage.ANALYZE_FAILURE)) == 1
    assert len(ledger.get_items(stage=SWETaskStage.FORMULATE_FIX)) == 1
    assert len(ledger.get_items(stage=SWETaskStage.RUN_TESTS)) == 1
    assert len(ledger.get_items(stage=SWETaskStage.VERIFY)) == 0


def test_evidence_item_to_dict_and_from_dict():
    """Verify EvidenceItem serializes to and deserializes from dictionary preserving provenance."""
    task_id = uuid4()
    exec_id = uuid4()
    req_id = uuid4()
    trace_id = uuid4()

    original = EvidenceItem(
        id=uuid4(),
        level=EvidenceLevel.OBSERVED,
        category=EvidenceCategory.FILE_CHANGE,
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        source="tool:write_file",
        content="Wrote 100 bytes",
        summary="File write summary",
        task_id=task_id,
        execution_id=exec_id,
        tool_name="write_file",
        request_id=req_id,
        trace_id=trace_id,
        workspace_root="/ws",
        metadata={"path": "src/main.py", "bytes_written": 100},
    )

    data = original.to_dict()
    assert data["level"] == "observed"
    assert data["category"] == "file_change"
    assert data["stage"] == "implement_change"
    assert data["task_id"] == str(task_id)
    assert data["execution_id"] == str(exec_id)
    assert data["tool_name"] == "write_file"

    reconstructed = EvidenceItem.from_dict(data)
    assert reconstructed.id == original.id
    assert reconstructed.level == original.level
    assert reconstructed.category == original.category
    assert reconstructed.stage == original.stage
    assert reconstructed.task_id == original.task_id
    assert reconstructed.execution_id == original.execution_id
    assert reconstructed.tool_name == original.tool_name
    assert reconstructed.request_id == original.request_id
    assert reconstructed.trace_id == original.trace_id
    assert reconstructed.workspace_root == original.workspace_root
    assert reconstructed.metadata == original.metadata


def test_metadata_sanitization_truncates_large_strings():
    """Verify excessively large metadata string values are safely truncated."""
    raw = {
        "huge_key": "A" * 6000,
        "list_huge": ["B" * 5000, "safe_entry"],
    }
    sanitized = _sanitize_metadata(raw)
    assert sanitized["huge_key"].endswith("... [TRUNCATED]")
    assert len(sanitized["huge_key"]) <= 4096 + 30
    assert sanitized["list_huge"][0].endswith("... [TRUNCATED]")
    assert sanitized["list_huge"][1] == "safe_entry"


def test_evidence_item_validation_errors():
    """Verify invalid EvidenceItem construction triggers TypeError or ValueError."""
    with pytest.raises(TypeError):
        EvidenceItem(
            id=uuid4(),
            level="invalid_level",  # type: ignore
            category=EvidenceCategory.COMMAND_RESULT,
            stage=SWETaskStage.INSPECT_REPOSITORY,
            source="source",
            content="content",
        )

    with pytest.raises(TypeError):
        EvidenceItem(
            id=uuid4(),
            level=EvidenceLevel.OBSERVED,
            category="invalid_category",  # type: ignore
            stage=SWETaskStage.INSPECT_REPOSITORY,
            source="source",
            content="content",
        )

    with pytest.raises(ValueError):
        EvidenceItem(
            id=uuid4(),
            level=EvidenceLevel.OBSERVED,
            category=EvidenceCategory.COMMAND_RESULT,
            stage=SWETaskStage.INSPECT_REPOSITORY,
            source="",  # Empty source
            content="content",
        )

    with pytest.raises(ValueError):
        EvidenceItem(
            id=uuid4(),
            level=EvidenceLevel.OBSERVED,
            category=EvidenceCategory.COMMAND_RESULT,
            stage=SWETaskStage.INSPECT_REPOSITORY,
            source="source",
            content="   ",  # Empty content
        )
