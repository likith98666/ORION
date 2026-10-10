"""Controlled Cognitive SWE Service connecting ModelRuntime to SWE stages safely."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from orion.config.model_config import ModelConfig
from orion.core.swe.cognitive.contracts import (
    FailureAnalysisProposal,
    FixProposal,
    PatchProposal,
)
from orion.core.swe.cognitive.errors import (
    CognitiveModelUnavailableError,
    InvalidProposalError,
)
from orion.core.swe.cognitive.patch_synthesizer import PatchSynthesizer
from orion.core.swe.cognitive.patch_validator import PatchValidator
from orion.core.swe.cognitive.validator import ProposalValidator
from orion.core.swe.evidence import EvidenceItem
from orion.core.workspace.models import ExecutionIdentity, Workspace
from orion.models.errors import sanitize_error_message
from orion.models.runtime.runtime import ModelRuntime

if TYPE_CHECKING:
    from orion.models.context.assembler import ContextAssembler

ANALYSIS_FORMAT_INSTRUCTIONS = """Respond strictly with a valid JSON object matching this schema:
{
  "failure_class": "string (e.g. assertion_error, syntax_error, runtime_error, logic_error)",
  "root_cause_hypothesis": "string explaining the suspected root cause",
  "observations": ["observation 1", "observation 2"],
  "affected_files": ["workspace/relative/path.py"],
  "proposed_action": "string describing next recommended step",
  "confidence": 0.85
}
Do not include any conversational filler. Only output valid JSON."""

FORMULATION_FORMAT_INSTRUCTIONS = """Respond strictly with a valid JSON object matching this schema:
{
  "change_intent": "string describing what needs to be changed and why",
  "affected_files": ["workspace/relative/path.py"],
  "modifications": ["detailed description of modification 1"],
  "rationale": "technical justification for the change",
  "expected_effect": "expected behavior after change is applied",
  "validation_plan": ["test to run to verify"],
  "confidence": 0.90
}
Do not include any conversational filler. Only output valid JSON."""


class SWECognitiveService:
    """Orchestrates model-assisted analysis and fix formulation under deterministic security."""

    def __init__(
        self,
        model_runtime: ModelRuntime,
        model_config: ModelConfig,
        workspace: Workspace,
        context_assembler: ContextAssembler | None = None,
        validator: ProposalValidator | None = None,
        patch_synthesizer: PatchSynthesizer | None = None,
        patch_validator: PatchValidator | None = None,
    ) -> None:
        if not isinstance(model_runtime, ModelRuntime):
            raise TypeError("model_runtime must be a ModelRuntime instance.")
        if not isinstance(model_config, ModelConfig):
            raise TypeError("model_config must be a ModelConfig instance.")
        if not isinstance(workspace, Workspace):
            raise TypeError("workspace must be a Workspace instance.")

        self._runtime = model_runtime
        self._config = model_config
        self._workspace = workspace
        if context_assembler is not None:
            self._assembler = context_assembler
        else:
            from orion.models.context.assembler import ContextAssembler

            self._assembler = ContextAssembler()
        self._validator = validator or ProposalValidator()
        self._patch_synthesizer = patch_synthesizer or PatchSynthesizer(
            model_runtime=self._runtime,
            model_config=self._config,
            workspace=self._workspace,
            context_assembler=self._assembler,
            validator=patch_validator,
        )

    @property
    def model_runtime(self) -> ModelRuntime:
        return self._runtime

    @property
    def model_config(self) -> ModelConfig:
        return self._config

    @property
    def patch_synthesizer(self) -> PatchSynthesizer:
        return self._patch_synthesizer

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    def _normalize_repository_files(
        self,
        repository_files: Sequence[tuple[str | Path, str] | str | Path],
    ) -> list[tuple[str | Path, str]]:
        normalized: list[tuple[str | Path, str]] = []
        for item in repository_files:
            if isinstance(item, tuple) and len(item) >= 2:
                normalized.append((item[0], item[1]))
            elif isinstance(item, (str, Path)):
                try:
                    resolved = self._workspace.resolve_path(str(item))
                    if resolved.is_file():
                        content = resolved.read_text(encoding="utf-8", errors="replace")
                        normalized.append((str(item), content))
                except Exception:
                    continue
        return normalized

    def analyze_failure(
        self,
        task_objective: str,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        test_output: str | None = None,
        repository_files: Sequence[tuple[str | Path, str] | str | Path] = (),
        evidence_items: Sequence[EvidenceItem] = (),
        execution_identity: ExecutionIdentity | None = None,
        fallback_on_error: bool = False,
    ) -> FailureAnalysisProposal:
        """Perform model-assisted failure analysis within strict context boundaries."""
        exec_outputs: list[tuple[str, str]] = []
        if test_output and test_output.strip():
            exec_outputs.append(("run_tests", test_output.strip()))

        normalized_files = self._normalize_repository_files(repository_files)

        secure_ctx = self._assembler.build_context(
            task_objective=task_objective,
            task_instructions=(
                "Analyze the failure output and repository context to identify root cause."
            ),
            repository_files=normalized_files,
            execution_outputs=exec_outputs,
            evidence_items=evidence_items,
            output_format_instructions=ANALYSIS_FORMAT_INSTRUCTIONS,
            workspace_root=self._workspace.repository_root,
            stage="analyze_failure",
            execution_identity=execution_identity,
        )

        model_req = secure_ctx.to_model_request(
            structured_output=True,
            response_format={"type": "json_object"},
            request_id=str(execution_id) if execution_id else None,
        )

        try:
            response = self._runtime.generate(self._config, model_req)
            proposal = self._validator.validate_failure_analysis(response.text, self._workspace)
            # Bind execution provenance
            return FailureAnalysisProposal(
                failure_classification=proposal.failure_classification,
                root_cause_hypothesis=proposal.root_cause_hypothesis,
                supporting_observations=proposal.supporting_observations,
                relevant_files=proposal.relevant_files,
                confidence=proposal.confidence,
                proposed_next_action=proposal.proposed_next_action,
                reasoning_summary=proposal.reasoning_summary,
                task_id=task_id,
                execution_id=execution_id,
                provider_name=response.provider_name,
                model_name=response.model_name,
                raw_response=response.text,
            )
        except Exception as exc:
            if fallback_on_error:
                return self.create_fallback_analysis(task_id, execution_id, str(exc))
            clean_msg = sanitize_error_message(f"Cognitive failure analysis failed: {exc}")
            if isinstance(exc, InvalidProposalError):
                raise
            raise CognitiveModelUnavailableError(clean_msg) from exc

    def formulate_fix(
        self,
        task_objective: str,
        diagnosis: FailureAnalysisProposal | str,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        repository_files: Sequence[tuple[str | Path, str] | str | Path] = (),
        evidence_items: Sequence[EvidenceItem] = (),
        execution_identity: ExecutionIdentity | None = None,
        fallback_on_error: bool = False,
    ) -> FixProposal:
        """Perform model-assisted fix formulation within strict context boundaries."""
        diag_text = (
            f"Diagnosis: {diagnosis.failure_classification}\n"
            f"Root Cause: {diagnosis.root_cause_hypothesis}\n"
            f"Observations: {'; '.join(diagnosis.supporting_observations)}"
            if isinstance(diagnosis, FailureAnalysisProposal)
            else str(diagnosis)
        )

        diag_ref = (
            diagnosis.failure_classification
            if isinstance(diagnosis, FailureAnalysisProposal)
            else "provided_diagnosis"
        )

        instructions = (
            f"Formulate a structured code repair plan based on this diagnosis:\n{diag_text}\n"
            f"Identify target files, intended modifications, and a validation strategy."
        )

        normalized_files = self._normalize_repository_files(repository_files)

        secure_ctx = self._assembler.build_context(
            task_objective=task_objective,
            task_instructions=instructions,
            repository_files=normalized_files,
            evidence_items=evidence_items,
            output_format_instructions=FORMULATION_FORMAT_INSTRUCTIONS,
            workspace_root=self._workspace.repository_root,
            stage="formulate_fix",
            execution_identity=execution_identity,
        )

        model_req = secure_ctx.to_model_request(
            structured_output=True,
            response_format={"type": "json_object"},
            request_id=str(execution_id) if execution_id else None,
        )

        try:
            response = self._runtime.generate(self._config, model_req)
            proposal = self._validator.validate_fix_proposal(response.text, self._workspace)
            return FixProposal(
                change_intent=proposal.change_intent,
                affected_files=proposal.affected_files,
                proposed_modifications=proposal.proposed_modifications,
                rationale=proposal.rationale,
                expected_effect=proposal.expected_effect,
                validation_plan=proposal.validation_plan,
                confidence=proposal.confidence,
                diagnosis_reference=diag_ref,
                task_id=task_id,
                execution_id=execution_id,
                provider_name=response.provider_name,
                model_name=response.model_name,
                raw_response=response.text,
            )
        except Exception as exc:
            if fallback_on_error:
                default_file = (
                    normalized_files[0][0]
                    if normalized_files
                    else "src/main.py"
                )
                return self.create_fallback_fix(
                    task_id=task_id,
                    execution_id=execution_id,
                    default_file=str(default_file),
                    reason=str(exc),
                )
            clean_msg = sanitize_error_message(f"Cognitive fix formulation failed: {exc}")
            if isinstance(exc, InvalidProposalError):
                raise
            raise CognitiveModelUnavailableError(clean_msg) from exc

    @staticmethod
    def create_fallback_analysis(
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        reason: str = "Fallback analysis active",
    ) -> FailureAnalysisProposal:
        return FailureAnalysisProposal(
            failure_classification="test_failure",
            root_cause_hypothesis=(
                "Deterministic analysis fallback: automated test suite reported failures."
            ),
            supporting_observations=(
                "Deterministic fallback active due to model unavailability",
            ),
            relevant_files=(),
            confidence=0.5,
            proposed_next_action="inspect_repository_and_formulate_fix",
            reasoning_summary=(
                f"Model analysis unavailable ({reason[:200]}); "
                "defaulted to deterministic analysis."
            ),
            task_id=task_id,
            execution_id=execution_id,
            provider_name="deterministic_fallback",
            model_name="fallback",
        )

    @staticmethod
    def create_fallback_fix(
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        default_file: str = "src/main.py",
        reason: str = "Fallback fix formulation active",
    ) -> FixProposal:
        return FixProposal(
            change_intent="Deterministic fallback fix formulation",
            affected_files=(default_file,),
            proposed_modifications=(
                "Review and correct implementation based on test failure assertions",
            ),
            rationale=(
                f"Model formulation unavailable ({reason[:200]}); "
                "defaulted to deterministic plan."
            ),
            expected_effect="Resolve failing test assertions",
            validation_plan=("run_tests",),
            confidence=0.5,
            diagnosis_reference="fallback_diagnosis",
            task_id=task_id,
            execution_id=execution_id,
            provider_name="deterministic_fallback",
            model_name="fallback",
        )

    def synthesize_patch(
        self,
        fix_proposal: FixProposal,
        task_objective: str = "Autonomous software engineering mission",
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        repository_files: Sequence[tuple[str | Path, str] | str | Path] = (),
        execution_identity: ExecutionIdentity | None = None,
        fallback_on_error: bool = False,
    ) -> PatchProposal:
        """Synthesize concrete code patches from a validated FixProposal."""
        return self._patch_synthesizer.synthesize_patch(
            fix_proposal=fix_proposal,
            task_objective=task_objective,
            task_id=task_id,
            execution_id=execution_id,
            repository_files=repository_files,
            execution_identity=execution_identity,
            fallback_on_error=fallback_on_error,
        )

    @staticmethod
    def create_fallback_patch(
        fix_proposal: FixProposal,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        reason: str = "Deterministic fallback patch",
    ) -> PatchProposal:
        """Create a safe, deterministic fallback patch proposal."""
        return PatchSynthesizer.create_fallback_patch(
            fix_proposal=fix_proposal,
            task_id=task_id,
            execution_id=execution_id,
            reason=reason,
        )


