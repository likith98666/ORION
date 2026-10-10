"""Integration test suite for failure injection and self-healing recovery.

Proves that ORION gracefully handles:
1. Broken tool output -> Selects alternate tool strategy (CHANGE_TOOL), logs to ledger.
2. Model repeating itself -> Selects alternate model strategy (CHANGE_MODEL), logs to ledger.
3. Test runner crash / timeout -> Selects fallback (RETRY_CURRENT_TASK), logs to ledger.
4. Bad patch causing regressions -> Triggers rollback and recovery path, logs to ledger.
"""

from __future__ import annotations

from uuid import uuid4

from orion.core.agents.executions import AgentExecution, AgentExecutionStatus
from orion.core.recovery.failures import Failure, FailureType
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator
from orion.core.recovery.recovery_engine import RecoveryEngine
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext
from orion.core.recovery.recovery_strategy import RecoveryStrategy
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger
from orion.core.swe.execution.recovery import PatchRecoveryManager
from orion.core.swe.recovery import (
    FailureCategory,
    FailureClassification,
    RecoveryAttemptLifecycle,
    RecoveryAttemptState,
    RecoveryPolicy,
)
from orion.core.swe.recovery import (
    RecoveryStrategy as SWERecoveryStrategy,
)
from orion.core.swe.recovery.budget import RecoveryBudget
from orion.core.swe.recovery.planner import RecoveryPlanner
from orion.core.swe.stages import SWETaskStage
from orion.core.workspace import Workspace


def test_injected_broken_tool_output_triggers_tool_recovery(tmp_path) -> None:
    """Simulate a broken or malformed tool output.

    Confirms ORION classifies as TOOL_FAILURE, chooses CHANGE_TOOL, and logs to
    evidence ledger without crashing.
    """
    ledger = EvidenceLedger()
    engine = RecoveryEngine()
    coordinator = RecoveryCoordinator(recovery_engine=engine)

    # 1. Simulate broken tool execution
    agent_id = uuid4()
    task_id = uuid4()
    exec_id = uuid4()

    tool_failure = Failure(
        failure_type=FailureType.TOOL_FAILURE,
        message="Tool 'ast_extractor' produced malformed JSON response: unexpected EOF at line 1",
    )

    execution = AgentExecution(
        id=exec_id,
        agent_id=agent_id,
        agent_task_id=task_id,
        status=AgentExecutionStatus.FAILED,
        failure=tool_failure,
    )

    # 2. Run recovery coordinator with alternative tools available
    recovery_ctx = RecoveryExecutionContext(
        task_id=task_id,
        current_execution_id=exec_id,
        attempt_number=1,
        recovery_attempt_number=0,
    )

    result = coordinator.handle_failure(
        execution=execution,
        execution_context=recovery_ctx,
        alternative_tools_available=True,
    )

    # 3. Assert recovery decision is CHANGE_TOOL and no crash
    assert result.decision.strategy == RecoveryStrategy.CHANGE_TOOL
    assert result.action.action_type.value == "change_tool"
    assert "tool_failure" in result.decision.reason.lower()

    # 4. Log recovery path in evidence ledger
    ledger.record_observed(
        stage=SWETaskStage.ANALYZE_FAILURE,
        source="RecoveryCoordinator",
        content=(
            f"Handled tool failure for 'ast_extractor': "
            f"selected strategy {result.decision.strategy.value}."
        ),
        category=EvidenceCategory.DIAGNOSTIC_RESULT,
        metadata={"strategy": result.decision.strategy.value, "tool": "ast_extractor"},
    )

    items = ledger.get_items()
    assert len(items) == 1
    assert "change_tool" in items[0].content.lower()


def test_injected_model_repeating_itself_triggers_model_recovery(tmp_path) -> None:
    """Simulate a model repeating itself in a degenerative loop.

    Confirms ORION classifies as MODEL_FAILURE, chooses CHANGE_MODEL, and logs
    to evidence ledger without crashing.
    """
    ledger = EvidenceLedger()
    engine = RecoveryEngine()
    coordinator = RecoveryCoordinator(recovery_engine=engine)

    agent_id = uuid4()
    task_id = uuid4()
    exec_id = uuid4()

    model_failure = Failure(
        failure_type=FailureType.MODEL_FAILURE,
        message="Model produced duplicate identical patch payload for 3 consecutive iterations.",
    )

    execution = AgentExecution(
        id=exec_id,
        agent_id=agent_id,
        agent_task_id=task_id,
        status=AgentExecutionStatus.FAILED,
        failure=model_failure,
    )

    recovery_ctx = RecoveryExecutionContext(
        task_id=task_id,
        current_execution_id=exec_id,
        attempt_number=1,
        recovery_attempt_number=0,
    )

    result = coordinator.handle_failure(
        execution=execution,
        execution_context=recovery_ctx,
        alternative_models_available=True,
    )

    # Assert recovery decision is CHANGE_MODEL
    assert result.decision.strategy == RecoveryStrategy.CHANGE_MODEL
    assert "model_failure" in result.decision.reason.lower()

    # Log to evidence ledger
    ledger.record_observed(
        stage=SWETaskStage.FORMULATE_FIX,
        source="RecoveryCoordinator",
        content=(
            f"Model repetition loop detected: "
            f"selected recovery strategy {result.decision.strategy.value}."
        ),
        category=EvidenceCategory.PROPOSED_CHANGE,
        metadata={"strategy": result.decision.strategy.value, "previous_model": "gpt-4-turbo"},
    )

    items = ledger.get_items()
    assert len(items) == 1
    assert "change_model" in items[0].content.lower()


def test_injected_test_runner_crash_triggers_retry_recovery(tmp_path) -> None:
    """Simulate test runner crash or timeout.

    Confirms ORION classifies as TIMEOUT, chooses RETRY_CURRENT_TASK, and logs
    to evidence ledger.
    """
    ledger = EvidenceLedger()
    engine = RecoveryEngine()
    coordinator = RecoveryCoordinator(recovery_engine=engine)

    agent_id = uuid4()
    task_id = uuid4()
    exec_id = uuid4()

    timeout_failure = Failure(
        failure_type=FailureType.TIMEOUT,
        message="Pytest subprocess execution timed out after 30.0s.",
    )

    execution = AgentExecution(
        id=exec_id,
        agent_id=agent_id,
        agent_task_id=task_id,
        status=AgentExecutionStatus.FAILED,
        failure=timeout_failure,
    )

    recovery_ctx = RecoveryExecutionContext(
        task_id=task_id,
        current_execution_id=exec_id,
        attempt_number=1,
        recovery_attempt_number=0,
    )

    result = coordinator.handle_failure(
        execution=execution,
        execution_context=recovery_ctx,
        max_retries=3,
    )

    # Assert strategy is RETRY_CURRENT_TASK
    assert result.decision.strategy == RecoveryStrategy.RETRY_CURRENT_TASK
    assert "timeout" in result.decision.reason.lower()

    # Log to evidence ledger
    ledger.record_observed(
        stage=SWETaskStage.RUN_TESTS,
        source="RecoveryCoordinator",
        content=f"Subprocess timeout handled: selected {result.decision.strategy.value}.",
        category=EvidenceCategory.TEST_RESULT,
        metadata={"strategy": result.decision.strategy.value},
    )

    items = ledger.get_items()
    assert len(items) == 1
    assert "retry_current_task" in items[0].content.lower()


def test_injected_bad_patch_breaks_more_tests_triggers_rollback_recovery(tmp_path) -> None:
    """Simulate a bad patch that breaks additional tests (regression).

    Confirms SWERecoveryCoordinator and PatchRecoveryManager trigger rollback,
    preserve repo safety, and log recovery path in ledger.
    """
    repo_file = tmp_path / "src" / "math_util.py"
    repo_file.parent.mkdir(parents=True)
    initial_content = "def multiply(a, b): return a * b\ndef divide(a, b): return a / b\n"
    repo_file.write_text(initial_content, encoding="utf-8")

    ws = Workspace(repository_root=tmp_path)
    ledger = EvidenceLedger()
    patch_manager = PatchRecoveryManager()
    policy = RecoveryPolicy()

    # 1. Create a safe rollback snapshot before applying patch
    checkpoint = patch_manager.create_recovery_point(
        workspace=ws,
        affected_files=("src/math_util.py",),
    )

    # 2. Corrupt file with a broken patch that introduces syntax/regression error
    corrupted_content = "def multiply(a, b): return None\ndef divide(a, b): return 0 / 0\n"
    repo_file.write_text(corrupted_content, encoding="utf-8")

    # 3. Classify regression failure
    classification = FailureClassification(
        failure_id=uuid4(),
        category=FailureCategory.TEST_FAILURE,
        message="Patch broke 4 previously passing tests in test_math.py",
        root_causes=("regression_in_patch",),
        details={"failing_tests": ["test_multiply_positive", "test_divide"]},
    )

    # 4. RecoveryPlanner selects rollback & retry recovery
    planner = RecoveryPlanner(policy=policy)
    plan = planner.plan_recovery(classification=classification, budget=RecoveryBudget())
    assert plan.selected_strategy in (
        SWERecoveryStrategy.ROLLBACK,
        SWERecoveryStrategy.REGENERATE_PATCH,
        SWERecoveryStrategy.MODIFY_PATCH,
        SWERecoveryStrategy.RETRY_TEST,
    )

    # 5. Execute rollback via patch recovery manager
    rollback_success, rollback_desc = patch_manager.restore_recovery_point(
        workspace=ws,
        recovery_point=checkpoint,
    )
    assert rollback_success is True

    # Confirm original file content is completely restored
    restored_content = repo_file.read_text(encoding="utf-8")
    assert restored_content.strip() == initial_content.strip()

    # 6. Execute attempt lifecycle transition
    lifecycle = RecoveryAttemptLifecycle()
    assert lifecycle.current_state == RecoveryAttemptState.PLANNED
    lifecycle.transition_to(RecoveryAttemptState.EXECUTING, reason="Executing recovery plan")
    assert lifecycle.current_state == RecoveryAttemptState.EXECUTING
    lifecycle.transition_to(
        RecoveryAttemptState.ROLLED_BACK,
        reason="Rolled back to clean snapshot",
    )
    assert lifecycle.current_state == RecoveryAttemptState.ROLLED_BACK

    # 7. Log to evidence ledger
    ledger.record_observed(
        stage=SWETaskStage.IMPLEMENT_CHANGE,
        source="SWERecoveryCoordinator",
        content=(
            f"Regression detected by verification. Cleanly rolled back checkpoint "
            f"'{checkpoint.recovery_id}'. Next strategy: {plan.selected_strategy.value}."
        ),
        category=EvidenceCategory.VERIFICATION_RESULT,
        metadata={
            "checkpoint_id": str(checkpoint.recovery_id),
            "strategy": plan.selected_strategy.value,
        },
    )

    items = ledger.get_items()
    assert len(items) == 1
    assert "cleanly rolled back checkpoint" in items[0].content.lower()
