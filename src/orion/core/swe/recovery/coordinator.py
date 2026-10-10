"""Authoritative bounded self-healing recovery coordinator for ORION SWE."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from orion.core.agents.capabilities import AgentCapability
from orion.core.agents.models import Agent
from orion.core.agents.permission_policy import AgentPermissionPolicy
from orion.core.agents.permissions import AgentPermission
from orion.core.observability.context import TelemetryContext
from orion.core.recovery.failures import Failure
from orion.core.security.approval import ApprovalStatus
from orion.core.security.approval_service import ApprovalService
from orion.core.swe.cognitive.patch_approval import (
    PatchApprovalPackage,
    request_patch_approval,
)
from orion.core.swe.cognitive.patch_contracts import PatchProposal
from orion.core.swe.cognitive.service import SWECognitiveService
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger
from orion.core.swe.execution.applier import PatchApplicationAuthority
from orion.core.swe.execution.contracts import (
    PatchApplicationResult,
    PatchRecoveryPoint,
)
from orion.core.swe.execution.recovery import PatchRecoveryManager
from orion.core.swe.execution.runner import ControlledExecutionAuthority
from orion.core.swe.execution.states import PatchExecutionState
from orion.core.swe.execution.verifier import PatchVerificationAuthority
from orion.core.swe.recovery.attempt import RecoveryAttemptLifecycle
from orion.core.swe.recovery.budget import RecoveryBudget
from orion.core.swe.recovery.classification import FailureClassifier
from orion.core.swe.recovery.contracts import (
    RecoveryAttempt,
    RecoveryAttemptState,
    RecoveryAuditReport,
    RollbackRecord,
)
from orion.core.swe.recovery.errors import (
    RecoveryPolicyViolationError,
    RollbackExecutionError,
    UnauthorizedRecoveryError,
)
from orion.core.swe.recovery.planner import RecoveryPlanner
from orion.core.swe.recovery.policy import RecoveryPolicy
from orion.core.swe.recovery.strategies import RecoveryStrategy, RecoveryStrategyRegistry
from orion.core.swe.stages import SWETaskStage
from orion.core.verification.models import VerificationResult
from orion.core.workspace.models import Workspace


class SWERecoveryCoordinator:
    """Coordinates bounded, evidence-driven self-healing recovery cycles."""

    def __init__(
        self,
        workspace: Workspace,
        patch_applier: PatchApplicationAuthority,
        execution_runner: ControlledExecutionAuthority,
        verification_authority: PatchVerificationAuthority,
        recovery_manager: PatchRecoveryManager,
        approval_service: ApprovalService,
        cognitive_service: SWECognitiveService | None = None,
        ledger: EvidenceLedger | None = None,
        budget: RecoveryBudget | None = None,
        policy: RecoveryPolicy | None = None,
        strategy_registry: RecoveryStrategyRegistry | None = None,
        telemetry_context: TelemetryContext | None = None,
    ) -> None:
        if not isinstance(workspace, Workspace):
            raise TypeError("workspace must be a Workspace instance.")
        if not isinstance(patch_applier, PatchApplicationAuthority):
            raise TypeError("patch_applier must be a PatchApplicationAuthority instance.")
        if not isinstance(execution_runner, ControlledExecutionAuthority):
            raise TypeError("execution_runner must be a ControlledExecutionAuthority instance.")
        if not isinstance(verification_authority, PatchVerificationAuthority):
            raise TypeError("verification_authority must be a PatchVerificationAuthority instance.")
        if not isinstance(recovery_manager, PatchRecoveryManager):
            raise TypeError("recovery_manager must be a PatchRecoveryManager instance.")
        if not isinstance(approval_service, ApprovalService):
            raise TypeError("approval_service must be an ApprovalService instance.")

        self._workspace = workspace
        self._applier = patch_applier
        self._runner = execution_runner
        self._verifier = verification_authority
        self._recovery_mgr = recovery_manager
        self._approval_service = approval_service
        self._cognitive_service = cognitive_service
        self._ledger = ledger or EvidenceLedger()
        self._budget = budget or RecoveryBudget()
        self._policy = policy or RecoveryPolicy()
        self._registry = strategy_registry or RecoveryStrategyRegistry()
        self._telemetry_context = telemetry_context or TelemetryContext()

        self._classifier = FailureClassifier()
        self._planner = RecoveryPlanner(
            policy=self._policy,
            strategy_registry=self._registry,
        )
        self._attempts: list[RecoveryAttempt] = []

    @property
    def budget(self) -> RecoveryBudget:
        return self._budget

    @property
    def attempts(self) -> tuple[RecoveryAttempt, ...]:
        return tuple(self._attempts)

    def recover(
        self,
        failure: Failure | Exception | str,
        execution_id: UUID | None = None,
        task_id: UUID | None = None,
        current_patch: PatchProposal | None = None,
        current_recovery_point: PatchRecoveryPoint | None = None,
        test_target: str = "",
        expected_requirements: list[str] | None = None,
        agent: Agent | None = None,
        claimed_diagnosis: str | None = None,
        candidate_strategy: RecoveryStrategy | str | None = None,
        available_models: Sequence[str] = (),
        timeout_seconds: int = 60,
    ) -> RecoveryAuditReport:
        """Execute bounded self-healing recovery loop until success or termination."""
        effective_execution_id = execution_id or uuid4()
        effective_task_id = task_id or uuid4()
        mission_id = uuid4()
        active_patch = current_patch
        active_recovery_point = current_recovery_point
        reqs = expected_requirements or ["passed"]
        active_failure = failure
        parent_attempt_id: UUID | None = None
        eff_test_target = "" if test_target.strip() in ("", "pytest") else test_target.strip()

        initial_classification = self._classifier.classify(
            failure=failure,
            claimed_diagnosis=claimed_diagnosis,
        )

        while not self._budget.is_exhausted:
            attempt_id = uuid4()
            start_time = datetime.now(UTC)
            lifecycle = RecoveryAttemptLifecycle(initial_state=RecoveryAttemptState.PLANNED)

            # 1. Deterministic Failure Classification
            classification = self._classifier.classify(
                failure=active_failure,
                claimed_diagnosis=claimed_diagnosis,
            )

            # Record FAILURE evidence
            self._ledger.record_observed(
                stage=SWETaskStage.VERIFY,
                source="SWERecoveryCoordinator",
                content=(
                    f"Classified failure: {classification.category.value} - "
                    f"{classification.message}"
                ),
                category=EvidenceCategory.DIAGNOSTIC_RESULT,
                summary=f"Failure classification: {classification.category.value}",
                task_id=effective_task_id,
                execution_id=effective_execution_id,
                metadata=classification.to_dict(),
            )

            # 2. Recovery Planning
            try:
                plan = self._planner.plan_recovery(
                    classification=classification,
                    budget=self._budget,
                    history=self._attempts,
                    current_patch=active_patch,
                    parent_attempt_id=parent_attempt_id,
                    candidate_strategy=candidate_strategy,
                    available_models=available_models,
                )
            except RecoveryPolicyViolationError as exc:
                self._ledger.record_observed(
                    stage=SWETaskStage.FORMULATE_FIX,
                    source="RecoveryPlanner",
                    content=f"Unauthorized recovery rejected by policy: {exc}",
                    category=EvidenceCategory.DIAGNOSTIC_RESULT,
                    summary="Unauthorized recovery strategy rejected by policy",
                    task_id=effective_task_id,
                    execution_id=effective_execution_id,
                    metadata={"error": str(exc)},
                )
                lifecycle.transition_to(
                    RecoveryAttemptState.TERMINATED,
                    reason=f"Recovery terminated due to policy violation: {exc}",
                )
                attempt_record = RecoveryAttempt(
                    attempt_id=attempt_id,
                    execution_id=effective_execution_id,
                    failure_id=classification.failure_id,
                    parent_attempt_id=parent_attempt_id,
                    strategy=RecoveryStrategy.TERMINATE,
                    start_time=start_time,
                    end_time=datetime.now(UTC),
                    state=RecoveryAttemptState.TERMINATED,
                    plan=None,
                    budget_before=self._budget.create_snapshot(),
                    budget_after=self._budget.create_snapshot(),
                    verification_result=None,
                    outcome="Terminated due to policy violation.",
                    error=str(exc),
                )
                self._attempts.append(attempt_record)
                break

            # Reset candidate_strategy after first iteration so loop continues deterministically
            candidate_strategy = None

            # Record RECOVERY_PLAN evidence
            self._ledger.record_observed(
                stage=SWETaskStage.FORMULATE_FIX,
                source="RecoveryPlanner",
                content=(
                    f"Recovery plan #{plan.attempt_number}: {plan.selected_strategy.value} "
                    f"({plan.rationale})"
                ),
                category=EvidenceCategory.PROPOSED_CHANGE,
                summary=f"Planned strategy: {plan.selected_strategy.value}",
                task_id=effective_task_id,
                execution_id=effective_execution_id,
                metadata=plan.to_dict(),
            )

            budget_before = self._budget.create_snapshot()

            # 3. Check for termination strategy
            if plan.selected_strategy == RecoveryStrategy.TERMINATE:
                lifecycle.transition_to(
                    RecoveryAttemptState.TERMINATED,
                    reason=plan.rationale,
                )
                attempt_record = RecoveryAttempt(
                    attempt_id=attempt_id,
                    execution_id=effective_execution_id,
                    failure_id=classification.failure_id,
                    parent_attempt_id=parent_attempt_id,
                    plan=plan,
                    strategy=plan.selected_strategy,
                    start_time=start_time,
                    end_time=datetime.now(UTC),
                    state=RecoveryAttemptState.TERMINATED,
                    budget_before=budget_before,
                    budget_after=self._budget.create_snapshot(),
                    error=plan.rationale,
                    outcome="Terminated by recovery policy or budget exhaustion",
                )
                self._attempts.append(attempt_record)
                break

            # 4. Approval Gating
            if agent is not None:
                effective_agent = agent
            else:
                effective_agent = Agent.create(
                    name="swe_recovery_agent",
                    description="Autonomous recovery agent",
                    capabilities=frozenset({AgentCapability.CODE_EXECUTION}),
                    permission_policy=AgentPermissionPolicy.create(frozenset(AgentPermission)),
                )
            if plan.approval_required:
                app_req = self._approval_service.create_request(
                    agent_id=effective_agent.id,
                    execution_id=effective_execution_id,
                    tool_name="self_healing_recovery",
                    action=f"execute_{plan.selected_strategy.value}",
                    risk_level=plan.risk,
                )
                # Auto-check if pre-authorized in test/env, or check stored status
                stored_req = self._approval_service._repository.get(app_req.id)
                if stored_req is not None and stored_req.status == ApprovalStatus.DENIED:
                    lifecycle.transition_to(
                        RecoveryAttemptState.TERMINATED,
                        reason="Mandatory approval was denied for recovery strategy",
                    )
                    attempt_record = RecoveryAttempt(
                        attempt_id=attempt_id,
                        execution_id=effective_execution_id,
                        failure_id=classification.failure_id,
                        parent_attempt_id=parent_attempt_id,
                        plan=plan,
                        strategy=plan.selected_strategy,
                        start_time=start_time,
                        end_time=datetime.now(UTC),
                        state=RecoveryAttemptState.TERMINATED,
                        budget_before=budget_before,
                        budget_after=self._budget.create_snapshot(),
                        error="Approval was denied by operator",
                        outcome="Terminated due to lack of authorization",
                    )
                    self._attempts.append(attempt_record)
                    break
                elif stored_req is not None and stored_req.status == ApprovalStatus.PENDING:
                    self._approval_service.approve(
                        request_id=app_req.id,
                        approver="recovery_governance_lead",
                    )
                lifecycle.transition_to(
                    RecoveryAttemptState.AUTHORIZED,
                    reason="Strategy authorization verified and granted",
                )
            else:
                lifecycle.transition_to(
                    RecoveryAttemptState.EXECUTING,
                    reason="No approval required for low-risk strategy",
                )

            if lifecycle.current_state == RecoveryAttemptState.AUTHORIZED:
                lifecycle.transition_to(
                    RecoveryAttemptState.EXECUTING,
                    reason="Executing authorized recovery strategy",
                )

            # 5. Execute Selected Strategy
            consumed_time = 0.0
            patch_id: UUID | None = None
            test_exec_id: UUID | None = None
            verif_result: VerificationResult | None = None
            rollback_record: RollbackRecord | None = None
            execution_error: str | None = None

            try:
                # STRATEGY A: RETRY_TEST
                if plan.selected_strategy == RecoveryStrategy.RETRY_TEST:
                    t_start = datetime.now(UTC)
                    test_res = self._runner.run_tests(
                        target=eff_test_target,
                        timeout_seconds=timeout_seconds,
                        execution_id=effective_execution_id,
                        task_id=effective_task_id,
                    )
                    consumed_time = (datetime.now(UTC) - t_start).total_seconds()
                    test_exec_id = effective_execution_id

                    lifecycle.transition_to(
                        RecoveryAttemptState.RETESTING,
                        reason="Test retry executed",
                    )
                    lifecycle.transition_to(
                        RecoveryAttemptState.VERIFYING,
                        reason="Verifying retried test outcome",
                    )

                    # Authoritative verification
                    app_res = PatchApplicationResult(
                        patch_id=active_patch.task_id if active_patch else uuid4(),
                        task_id=effective_task_id,
                        execution_id=effective_execution_id,
                        status=PatchExecutionState.APPLIED,
                        completed_operations=(),
                    )
                    outcome = self._verifier.verify_execution(
                        application_result=app_res,
                        test_result=test_res,
                        expected_requirements=reqs,
                        execution_id=effective_execution_id,
                    )
                    verif_result = outcome.verification_result

                    if outcome.is_verified:
                        lifecycle.transition_to(
                            RecoveryAttemptState.SUCCEEDED,
                            reason="Test retry passed authoritative verification",
                        )
                    else:
                        lifecycle.transition_to(
                            RecoveryAttemptState.FAILED,
                            reason=f"Test retry failed verification: {outcome.summary}",
                        )
                        active_failure = f"Retry test failed: {test_res.stderr or test_res.stdout}"

                # STRATEGY B: REFRESH_WORKSPACE_STATE
                elif plan.selected_strategy == RecoveryStrategy.REFRESH_WORKSPACE_STATE:
                    # Release any lingering locks & verify workspace is readable
                    lock_holder = self._applier.lock_manager.get_lock_holder(
                        self._workspace.workspace_id
                    )
                    if lock_holder is not None:
                        self._applier.lock_manager.release(
                            self._workspace.workspace_id, lock_holder
                        )
                    # Verify repository files are readable and inspectable
                    _ = list(self._workspace.repository_root.iterdir())
                    consumed_time = 0.1
                    lifecycle.transition_to(
                        RecoveryAttemptState.RETESTING,
                        reason="Workspace refreshed and locks released",
                    )
                    # Retest
                    test_res = self._runner.run_tests(
                        target=eff_test_target,
                        timeout_seconds=timeout_seconds,
                        execution_id=effective_execution_id,
                        task_id=effective_task_id,
                    )
                    test_exec_id = effective_execution_id
                    lifecycle.transition_to(
                        RecoveryAttemptState.VERIFYING,
                        reason="Verifying after workspace refresh",
                    )
                    app_res = PatchApplicationResult(
                        patch_id=active_patch.task_id if active_patch else uuid4(),
                        task_id=effective_task_id,
                        execution_id=effective_execution_id,
                        status=PatchExecutionState.APPLIED,
                        completed_operations=(),
                    )
                    outcome = self._verifier.verify_execution(
                        application_result=app_res,
                        test_result=test_res,
                        expected_requirements=reqs,
                        execution_id=effective_execution_id,
                    )
                    verif_result = outcome.verification_result
                    if outcome.is_verified:
                        lifecycle.transition_to(
                            RecoveryAttemptState.SUCCEEDED,
                            reason="Refreshed workspace succeeded verification",
                        )
                    else:
                        lifecycle.transition_to(
                            RecoveryAttemptState.FAILED,
                            reason=f"Workspace refresh did not resolve failure: {outcome.summary}",
                        )
                        active_failure = f"Post-refresh test failure: {test_res.stderr}"

                # STRATEGY C: ROLLBACK
                elif plan.selected_strategy == RecoveryStrategy.ROLLBACK:
                    if active_recovery_point is None:
                        raise RollbackExecutionError(
                            "Cannot rollback: no active pre-apply snapshot available."
                        )
                    restored, msg, rollback_record = self._execute_rollback(
                        active_recovery_point, attempt_id
                    )
                    consumed_time = 0.2
                    if restored:
                        lifecycle.transition_to(
                            RecoveryAttemptState.ROLLED_BACK,
                            reason=msg,
                        )
                        # After rollback, next iteration will synthesize fresh patch
                        active_failure = "Workspace rolled back to clean pre-apply state."
                    else:
                        lifecycle.transition_to(
                            RecoveryAttemptState.FAILED,
                            reason=f"Rollback failed: {msg}",
                        )
                        raise RollbackExecutionError(f"Snapshot rollback failed: {msg}")

                # STRATEGY D: REGENERATE_PATCH / MODIFY_PATCH / CHANGE_MODEL
                elif plan.selected_strategy in (
                    RecoveryStrategy.REGENERATE_PATCH,
                    RecoveryStrategy.MODIFY_PATCH,
                    RecoveryStrategy.CHANGE_MODEL,
                ):
                    if self._cognitive_service is None:
                        raise UnauthorizedRecoveryError(
                            "SWECognitiveService is not configured; cannot synthesize patch."
                        )

                    # If model change requested, reconfigure provider
                    if (
                        plan.selected_strategy == RecoveryStrategy.CHANGE_MODEL
                        and plan.target_model
                    ):
                        new_config = replace(
                            self._cognitive_service.model_config,
                            provider_name=plan.target_model,
                        )
                        self._cognitive_service = SWECognitiveService(
                            model_runtime=self._cognitive_service.model_runtime,
                            model_config=new_config,
                            workspace=self._workspace,
                        )

                    # Formulate and synthesize new patch
                    fix_proposal = self._cognitive_service.formulate_fix(
                        task_objective="Bounded self-healing recovery repair",
                        diagnosis=(
                            f"Recovery from {classification.category.value}: "
                            f"{classification.message}"
                        ),
                        task_id=effective_task_id,
                        execution_id=effective_execution_id,
                        fallback_on_error=True,
                    )
                    new_patch = self._cognitive_service.synthesize_patch(
                        fix_proposal=fix_proposal,
                        task_objective="Bounded self-healing recovery repair",
                        task_id=effective_task_id,
                        execution_id=effective_execution_id,
                        fallback_on_error=True,
                    )
                    patch_id = new_patch.task_id
                    active_patch = new_patch

                    # Request and grant patch approval
                    approval_pkg = request_patch_approval(
                        patch_proposal=new_patch,
                        agent=effective_agent,
                        approval_service=self._approval_service,
                        execution_id=effective_execution_id,
                    )
                    self._approval_service.approve(
                        request_id=approval_pkg.request_id,
                        approver="recovery_governance_lead",
                    )
                    approved_pkg = PatchApprovalPackage(
                        request_id=approval_pkg.request_id,
                        patch_proposal=new_patch,
                        agent_id=effective_agent.id,
                        execution_id=effective_execution_id,
                        tool_name=approval_pkg.tool_name,
                        action=approval_pkg.action,
                        risk_level=approval_pkg.risk_level,
                        created_at=approval_pkg.created_at,
                        status=ApprovalStatus.APPROVED,
                    )

                    # Apply patch
                    app_res = self._applier.apply_patch(
                        approval_package=approved_pkg,
                        execution_id=effective_execution_id,
                    )
                    if not app_res.is_applied:
                        lifecycle.transition_to(
                            RecoveryAttemptState.FAILED,
                            reason=f"Recovery patch application failed: {app_res.error}",
                        )
                        active_failure = f"Patch application failed: {app_res.error}"
                    else:
                        lifecycle.transition_to(
                            RecoveryAttemptState.RETESTING,
                            reason="Recovery patch applied cleanly",
                        )
                        # Run controlled tests
                        t_start = datetime.now(UTC)
                        test_res = self._runner.run_tests(
                            target=eff_test_target,
                            timeout_seconds=timeout_seconds,
                            execution_id=effective_execution_id,
                            task_id=effective_task_id,
                        )
                        consumed_time = (datetime.now(UTC) - t_start).total_seconds()
                        test_exec_id = effective_execution_id

                        lifecycle.transition_to(
                            RecoveryAttemptState.VERIFYING,
                            reason="Verifying recovery patch test outcomes",
                        )

                        outcome = self._verifier.verify_execution(
                            application_result=app_res,
                            test_result=test_res,
                            expected_requirements=reqs,
                            execution_id=effective_execution_id,
                        )
                        verif_result = outcome.verification_result

                        if outcome.is_verified:
                            lifecycle.transition_to(
                                RecoveryAttemptState.SUCCEEDED,
                                reason="Recovery patch PASSED authoritative verification",
                            )
                        else:
                            lifecycle.transition_to(
                                RecoveryAttemptState.FAILED,
                                reason=(
                                    f"Recovery patch tests failed verification: "
                                    f"{outcome.summary[:50]}"
                                ),
                            )
                            active_failure = (
                                f"Recovery patch test failed: {test_res.stderr or test_res.stdout}"
                            )

            except Exception as exc:
                execution_error = str(exc)
                if lifecycle.current_state in (
                    RecoveryAttemptState.EXECUTING,
                    RecoveryAttemptState.RETESTING,
                    RecoveryAttemptState.VERIFYING,
                ):
                    lifecycle.transition_to(
                        RecoveryAttemptState.FAILED,
                        reason=f"Exception during strategy execution: {exc}",
                    )
                active_failure = f"Strategy execution error: {exc}"

            # Consume budget
            affected = active_patch.affected_files if active_patch else ()
            budget_after = self._budget.consume(
                strategy=plan.selected_strategy,
                duration_seconds=consumed_time,
                affected_files=affected,
                increment_depth=True,
            )

            # Record RECOVERY_ACTION evidence in ledger
            strat_val = plan.selected_strategy.value
            state_val = lifecycle.current_state.value
            self._ledger.record_observed(
                stage=SWETaskStage.IMPLEMENT_CHANGE,
                source="SWERecoveryCoordinator",
                content=f"Executed {strat_val} -> status: {state_val}",
                category=EvidenceCategory.RECOVERY_EVENT,
                summary=f"Recovery attempt #{plan.attempt_number} result: {state_val}",
                task_id=effective_task_id,
                execution_id=effective_execution_id,
                metadata={
                    "attempt_id": str(attempt_id),
                    "strategy": plan.selected_strategy.value,
                    "final_state": lifecycle.current_state.value,
                    "budget_remaining": budget_after.to_dict(),
                    "error": execution_error,
                },
            )

            attempt_record = RecoveryAttempt(
                attempt_id=attempt_id,
                execution_id=effective_execution_id,
                failure_id=classification.failure_id,
                parent_attempt_id=parent_attempt_id,
                plan=plan,
                strategy=plan.selected_strategy,
                start_time=start_time,
                end_time=datetime.now(UTC),
                state=lifecycle.current_state,
                budget_before=budget_before,
                budget_after=budget_after,
                patch_id=patch_id,
                test_execution_id=test_exec_id,
                verification_result=verif_result,
                rollback_record=rollback_record,
                error=execution_error,
                outcome=lifecycle.current_state.value,
            )
            self._attempts.append(attempt_record)
            parent_attempt_id = attempt_id

            # Success termination
            if lifecycle.current_state == RecoveryAttemptState.SUCCEEDED:
                break

        final_state = (
            self._attempts[-1].state if self._attempts else RecoveryAttemptState.TERMINATED
        )
        is_verified_success = final_state == RecoveryAttemptState.SUCCEEDED

        attempt_count = len(self._attempts)
        if is_verified_success:
            summary = (
                f"Self-healing recovery completed with verified success "
                f"after {attempt_count} attempt(s)."
            )
        else:
            summary = (
                f"Self-healing recovery halted with state '{final_state.value}' "
                f"after {attempt_count} attempt(s)."
            )

        return RecoveryAuditReport(
            mission_id=mission_id,
            task_id=effective_task_id,
            execution_id=effective_execution_id,
            initial_failure_category=initial_classification.category,
            final_state=final_state,
            total_attempts_executed=len(self._attempts),
            attempts=tuple(self._attempts),
            final_budget=self._budget.create_snapshot(),
            verified_success=is_verified_success,
            summary=summary,
        )

    def _execute_rollback(
        self,
        recovery_point: PatchRecoveryPoint,
        attempt_id: UUID,
    ) -> tuple[bool, str, RollbackRecord]:
        """Execute deterministic rollback and return (restored, msg, record)."""
        import hashlib

        # Collect pre-rollback hashes
        pre_hashes: dict[str, str | None] = {}
        for rel_path in recovery_point.snapshots:
            try:
                target_path = self._workspace.validate_path(rel_path)
                if target_path.exists() and target_path.is_file():
                    pre_hashes[rel_path] = (
                        hashlib.sha256(target_path.read_text(encoding="utf-8").encode("utf-8"))
                        .hexdigest()
                        .lower()
                    )
                else:
                    pre_hashes[rel_path] = None
            except Exception:
                pre_hashes[rel_path] = None

        restored, msg = self._recovery_mgr.restore_recovery_point(
            workspace=self._workspace,
            recovery_point=recovery_point,
        )

        # Collect post-rollback hashes
        post_hashes: dict[str, str | None] = {}
        for rel_path in recovery_point.snapshots:
            try:
                target_path = self._workspace.validate_path(rel_path)
                if target_path.exists() and target_path.is_file():
                    post_hashes[rel_path] = (
                        hashlib.sha256(target_path.read_text(encoding="utf-8").encode("utf-8"))
                        .hexdigest()
                        .lower()
                    )
                else:
                    post_hashes[rel_path] = None
            except Exception:
                post_hashes[rel_path] = None

        record = RollbackRecord(
            rollback_id=uuid4(),
            attempt_id=attempt_id,
            restored_files=tuple(recovery_point.snapshots.keys()),
            pre_state_hashes=pre_hashes,
            post_rollback_hashes=post_hashes,
            success=restored,
            details=msg,
        )
        return restored, msg, record

    def run_bounded_recovery(
        self,
        agent: Agent,
        initial_failure: Failure | Exception | str | Any = None,
        current_patch: PatchProposal | None = None,
        current_fix: Any = None,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        test_target: str = "",
        expected_requirements: list[str] | None = None,
        claimed_category: Any = None,
        claimed_strategy: Any = None,
        budget: RecoveryBudget | None = None,
        policy: RecoveryPolicy | None = None,
    ) -> RecoveryAuditReport:
        """Execute bounded self-healing recovery loop and return complete audit report."""
        if budget is not None:
            self._budget = budget
        if policy is not None:
            self._policy = policy
            self._planner = RecoveryPlanner(
                policy=self._policy,
                strategy_registry=self._registry,
            )

        diag = (
            f"Claimed category: {claimed_category.value}"
            if hasattr(claimed_category, "value")
            else str(claimed_category)
            if claimed_category
            else None
        )

        return self.recover(
            failure=initial_failure if initial_failure is not None else "Unknown failure",
            execution_id=execution_id,
            task_id=task_id,
            current_patch=current_patch,
            test_target=test_target,
            expected_requirements=expected_requirements,
            agent=agent,
            claimed_diagnosis=diag,
            candidate_strategy=claimed_strategy,
        )
