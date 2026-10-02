from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from orion.core.agents.executions import AgentExecution
from orion.core.agents.models import Agent
from orion.core.observability.context import TelemetryContext
from orion.core.recovery.recovery_coordinator import RecoveryCoordinator, RecoveryResult
from orion.core.recovery.recovery_execution_context import RecoveryExecutionContext
from orion.core.recovery.recovery_service import RecoveryService
from orion.core.swe.cognitive import (
    CognitiveModelUnavailableError,
    FailureAnalysisProposal,
    FixProposal,
    PatchApprovalPackage,
    PatchApprovalRequiredError,
    PatchProposal,
    SWECognitiveService,
    refresh_patch_approval,
    request_patch_approval,
)
from orion.core.swe.execution import (
    ControlledExecutionAuthority,
    ControlledTestResult,
    PatchApplicationAuthority,
    PatchApplicationResult,
    PatchVerificationAuthority,
    Phase5ExecutionOutcome,
    UnapprovedPatchError,
)
from orion.core.swe.errors import (
    DisallowedFileModificationError,
    DisallowedStageToolError,
    MissingWorkspaceError,
    WorkflowSequenceError,
)
from orion.core.swe.evaluation import (
    EvaluationStatus,
    MissionEvaluation,
    SWEEvaluator,
)
from orion.core.swe.evidence import (
    EvidenceCategory,
    EvidenceItem,
    EvidenceLedger,
    SWEReport,
)
from orion.core.swe.formulation import ProposedFixPlan
from orion.core.swe.graph import SWETaskGraph
from orion.core.swe.stages import (
    FILE_MODIFICATION_TOOLS,
    SWETaskStage,
)
from orion.core.tools.executor import ToolExecutionResult, ToolExecutor
from orion.core.verification.engine import VerificationEngine
from orion.core.verification.models import VerificationResult, VerificationStatus
from orion.core.workspace.models import ExecutionIdentity, Workspace

STAGE_ORDER: tuple[SWETaskStage, ...] = (
    SWETaskStage.INSPECT_REPOSITORY,
    SWETaskStage.ANALYZE_FAILURE,
    SWETaskStage.FORMULATE_FIX,
    SWETaskStage.IMPLEMENT_CHANGE,
    SWETaskStage.RUN_TESTS,
    SWETaskStage.VERIFY,
    SWETaskStage.GENERATE_REPORT,
)


class SWEWorkflowCoordinator:
    """Coordinates the 7-stage Autonomous Software Engineering task graph."""

    def __init__(
        self,
        workspace: Workspace,
        tool_executor: ToolExecutor,
        verification_engine: VerificationEngine,
        mission_id: UUID | None = None,
        task_id: UUID | None = None,
        recovery_coordinator: RecoveryCoordinator | None = None,
        recovery_service: RecoveryService | None = None,
        telemetry_context: TelemetryContext | None = None,
        task_graph: SWETaskGraph | None = None,
        cognitive_service: SWECognitiveService | None = None,
    ) -> None:
        if not isinstance(workspace, Workspace):
            raise MissingWorkspaceError(
                "A valid Workspace instance is mandatory for all SWE workflows."
            )

        if not isinstance(tool_executor, ToolExecutor):
            raise TypeError("tool_executor must be a ToolExecutor instance.")

        if not isinstance(verification_engine, VerificationEngine):
            raise TypeError("verification_engine must be a VerificationEngine instance.")

        self._workspace = workspace
        self._tool_executor = tool_executor
        self._verification_engine = verification_engine
        self._recovery_coordinator = recovery_coordinator
        self._recovery_service = recovery_service
        self._mission_id = mission_id or uuid4()
        self._task_id = task_id or uuid4()
        self._telemetry_context = telemetry_context or TelemetryContext(
            task_id=self._task_id,
        )

        self._task_graph = task_graph or SWETaskGraph.create(
            task_id=self._task_id,
            objective="Autonomous software engineering mission",
        )

        self._execution_identity = ExecutionIdentity.from_telemetry_context(
            workspace_id=self._workspace.workspace_id,
            telemetry_context=self._telemetry_context,
        )

        self._cognitive_service = cognitive_service
        self._last_failure_analysis: FailureAnalysisProposal | None = None
        self._last_fix_proposal: FixProposal | None = None
        self._last_patch_proposal: PatchProposal | None = None
        self._last_patch_approval: PatchApprovalPackage | None = None

        self._ledger = EvidenceLedger()
        self._current_stage: SWETaskStage | None = None
        self._completed_stages: list[SWETaskStage] = []
        self._formulated_plan: ProposedFixPlan | None = None
        self._last_test_output: str | None = None
        self._last_verification_result: VerificationResult | None = None
        self._last_application_result: PatchApplicationResult | None = None
        self._last_controlled_test_result: ControlledTestResult | None = None
        self._last_phase5_outcome: Phase5ExecutionOutcome | None = None
        self._patch_applier: PatchApplicationAuthority | None = None
        self._controlled_runner: ControlledExecutionAuthority | None = None
        self._patch_verifier: PatchVerificationAuthority | None = None

    @property
    def workspace(self) -> Workspace:
        """Return the bound workspace."""
        return self._workspace

    @property
    def current_stage(self) -> SWETaskStage | None:
        """Return the current active stage."""
        return self._current_stage

    @property
    def completed_stages(self) -> tuple[SWETaskStage, ...]:
        """Return tuple of completed stages in order."""
        return tuple(self._completed_stages)

    @property
    def ledger(self) -> EvidenceLedger:
        """Return the active evidence ledger."""
        return self._ledger

    @property
    def task_graph(self) -> SWETaskGraph:
        """Return the task graph."""
        return self._task_graph

    @property
    def formulated_plan(self) -> ProposedFixPlan | None:
        """Return the formulated plan if created."""
        return self._formulated_plan

    @property
    def cognitive_service(self) -> SWECognitiveService | None:
        """Return the bound cognitive service if configured."""
        return self._cognitive_service

    @property
    def last_failure_analysis(self) -> FailureAnalysisProposal | None:
        """Return the most recent failure analysis proposal."""
        return self._last_failure_analysis

    @property
    def last_fix_proposal(self) -> FixProposal | None:
        """Return the most recent fix proposal."""
        return self._last_fix_proposal

    @property
    def last_patch_proposal(self) -> PatchProposal | None:
        """Return the most recent patch proposal."""
        return self._last_patch_proposal

    @property
    def last_patch_approval(self) -> PatchApprovalPackage | None:
        """Return the most recent patch approval package."""
        return self._last_patch_approval

    @property
    def last_application_result(self) -> PatchApplicationResult | None:
        """Return the most recent patch application result."""
        return self._last_application_result

    @property
    def last_controlled_test_result(self) -> ControlledTestResult | None:
        """Return the most recent controlled test execution result."""
        return self._last_controlled_test_result

    @property
    def last_phase5_outcome(self) -> Phase5ExecutionOutcome | None:
        """Return the most recent Phase 5 execution and verification outcome."""
        return self._last_phase5_outcome

    @property
    def patch_application_authority(self) -> PatchApplicationAuthority:
        """Return or lazily construct the PatchApplicationAuthority."""
        if self._patch_applier is None:
            approval_service = getattr(self._tool_executor, "approval_service", None)
            if approval_service is None:
                raise PatchApprovalRequiredError(
                    "ToolExecutor has no configured ApprovalService."
                )
            self._patch_applier = PatchApplicationAuthority(
                workspace=self._workspace,
                approval_service=approval_service,
                ledger=self._ledger,
                telemetry_context=self._telemetry_context,
            )
        return self._patch_applier

    @property
    def controlled_execution_authority(self) -> ControlledExecutionAuthority:
        """Return or lazily construct the ControlledExecutionAuthority."""
        if self._controlled_runner is None:
            self._controlled_runner = ControlledExecutionAuthority(
                workspace=self._workspace,
                ledger=self._ledger,
                telemetry_context=self._telemetry_context,
            )
        return self._controlled_runner

    @property
    def patch_verification_authority(self) -> PatchVerificationAuthority:
        """Return or lazily construct the PatchVerificationAuthority."""
        if self._patch_verifier is None:
            self._patch_verifier = PatchVerificationAuthority(
                verification_engine=self._verification_engine,
                recovery_coordinator=self._recovery_coordinator,
                ledger=self._ledger,
                telemetry_context=self._telemetry_context,
            )
        return self._patch_verifier

    def advance_stage(self, stage: SWETaskStage) -> None:
        """Advance the workflow state machine to the specified stage."""
        if not isinstance(stage, SWETaskStage):
            raise TypeError("stage must be an SWETaskStage instance.")

        target_idx = STAGE_ORDER.index(stage)

        # Enforce all prior stages must be completed
        for prior_idx in range(target_idx):
            prior_stage = STAGE_ORDER[prior_idx]
            if prior_stage not in self._completed_stages:
                raise WorkflowSequenceError(
                    f"Cannot advance to '{stage.value}' before completing prior stage '{prior_stage.value}'."
                )

        if self._current_stage is not None and self._current_stage not in self._completed_stages:
            self._completed_stages.append(self._current_stage)

        self._current_stage = stage

    def complete_stage(self, stage: SWETaskStage) -> None:
        """Explicitly mark a stage as completed."""
        if stage != self._current_stage:
            raise WorkflowSequenceError(
                f"Cannot complete stage '{stage.value}' because current active stage is '{getattr(self._current_stage, 'value', None)}'."
            )
        if stage not in self._completed_stages:
            self._completed_stages.append(stage)

    def validate_tool_for_stage(self, stage: SWETaskStage, tool_name: str) -> None:
        """Verify that a tool is permitted in the designated stage."""
        spec = self._task_graph.get_spec(stage)

        if tool_name not in spec.allowed_tools:
            if tool_name in FILE_MODIFICATION_TOOLS and not spec.allows_file_modification:
                raise DisallowedFileModificationError(
                    f"Stage '{stage.value}' prohibits file modification tools like '{tool_name}'."
                )
            raise DisallowedStageToolError(
                f"Tool '{tool_name}' is not permitted in stage '{stage.value}'. "
                f"Allowed tools: {sorted(spec.allowed_tools)}"
            )

    def _categorize_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: ToolExecutionResult,
    ) -> tuple[EvidenceCategory, str, dict[str, Any]]:
        """Map tool execution to a controlled evidence category, summary, and safe metadata."""
        out = result.output if isinstance(result.output, dict) else {}

        if tool_name == "list_files":
            cat = EvidenceCategory.REPOSITORY_STATE
            path = arguments.get("path", ".")
            total = out.get("total_count", 0)
            summary = f"Listed repository files in '{path}' ({total} entries)"
            meta = {"path": path, "total_count": total, "truncated": out.get("truncated", False)}
        elif tool_name == "read_file":
            cat = EvidenceCategory.FILE_OBSERVATION
            path = arguments.get("path", "")
            size = out.get("size", 0)
            summary = f"Read repository file '{path}' ({size} bytes)"
            meta = {"path": path, "size": size, "lines_read": out.get("lines_read", 0)}
        elif tool_name == "search_files":
            cat = EvidenceCategory.DIAGNOSTIC_RESULT
            query = arguments.get("query", "")
            matches = out.get("total_matches", 0)
            summary = f"Searched repository files for '{query}' ({matches} matches)"
            meta = {"query": query, "total_matches": matches}
        elif tool_name == "diff":
            cat = EvidenceCategory.DIFF_RESULT
            path = arguments.get("path", "")
            identical = out.get("identical", False)
            added = out.get("lines_added", 0)
            removed = out.get("lines_removed", 0)
            summary = f"Diff on '{path}': {'identical' if identical else f'+{added} -{removed}'}"
            meta = {"path": path, "identical": identical, "lines_added": added, "lines_removed": removed}
        elif tool_name in ("write_file", "apply_change"):
            cat = EvidenceCategory.FILE_CHANGE
            path = arguments.get("path", "")
            if tool_name == "write_file":
                summary = f"Wrote file '{path}' ({out.get('bytes_written', 0)} bytes)"
                meta = {
                    "path": path,
                    "bytes_written": out.get("bytes_written", 0),
                    "checksum": out.get("checksum", ""),
                    "created": out.get("created", False),
                }
            else:
                summary = f"Applied change to '{path}'"
                meta = {
                    "path": path,
                    "previous_hash": out.get("previous_hash", ""),
                    "new_hash": out.get("new_hash", ""),
                    "lines_added": out.get("lines_added", 0),
                    "lines_removed": out.get("lines_removed", 0),
                    "diff_summary": str(out.get("diff_summary", ""))[:500],
                }
        elif tool_name == "run_tests":
            cat = EvidenceCategory.TEST_RESULT
            target = arguments.get("target", "")
            exit_code = out.get("exit_code")
            status_str = out.get("status", "unknown")
            stdout_sample = str(out.get("stdout", ""))[:500].strip()
            stderr_sample = str(out.get("stderr", ""))[:500].strip()
            out_summary = f"{stdout_sample}\n{stderr_sample}".strip() if (stdout_sample or stderr_sample) else ""
            summary = f"Ran tests target='{target}' exit_code={exit_code} status={status_str}"
            meta = {
                "target": target,
                "exit_code": exit_code,
                "status": status_str,
                "duration": out.get("duration", 0.0),
                "output_summary": out_summary[:500],
            }
        else:
            cat = EvidenceCategory.COMMAND_RESULT
            summary = f"Executed {tool_name}"
            meta = {"tool_name": tool_name}

        return cat, summary, meta

    def execute_tool(
        self,
        stage: SWETaskStage,
        agent: Agent,
        tool_name: str,
        arguments: dict[str, Any],
        execution_id: UUID | None = None,
        approval_id: UUID | None = None,
    ) -> ToolExecutionResult:
        """Execute a tool within the strict boundaries of an SWE stage with provenance."""
        if self._current_stage is None:
            self.advance_stage(stage)
        elif self._current_stage != stage:
            raise WorkflowSequenceError(
                f"Attempted to execute tool in stage '{stage.value}', but workflow is currently at '{self._current_stage.value}'."
            )

        self.validate_tool_for_stage(stage, tool_name)

        effective_execution_id = execution_id or uuid4()

        result = self._tool_executor.execute(
            agent=agent,
            tool_name=tool_name,
            arguments=arguments,
            execution_id=effective_execution_id,
            approval_id=approval_id,
        )

        category, summary, safe_meta = self._categorize_tool_execution(tool_name, arguments, result)
        safe_meta.update({
            "tool_name": tool_name,
            "agent_id": str(agent.id),
        })

        if result.success:
            if tool_name == "run_tests" and result.output is not None:
                # Capture test output for subsequent verification (bounded to 65536 chars)
                if isinstance(result.output, dict):
                    stdout = str(result.output.get("stdout", ""))
                    stderr = str(result.output.get("stderr", ""))
                else:
                    stdout = str(getattr(result.output, "stdout", ""))
                    stderr = str(getattr(result.output, "stderr", ""))
                combined = f"{stdout}\n{stderr}".strip()
                self._last_test_output = combined[:65536]
                content = f"Ran tests target='{arguments.get('target', '')}' (exit_code={safe_meta.get('exit_code')}, status={safe_meta.get('status')})."
            else:
                content = f"Executed {tool_name} successfully."

            self._ledger.record_observed(
                stage=stage,
                source=f"tool:{tool_name}",
                content=content,
                category=category,
                summary=summary,
                task_id=self._task_id,
                execution_id=effective_execution_id,
                tool_name=tool_name,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata=safe_meta,
            )
        else:
            safe_meta["error"] = result.error
            self._ledger.record_observed(
                stage=stage,
                source=f"tool:{tool_name}",
                content=f"Tool execution failed: {result.error}",
                category=category,
                summary=f"Failed {tool_name}: {result.error}",
                task_id=self._task_id,
                execution_id=effective_execution_id,
                tool_name=tool_name,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata=safe_meta,
            )

        return result

    def analyze_failure(
        self,
        agent: Agent,
        test_output: str | None = None,
        repository_files: Sequence[tuple[str | Path, str] | str | Path] = (),
        execution_id: UUID | None = None,
        fallback_on_error: bool = True,
    ) -> FailureAnalysisProposal:
        """Perform model-assisted failure analysis within strict context boundaries."""
        stage_val = getattr(self._current_stage, "value", None)
        if self._current_stage != SWETaskStage.ANALYZE_FAILURE:
            raise WorkflowSequenceError(
                f"Cannot analyze failure during stage '{stage_val}'."
            )

        effective_execution_id = execution_id or uuid4()
        effective_output = test_output if test_output is not None else self._last_test_output
        tg = getattr(self, "_task_graph", None)
        plan_obj = getattr(tg, "plan", None)
        obj_val = getattr(tg, "objective", None) or getattr(plan_obj, "objective", None)
        objective = str(obj_val) if obj_val else "Autonomous software engineering mission"

        if self._cognitive_service is not None:
            try:
                proposal = self._cognitive_service.analyze_failure(
                    task_objective=objective,
                    task_id=self._task_id,
                    execution_id=effective_execution_id,
                    test_output=effective_output,
                    repository_files=repository_files,
                    evidence_items=self._ledger.get_items(),
                    execution_identity=self._execution_identity,
                    fallback_on_error=fallback_on_error,
                )
            except Exception as exc:
                if fallback_on_error:
                    proposal = SWECognitiveService.create_fallback_analysis(
                        task_id=self._task_id,
                        execution_id=effective_execution_id,
                        reason=str(exc),
                    )
                else:
                    raise
        else:
            if not fallback_on_error:
                raise CognitiveModelUnavailableError(
                    "Cognitive service is not configured on this coordinator."
                )
            proposal = SWECognitiveService.create_fallback_analysis(
                task_id=self._task_id,
                execution_id=effective_execution_id,
                reason="Cognitive service not configured; using deterministic fallback.",
            )

        self._last_failure_analysis = proposal
        self._ledger.record_claimed(
            stage=SWETaskStage.ANALYZE_FAILURE,
            source=f"cognitive:{proposal.provider_name}",
            content=(
                f"Failure Analysis [{proposal.failure_classification}]: "
                f"{proposal.root_cause_hypothesis} "
                f"(Action: {proposal.proposed_next_action}, Confidence: {proposal.confidence})"
            ),
            category=EvidenceCategory.DIAGNOSTIC_RESULT,
            summary=f"Analysis: {proposal.failure_classification}",
            task_id=self._task_id,
            execution_id=effective_execution_id,
            request_id=self._telemetry_context.request_id,
            trace_id=self._telemetry_context.trace_id,
            workspace_root=str(self._workspace.repository_root),
            metadata=proposal.to_dict(),
        )

        return proposal

    def formulate_fix(
        self,
        agent: Agent,
        diagnosis: FailureAnalysisProposal | str | None = None,
        repository_files: Sequence[tuple[str | Path, str] | str | Path] = (),
        execution_id: UUID | None = None,
        fallback_on_error: bool = True,
    ) -> FixProposal:
        """Perform model-assisted fix formulation within strict context boundaries."""
        stage_val = getattr(self._current_stage, "value", None)
        if self._current_stage != SWETaskStage.FORMULATE_FIX:
            raise WorkflowSequenceError(
                f"Cannot formulate fix during stage '{stage_val}'."
            )

        effective_execution_id = execution_id or uuid4()
        effective_diagnosis = (
            diagnosis
            if diagnosis is not None
            else (self._last_failure_analysis or "General automated test failure")
        )
        tg = getattr(self, "_task_graph", None)
        plan_obj = getattr(tg, "plan", None)
        obj_val = getattr(tg, "objective", None) or getattr(plan_obj, "objective", None)
        objective = str(obj_val) if obj_val else "Autonomous software engineering mission"

        if self._cognitive_service is not None:
            try:
                proposal = self._cognitive_service.formulate_fix(
                    task_objective=objective,
                    diagnosis=effective_diagnosis,
                    task_id=self._task_id,
                    execution_id=effective_execution_id,
                    repository_files=repository_files,
                    evidence_items=self._ledger.get_items(),
                    execution_identity=self._execution_identity,
                    fallback_on_error=fallback_on_error,
                )
            except Exception as exc:
                if fallback_on_error:
                    default_file = (
                        str(repository_files[0][0])
                        if (repository_files and isinstance(repository_files[0], tuple))
                        else (str(repository_files[0]) if repository_files else "src/main.py")
                    )
                    proposal = SWECognitiveService.create_fallback_fix(
                        task_id=self._task_id,
                        execution_id=effective_execution_id,
                        default_file=default_file,
                        reason=str(exc),
                    )
                else:
                    raise
        else:
            if not fallback_on_error:
                raise CognitiveModelUnavailableError(
                    "Cognitive service is not configured on this coordinator."
                )
            default_file = (
                str(repository_files[0][0])
                if (repository_files and isinstance(repository_files[0], tuple))
                else (str(repository_files[0]) if repository_files else "src/main.py")
            )
            proposal = SWECognitiveService.create_fallback_fix(
                task_id=self._task_id,
                execution_id=effective_execution_id,
                default_file=default_file,
                reason="Cognitive service not configured; using deterministic fallback.",
            )

        self._last_fix_proposal = proposal
        # Update self._formulated_plan so subsequent stages and tests maintain compatibility
        self._formulated_plan = proposal.to_proposed_fix_plan()

        self._ledger.record_claimed(
            stage=SWETaskStage.FORMULATE_FIX,
            source=f"cognitive:{proposal.provider_name}",
            content=(
                f"Fix Proposal for {list(proposal.affected_files)}: "
                f"{proposal.change_intent} "
                f"(Plan: {list(proposal.validation_plan)}, Confidence: {proposal.confidence})"
            ),
            category=EvidenceCategory.PROPOSED_CHANGE,
            summary=f"Proposed fix for {list(proposal.affected_files)}",
            task_id=self._task_id,
            execution_id=effective_execution_id,
            request_id=self._telemetry_context.request_id,
            trace_id=self._telemetry_context.trace_id,
            workspace_root=str(self._workspace.repository_root),
            metadata=proposal.to_dict(),
        )

        return proposal

    def synthesize_patch(
        self,
        agent: Agent,
        fix_proposal: FixProposal | None = None,
        repository_files: Sequence[tuple[str | Path, str] | str | Path] = (),
        execution_id: UUID | None = None,
        fallback_on_error: bool = True,
    ) -> PatchProposal:
        """Synthesize concrete code patches from a validated FixProposal."""
        stage_val = getattr(self._current_stage, "value", None)
        if self._current_stage not in (SWETaskStage.FORMULATE_FIX, SWETaskStage.IMPLEMENT_CHANGE):
            raise WorkflowSequenceError(
                f"Cannot synthesize patch during stage '{stage_val}'."
            )

        effective_execution_id = execution_id or uuid4()
        target_fix = fix_proposal or self._last_fix_proposal
        if target_fix is None:
            raise WorkflowSequenceError("Cannot synthesize patch before a fix is formulated.")

        tg = getattr(self, "_task_graph", None)
        plan_obj = getattr(tg, "plan", None)
        obj_val = getattr(tg, "objective", None) or getattr(plan_obj, "objective", None)
        objective = str(obj_val) if obj_val else "Autonomous software engineering mission"

        if self._cognitive_service is not None:
            try:
                proposal = self._cognitive_service.synthesize_patch(
                    fix_proposal=target_fix,
                    task_objective=objective,
                    task_id=self._task_id,
                    execution_id=effective_execution_id,
                    repository_files=repository_files,
                    execution_identity=self._execution_identity,
                    fallback_on_error=fallback_on_error,
                )
            except Exception as exc:
                if fallback_on_error:
                    proposal = SWECognitiveService.create_fallback_patch(
                        fix_proposal=target_fix,
                        task_id=self._task_id,
                        execution_id=effective_execution_id,
                        reason=str(exc),
                    )
                else:
                    raise
        else:
            if not fallback_on_error:
                raise CognitiveModelUnavailableError(
                    "Cognitive service is not configured on this coordinator."
                )
            proposal = SWECognitiveService.create_fallback_patch(
                fix_proposal=target_fix,
                task_id=self._task_id,
                execution_id=effective_execution_id,
                reason="Cognitive service not configured; using deterministic fallback.",
            )

        self._last_patch_proposal = proposal

        # Record CLAIMED evidence for the patch proposal
        assert self._current_stage is not None
        self._ledger.record_claimed(
            stage=self._current_stage,
            source=f"cognitive:{proposal.provider_name}",
            content=(
                f"Patch Proposal for {list(proposal.affected_files)}: "
                f"+{proposal.total_lines_added}/-{proposal.total_lines_removed} "
                f"(Confidence: {proposal.confidence})"
            ),
            category=EvidenceCategory.PROPOSED_CHANGE,
            summary=f"Patch proposal for {list(proposal.affected_files)}",
            task_id=self._task_id,
            execution_id=effective_execution_id,
            request_id=self._telemetry_context.request_id,
            trace_id=self._telemetry_context.trace_id,
            workspace_root=str(self._workspace.repository_root),
            metadata=proposal.to_dict(),
        )

        # Record OBSERVED evidence for diff inspection and syntax validation if diff exists
        if proposal.unified_diff:
            self._ledger.record_observed(
                stage=self._current_stage,
                source="patch_validator",
                content=proposal.unified_diff[:2000],
                category=EvidenceCategory.DIFF_RESULT,
                summary=(
                    f"Diff: +{proposal.total_lines_added}/-{proposal.total_lines_removed}"
                ),
                task_id=self._task_id,
                execution_id=effective_execution_id,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata={
                    "lines_added": proposal.total_lines_added,
                    "lines_removed": proposal.total_lines_removed,
                    "syntax_valid": all(r.valid for r in proposal.syntax_results),
                },
            )

        return proposal

    def request_patch_approval(
        self,
        agent: Agent,
        patch_proposal: PatchProposal | None = None,
        execution_id: UUID | None = None,
    ) -> PatchApprovalPackage:
        """Submit a patch proposal for explicit ApprovalService review and authorization."""
        stage_val = getattr(self._current_stage, "value", None)
        if self._current_stage not in (SWETaskStage.FORMULATE_FIX, SWETaskStage.IMPLEMENT_CHANGE):
            raise WorkflowSequenceError(
                f"Cannot request patch approval during stage '{stage_val}'."
            )

        approval_service = getattr(self._tool_executor, "_approval_service", None)
        if approval_service is None:
            raise PatchApprovalRequiredError(
                "ApprovalService is not configured; cannot request patch approval."
            )

        target_patch = patch_proposal or self._last_patch_proposal
        if target_patch is None:
            raise WorkflowSequenceError("No patch proposal available to request approval for.")

        effective_execution_id = execution_id or uuid4()
        pkg = request_patch_approval(
            patch_proposal=target_patch,
            agent=agent,
            approval_service=approval_service,
            execution_id=effective_execution_id,
        )
        self._last_patch_approval = pkg
        return pkg

    def refresh_patch_approval(self) -> PatchApprovalPackage | None:
        """Refresh current patch approval package status against ApprovalService."""
        approval_service = getattr(self._tool_executor, "_approval_service", None)
        if approval_service is None or self._last_patch_approval is None:
            return self._last_patch_approval

        pkg = refresh_patch_approval(self._last_patch_approval, approval_service)
        self._last_patch_approval = pkg
        return pkg

    def apply_approved_patch(
        self,
        package: PatchApprovalPackage | None = None,
        execution_id: UUID | None = None,
    ) -> PatchApplicationResult:
        """Apply an approved patch during IMPLEMENT_CHANGE stage under strict controls."""
        if self._current_stage != SWETaskStage.IMPLEMENT_CHANGE:
            raise WorkflowSequenceError(
                f"Cannot apply patch during stage '{getattr(self._current_stage, 'value', None)}'."
            )

        target_pkg = package or self._last_patch_approval
        if target_pkg is None:
            raise UnapprovedPatchError("No patch approval package available to apply.")

        effective_execution_id = (
            execution_id
            or (target_pkg.execution_id if target_pkg else None)
            or uuid4()
        )
        result = self.patch_application_authority.apply_patch(
            approval_package=target_pkg,
            execution_id=effective_execution_id,
        )
        self._last_application_result = result
        return result

    def run_controlled_tests(
        self,
        target: str = "",
        timeout_seconds: int = 60,
        fail_fast: bool = False,
        verbose: bool = False,
        execution_id: UUID | None = None,
    ) -> ControlledTestResult:
        """Run policy-controlled allowlisted tests during RUN_TESTS stage."""
        if self._current_stage != SWETaskStage.RUN_TESTS:
            raise WorkflowSequenceError(
                f"Cannot run tests during stage '{getattr(self._current_stage, 'value', None)}'."
            )

        effective_execution_id = (
            execution_id
            or (self._last_application_result.execution_id if self._last_application_result else None)
            or uuid4()
        )
        result = self.controlled_execution_authority.run_tests(
            target=target,
            timeout_seconds=timeout_seconds,
            fail_fast=fail_fast,
            verbose=verbose,
            execution_id=effective_execution_id,
            task_id=self._task_id,
        )
        self._last_test_output = f"{result.stdout}\n{result.stderr}".strip()
        self._last_controlled_test_result = result
        return result

    def verify_patch_execution(
        self,
        expected_requirements: list[str] | None = None,
        execution_id: UUID | None = None,
    ) -> Phase5ExecutionOutcome:
        """Verify patch application and test outcomes using VerificationEngine during VERIFY."""
        if self._current_stage != SWETaskStage.VERIFY:
            raise WorkflowSequenceError(
                f"Cannot execute verification during stage "
                f"'{getattr(self._current_stage, 'value', None)}'."
            )

        if self._last_application_result is None:
            raise WorkflowSequenceError("Cannot verify without prior patch application result.")

        effective_execution_id = (
            execution_id
            or (self._last_application_result.execution_id if self._last_application_result else None)
            or uuid4()
        )
        outcome = self.patch_verification_authority.verify_execution(
            application_result=self._last_application_result,
            test_result=self._last_controlled_test_result,
            expected_requirements=expected_requirements,
            execution_id=effective_execution_id,
        )
        self._last_phase5_outcome = outcome
        self._last_verification_result = outcome.verification_result
        return outcome

    def record_formulation(
        self,
        plan: ProposedFixPlan,
        source: str = "agent:formulator",
    ) -> EvidenceItem:
        """Record the proposed change plan formulated during FORMULATE_FIX."""
        if self._current_stage != SWETaskStage.FORMULATE_FIX:
            raise WorkflowSequenceError(
                f"Cannot record formulation plan during stage '{getattr(self._current_stage, 'value', None)}'."
            )

        if not isinstance(plan, ProposedFixPlan):
            raise TypeError("plan must be a ProposedFixPlan instance.")

        self._formulated_plan = plan
        return self._ledger.record_claimed(
            stage=SWETaskStage.FORMULATE_FIX,
            source=source,
            content=(
                f"Proposed fix for targets {list(plan.target_files)}: "
                f"{plan.intended_modification} (Strategy: {plan.validation_strategy})"
            ),
            category=EvidenceCategory.PROPOSED_CHANGE,
            summary=f"Proposed fix for {list(plan.target_files)}",
            task_id=self._task_id,
            request_id=self._telemetry_context.request_id,
            trace_id=self._telemetry_context.trace_id,
            workspace_root=str(self._workspace.repository_root),
            metadata=plan.to_dict(),
        )

    def record_claimed(
        self,
        stage: SWETaskStage,
        source: str,
        content: str,
        category: EvidenceCategory | None = None,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        """Record claimed evidence in the active stage with provenance."""
        return self._ledger.record_claimed(
            stage=stage,
            source=source,
            content=content,
            category=category,
            summary=summary,
            task_id=self._task_id,
            request_id=self._telemetry_context.request_id,
            trace_id=self._telemetry_context.trace_id,
            workspace_root=str(self._workspace.repository_root),
            metadata=metadata,
        )

    def verify_fix(
        self,
        execution_id: UUID,
        expected_requirements: list[str],
        custom_output: str | None = None,
    ) -> VerificationResult:
        """Formally verify the execution outcome using ORION VerificationEngine."""
        if self._current_stage != SWETaskStage.VERIFY:
            raise WorkflowSequenceError(
                f"Cannot execute verify_fix during stage '{getattr(self._current_stage, 'value', None)}'."
            )

        output_to_verify = custom_output if custom_output is not None else self._last_test_output

        verification_result = self._verification_engine.verify_output(
            execution_id=execution_id,
            output=output_to_verify,
            expected_requirements=expected_requirements,
        )

        self._last_verification_result = verification_result

        if verification_result.status == VerificationStatus.PASSED:
            self._ledger.record_verified(
                stage=SWETaskStage.VERIFY,
                source="VerificationEngine",
                content=f"Verification PASSED: {verification_result.reason}",
                category=EvidenceCategory.VERIFICATION_RESULT,
                summary="Authoritative verification passed",
                task_id=self._task_id,
                execution_id=execution_id,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata={
                    "verification_id": str(verification_result.id),
                    "execution_id": str(execution_id),
                    "status": verification_result.status.value,
                    "requirements": expected_requirements,
                    "metadata": verification_result.metadata,
                },
            )
        else:
            self._ledger.record_observed(
                stage=SWETaskStage.VERIFY,
                source="VerificationEngine",
                content=f"Verification FAILED: {verification_result.reason}",
                category=EvidenceCategory.VERIFICATION_RESULT,
                summary="Authoritative verification failed",
                task_id=self._task_id,
                execution_id=execution_id,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata={
                    "verification_id": str(verification_result.id),
                    "execution_id": str(execution_id),
                    "status": verification_result.status.value,
                    "requirements": expected_requirements,
                    "metadata": verification_result.metadata,
                },
            )

        return verification_result

    def handle_stage_failure(
        self,
        execution: AgentExecution,
        execution_context: RecoveryExecutionContext | None = None,
    ) -> RecoveryResult:
        """Invoke ORION RecoveryCoordinator for a failed execution and record recovery event."""
        if self._recovery_coordinator is None:
            raise ValueError("RecoveryCoordinator is not configured on this coordinator.")

        recovery_result = self._recovery_coordinator.handle_failure(
            execution=execution,
            execution_context=execution_context,
        )

        failure_type_val = execution.failure.failure_type.value if execution.failure else "unknown"
        failure_msg = execution.failure.message if execution.failure else ""

        self._ledger.record_observed(
            stage=self._current_stage or SWETaskStage.RUN_TESTS,
            source="RecoveryCoordinator",
            content=(
                f"Recovery decision: {recovery_result.decision.strategy.value}, "
                f"action: {recovery_result.action.action_type.value}"
            ),
            category=EvidenceCategory.RECOVERY_EVENT,
            summary=f"Recovery initiated for failure '{failure_type_val}'",
            task_id=self._task_id,
            execution_id=execution.id,
            request_id=self._telemetry_context.request_id,
            trace_id=self._telemetry_context.trace_id,
            workspace_root=str(self._workspace.repository_root),
            metadata={
                "execution_id": str(execution.id),
                "failure_type": failure_type_val,
                "failure_message": failure_msg,
                "recovery_strategy": recovery_result.decision.strategy.value,
                "recovery_action": recovery_result.action.action_type.value,
            },
        )

        return recovery_result

    def evaluate_mission(
        self,
        required_stages: Sequence[SWETaskStage] | None = None,
        required_categories: Sequence[EvidenceCategory] | None = None,
    ) -> MissionEvaluation:
        """Evaluate the SWE mission deterministically using SWEEvaluator."""
        evaluator = SWEEvaluator()
        return evaluator.evaluate(
            ledger=self._ledger,
            completed_stages=self._completed_stages,
            required_stages=required_stages,
            required_categories=required_categories,
        )

    def generate_report(
        self,
        summary: str = "",
        required_categories: Sequence[EvidenceCategory] | None = None,
    ) -> SWEReport:
        """Generate structured mission report with evidence categorization and deterministic evaluation."""
        if self._current_stage != SWETaskStage.GENERATE_REPORT:
            raise WorkflowSequenceError(
                f"Cannot generate report during stage '{getattr(self._current_stage, 'value', None)}'."
            )

        evaluation = self.evaluate_mission(required_categories=required_categories)

        if evaluation.status == EvaluationStatus.PASS:
            status = "verified_success"
        elif evaluation.status == EvaluationStatus.FAIL:
            status = "failed"
        else:
            status = "inconclusive"

        files_modified = tuple(sorted({
            str(item.metadata["path"])
            for item in self._ledger.get_items(category=EvidenceCategory.FILE_CHANGE)
            if "path" in item.metadata and item.metadata["path"]
        }))

        report = SWEReport.create(
            mission_id=self._mission_id,
            task_id=self._task_id,
            workspace_root=str(self._workspace.repository_root),
            ledger=self._ledger,
            status=status,
            evaluation=evaluation,
            stages_completed=tuple(self._completed_stages),
            files_modified=files_modified,
            summary=summary or evaluation.summary,
        )

        self.complete_stage(SWETaskStage.GENERATE_REPORT)
        return report
