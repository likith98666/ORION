"""Tests for deterministic Bounded Test-Target Selection in ORION SWE workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orion.core.security import ApprovalService
from orion.core.security.approval_repository_memory import InMemoryApprovalRepository
from orion.core.swe.coordinator import SWEWorkflowCoordinator
from orion.core.swe.evidence import EvidenceCategory
from orion.core.swe.execution.contracts import ControlledTestResult, PatchApplicationResult
from orion.core.swe.execution.errors import ControlledExecutionError
from orion.core.swe.execution.runner import ControlledExecutionAuthority
from orion.core.swe.execution.selector import (
    MAX_BOUNDED_FALLBACK_COUNT,
    TestSelectionStrategy,
    TestTargetSelector,
)
from orion.core.swe.execution.states import PatchExecutionState
from orion.core.swe.stages import SWETaskStage
from orion.core.tools.executor import ToolExecutor
from orion.core.tools.memory_registry import InMemoryToolRegistry
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.repository_memory import InMemoryVerificationRepository
from orion.core.verification.service import VerificationService
from orion.core.workspace.models import Workspace


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Workspace:
    """Create an isolated temporary workspace with source and test directories."""
    repo_root = tmp_path / "test_repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    # Initialize a mock git workspace layout
    (repo_root / ".git").mkdir()
    (repo_root / "src" / "pkg").mkdir(parents=True)
    (repo_root / "tests" / "unit" / "pkg").mkdir(parents=True)
    (repo_root / "tests" / "smoke").mkdir(parents=True)

    # Populate dummy files
    (repo_root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (repo_root / "src" / "pkg" / "feature.py").write_text("def run():\n    pass\n")
    (repo_root / "tests" / "test_calc.py").write_text(
        "def test_calc_add():\n    from calc import add\n    assert add(1, 2) == 3\n"
    )
    (repo_root / "tests" / "unit" / "pkg" / "test_feature.py").write_text(
        "def test_feature():\n    assert True\n"
    )
    (repo_root / "tests" / "unit" / "pkg" / "test_other.py").write_text(
        "def test_other():\n    assert True\n"
    )
    (repo_root / "tests" / "smoke" / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n"
    )

    return Workspace.create(
        repository_root=repo_root,
    )


def _create_coordinator(workspace: Workspace) -> SWEWorkflowCoordinator:
    tool_reg = InMemoryToolRegistry()
    approval_repo = InMemoryApprovalRepository()
    approval_service = ApprovalService(repository=approval_repo)
    executor = ToolExecutor(registry=tool_reg, approval_service=approval_service)

    v_repo = InMemoryVerificationRepository()
    v_service = VerificationService(repository=v_repo)
    v_engine = VerificationEngine(verification_service=v_service)

    return SWEWorkflowCoordinator(
        workspace=workspace,
        tool_executor=executor,
        verification_engine=v_engine,
    )


class TestBoundedSelectionPointByPoint:
    """Tests A through N as specified in Section 9 of the bounded test selection specification."""

    def test_a_explicit_target_is_preserved(self, temp_workspace: Workspace):
        """A. Explicit target is preserved."""
        selector = TestTargetSelector(temp_workspace)
        result = selector.select_test_targets(explicit_target="tests/test_calc.py")

        assert result.strategy == TestSelectionStrategy.EXPLICIT_TEST_TARGET
        assert result.is_explicit is True
        assert result.is_fallback is False
        assert result.selected_tests == ("tests/test_calc.py",)
        assert result.target_spec == "tests/test_calc.py"
        assert "tests/test_calc.py" in result.reason

    def test_b_direct_source_to_test_mapping(self, temp_workspace: Workspace):
        """B. Direct source->test mapping works."""
        selector = TestTargetSelector(temp_workspace)
        result = selector.select_test_targets(affected_files=["src/calc.py"])

        assert result.strategy == TestSelectionStrategy.DIRECT_TEST_MAPPING
        assert result.is_explicit is False
        assert result.is_fallback is False
        assert "tests/test_calc.py" in result.selected_tests

    def test_c_package_mapping_works(self, temp_workspace: Workspace):
        """C. Package mapping works when direct module mapping is absent."""
        # Create a source file in pkg without a direct test_unmatched.py
        unmatched = temp_workspace.repository_root / "src" / "pkg" / "unmatched.py"
        unmatched.write_text("def unmatched(): pass\n")

        selector = TestTargetSelector(temp_workspace)
        result = selector.select_test_targets(affected_files=["src/pkg/unmatched.py"])

        assert result.strategy == TestSelectionStrategy.PACKAGE_MAPPING
        assert result.is_explicit is False
        assert result.is_fallback is False
        assert len(result.selected_tests) > 0
        assert "tests/unit/pkg/test_feature.py" in result.selected_tests
        assert "tests/unit/pkg/test_other.py" in result.selected_tests

    def test_d_failure_location_mapping_works(self, temp_workspace: Workspace):
        """D. Failure-location mapping works from failure diagnostic or task directive."""
        selector = TestTargetSelector(temp_workspace)

        # Test from explicit failure_locations
        res_loc = selector.select_test_targets(failure_locations=["src/calc.py"])
        assert res_loc.strategy == TestSelectionStrategy.FAILURE_LOCATION_MAPPING
        assert res_loc.is_explicit is False
        assert res_loc.is_fallback is False
        assert "tests/test_calc.py" in res_loc.selected_tests

        # Test from task_directive mentioning the file
        res_dir = selector.select_test_targets(
            task_directive="Investigate error reported in calc.py arithmetic"
        )
        assert res_dir.strategy == TestSelectionStrategy.FAILURE_LOCATION_MAPPING
        assert "tests/test_calc.py" in res_dir.selected_tests

    def test_e_duplicate_paths_are_removed(self, temp_workspace: Workspace):
        """E. Duplicate paths are removed."""
        selector = TestTargetSelector(temp_workspace)
        result = selector.select_test_targets(
            explicit_target=[
                "tests/test_calc.py",
                "tests/test_calc.py",
                "tests/smoke/test_smoke.py",
                "tests/test_calc.py",
            ]
        )

        assert len(result.selected_tests) == 2
        assert result.selected_tests == (
            "tests/smoke/test_smoke.py",
            "tests/test_calc.py",
        )

    def test_f_results_are_deterministic(self, temp_workspace: Workspace):
        """F. Results are deterministic across repeated runs."""
        selector = TestTargetSelector(temp_workspace)
        results = [
            selector.select_test_targets(affected_files=["src/pkg/feature.py", "src/calc.py"])
            for _ in range(5)
        ]

        first = results[0]
        for subsequent in results[1:]:
            assert subsequent.selected_tests == first.selected_tests
            assert subsequent.strategy == first.strategy
            assert subsequent.target_spec == first.target_spec
            assert subsequent.reason == first.reason

    def test_g_paths_outside_workspace_are_rejected(self, temp_workspace: Workspace):
        """G. Paths outside workspace are rejected."""
        selector = TestTargetSelector(temp_workspace)

        outside_target = str(temp_workspace.repository_root.parent / "outside_test.py")
        with pytest.raises(ControlledExecutionError, match="escapes workspace boundary"):
            selector.select_test_targets(explicit_target=outside_target)

    def test_h_path_traversal_is_rejected(self, temp_workspace: Workspace):
        """H. Path traversal is rejected."""
        selector = TestTargetSelector(temp_workspace)

        with pytest.raises(ControlledExecutionError, match="forbidden sequences"):
            selector.select_test_targets(explicit_target="../outside.py")

        with pytest.raises(ControlledExecutionError, match="forbidden sequences"):
            selector.select_test_targets(explicit_target="tests/../../outside.py")

        with pytest.raises(ControlledExecutionError, match="forbidden sequences"):
            selector.select_test_targets(explicit_target="tests/\0test.py")

    def test_i_missing_mapping_uses_bounded_fallback(self, temp_workspace: Workspace):
        """I. Missing mapping uses bounded fallback."""
        selector = TestTargetSelector(temp_workspace)
        result = selector.select_test_targets(affected_files=["src/nonexistent/random_module.xyz"])

        assert result.strategy == TestSelectionStrategy.SAFE_BOUNDED_FALLBACK
        assert result.is_fallback is True
        assert len(result.selected_tests) <= MAX_BOUNDED_FALLBACK_COUNT
        # In temp_workspace, smoke test exists
        assert result.selected_tests == ("tests/smoke/test_smoke.py",)

    def test_j_selector_never_returns_entire_repo_suite(self, temp_workspace: Workspace):
        """J. Selector never returns the entire repository suite as an implicit default."""
        selector = TestTargetSelector(temp_workspace)

        # Pass completely empty inputs
        result = selector.select_test_targets()

        assert result.strategy == TestSelectionStrategy.SAFE_BOUNDED_FALLBACK
        assert result.is_fallback is True
        # Must be bounded to at most fallback count, never hundreds of tests
        assert len(result.selected_tests) <= MAX_BOUNDED_FALLBACK_COUNT
        assert result.selected_tests != ()

    def test_k_selector_performs_no_process_execution(self, temp_workspace: Workspace):
        """K. Selector performs no process execution."""
        selector = TestTargetSelector(temp_workspace)

        with (
            patch("subprocess.run") as mock_run,
            patch("subprocess.Popen") as mock_popen,
            patch("os.system") as mock_system,
        ):
            # Exercise all strategies
            selector.select_test_targets(explicit_target="tests/test_calc.py")
            selector.select_test_targets(affected_files=["src/calc.py"])
            selector.select_test_targets(affected_files=["src/pkg/feature.py"])
            selector.select_test_targets(failure_locations=["src/calc.py"])
            selector.select_test_targets()

            assert mock_run.call_count == 0
            assert mock_popen.call_count == 0
            assert mock_system.call_count == 0

    def test_l_controlled_execution_remains_responsible_for_execution(
        self, temp_workspace: Workspace
    ):
        """L. Existing controlled execution remains responsible for subprocess execution."""
        authority = ControlledExecutionAuthority(temp_workspace)

        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "1 passed in 0.05s"
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            result = authority.run_tests(target="tests/test_calc.py", timeout_seconds=15)

            assert mock_run.call_count == 1
            call_args, call_kwargs = mock_run.call_args
            cmd = call_args[0]
            assert "pytest" in cmd[2]
            assert "tests/test_calc.py" in cmd
            assert result.passed is True
            assert result.exit_code == 0

    def test_m_existing_successful_test_missions_continue_to_work(self, temp_workspace: Workspace):
        coordinator = _create_coordinator(temp_workspace)
        for st in (
            SWETaskStage.INSPECT_REPOSITORY,
            SWETaskStage.ANALYZE_FAILURE,
            SWETaskStage.FORMULATE_FIX,
            SWETaskStage.IMPLEMENT_CHANGE,
        ):
            coordinator.advance_stage(st)
            coordinator.complete_stage(st)
        coordinator.advance_stage(SWETaskStage.RUN_TESTS)

        # Mocking runner execution for clean deterministic success
        with patch.object(coordinator.controlled_execution_authority, "run_tests") as mock_runner:
            mock_runner.return_value = ControlledTestResult(
                execution_id=uuid4(),
                target="tests/test_calc.py",
                exit_code=0,
                status="passed",
                stdout="1 passed",
                stderr="",
                duration_seconds=0.08,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                timed_out=False,
            )

            res = coordinator.run_controlled_tests(target="tests/test_calc.py")
            assert res.passed is True
            assert res.exit_code == 0
            assert res.timed_out is False
            assert coordinator.last_test_selection is not None
            assert (
                coordinator.last_test_selection.strategy
                == TestSelectionStrategy.EXPLICIT_TEST_TARGET
            )

    def test_n_existing_failed_and_timeout_missions_remain_authoritative_failures(
        self, temp_workspace: Workspace
    ):
        """N. Existing failed/timeout missions remain authoritative failures."""
        coordinator = _create_coordinator(temp_workspace)

        # 1. Advance through stages up to RUN_TESTS
        coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
        coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)
        coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
        coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)
        coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
        coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)
        coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)

        # Mock patch application
        coordinator._last_application_result = PatchApplicationResult(
            patch_id=uuid4(),
            task_id=uuid4(),
            execution_id=uuid4(),
            status=PatchExecutionState.APPLIED,
            completed_operations=(),
            recovery_status="NONE",
            affected_files=("src/calc.py",),
            error=None,
        )
        coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

        coordinator.advance_stage(SWETaskStage.RUN_TESTS)

        # Simulate timeout failure
        with patch.object(coordinator.controlled_execution_authority, "run_tests") as mock_runner:
            mock_runner.return_value = ControlledTestResult(
                execution_id=uuid4(),
                target="tests/test_calc.py",
                exit_code=-1,
                status="timeout",
                stdout="",
                stderr="Test execution timed out after 30 seconds.",
                duration_seconds=30.015,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                timed_out=True,
            )

            test_res = coordinator.run_controlled_tests(target="tests/test_calc.py")
            assert test_res.passed is False
            assert test_res.timed_out is True
            assert test_res.exit_code == -1

        coordinator.complete_stage(SWETaskStage.RUN_TESTS)

        # Authoritative Verification must reject certification
        coordinator.advance_stage(SWETaskStage.VERIFY)
        outcome = coordinator.verify_patch_execution()
        assert outcome.is_verified is False
        assert outcome.lifecycle_state == PatchExecutionState.FAILED
        assert outcome.verification_result.status.value == "failed"


class TestCoordinatorBoundedSelectionIntegration:
    """Integration test verifying end-to-end RUN_TESTS bounded target inference."""

    def test_coordinator_infers_bounded_tests_when_target_empty(self, temp_workspace: Workspace):
        """When coordinator.run_controlled_tests receives target='', it infers bounded scope."""
        coordinator = _create_coordinator(temp_workspace)

        coordinator.advance_stage(SWETaskStage.INSPECT_REPOSITORY)
        coordinator.complete_stage(SWETaskStage.INSPECT_REPOSITORY)
        coordinator.advance_stage(SWETaskStage.ANALYZE_FAILURE)
        coordinator.complete_stage(SWETaskStage.ANALYZE_FAILURE)
        coordinator.advance_stage(SWETaskStage.FORMULATE_FIX)
        coordinator.complete_stage(SWETaskStage.FORMULATE_FIX)
        coordinator.advance_stage(SWETaskStage.IMPLEMENT_CHANGE)

        # Set last application result with affected_files
        coordinator._last_application_result = PatchApplicationResult(
            patch_id=uuid4(),
            task_id=uuid4(),
            execution_id=uuid4(),
            status=PatchExecutionState.APPLIED,
            completed_operations=(),
            recovery_status="NONE",
            affected_files=("src/calc.py",),
            error=None,
        )
        coordinator.complete_stage(SWETaskStage.IMPLEMENT_CHANGE)

        coordinator.advance_stage(SWETaskStage.RUN_TESTS)

        with patch.object(coordinator.controlled_execution_authority, "run_tests") as mock_runner:
            mock_runner.return_value = ControlledTestResult(
                execution_id=uuid4(),
                target="tests/test_calc.py",
                exit_code=0,
                status="passed",
                stdout="1 passed in 0.02s",
                stderr="",
                duration_seconds=0.02,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                timed_out=False,
            )

            # Invoke with empty target
            test_res = coordinator.run_controlled_tests(target="")

            assert test_res.passed is True
            assert coordinator.last_test_selection is not None
            assert (
                coordinator.last_test_selection.strategy
                == TestSelectionStrategy.DIRECT_TEST_MAPPING
            )
            assert coordinator.last_test_selection.selected_tests == ("tests/test_calc.py",)

            # Ensure evidence was recorded in ledger
            evidence_items = coordinator.ledger.get_items(
                stage=SWETaskStage.RUN_TESTS,
                category=EvidenceCategory.TEST_RESULT,
            )
            selector_items = [i for i in evidence_items if i.source == "TestTargetSelector"]
            assert len(selector_items) == 1
            assert (
                selector_items[0].metadata["strategy"]
                == TestSelectionStrategy.DIRECT_TEST_MAPPING.value
            )
            assert selector_items[0].metadata["selected_tests"] == ["tests/test_calc.py"]
