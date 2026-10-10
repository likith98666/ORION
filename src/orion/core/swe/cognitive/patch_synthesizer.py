"""PatchSynthesizer: Connects FixProposal to bounded model patch generation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from orion.config.model_config import ModelConfig
from orion.core.swe.cognitive.contracts import FixProposal
from orion.core.swe.cognitive.errors import (
    CognitiveModelUnavailableError,
    InvalidPatchError,
    PatchSynthesisError,
)
from orion.core.swe.cognitive.patch_contracts import PatchProposal
from orion.core.swe.cognitive.patch_validator import PatchValidator
from orion.core.workspace.models import ExecutionIdentity, Workspace
from orion.models.errors import sanitize_error_message
from orion.models.runtime.runtime import ModelRuntime

if TYPE_CHECKING:
    from orion.models.context.assembler import ContextAssembler

PATCH_FORMAT_INSTRUCTIONS = """Respond strictly with a valid JSON object matching this schema:
{
  "affected_files": ["workspace/relative/path.py"],
  "operations": [
    {
      "operation_type": "create_file | modify_file | delete_file",
      "path": "workspace/relative/path.py",
      "new_content": "complete updated file content",
      "expected_hash": "sha256_hash_if_known (or omit)"
    }
  ],
  "rationale": "detailed technical explanation of exact code modifications",
  "validation_steps": ["test command or verification check"],
  "confidence": 0.90
}
Do not include any conversational filler. Only output valid JSON."""


class PatchSynthesizer:
    """Synthesizes bounded code patch proposals from validated FixProposals."""

    def __init__(
        self,
        model_runtime: ModelRuntime,
        model_config: ModelConfig,
        workspace: Workspace,
        context_assembler: ContextAssembler | None = None,
        validator: PatchValidator | None = None,
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
        self._validator = validator or PatchValidator()

    @property
    def model_runtime(self) -> ModelRuntime:
        return self._runtime

    @property
    def model_config(self) -> ModelConfig:
        return self._config

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    @property
    def validator(self) -> PatchValidator:
        return self._validator

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
        """Synthesize a reviewable PatchProposal from a FixProposal using bounded context."""
        if not isinstance(fix_proposal, FixProposal):
            raise TypeError("fix_proposal must be a FixProposal instance.")

        # Determine target files to include in prompt context
        files_to_load: list[str] = list(fix_proposal.affected_files)
        normalized_files: list[tuple[str | Path, str]] = []

        # Include explicit repository files if provided
        for item in repository_files:
            if isinstance(item, tuple) and len(item) >= 2:
                normalized_files.append((item[0], item[1]))
            elif isinstance(item, (str, Path)):
                try:
                    resolved = self._workspace.resolve_path(str(item))
                    if resolved.is_file():
                        content = resolved.read_text(encoding="utf-8", errors="replace")
                        normalized_files.append((str(item), content))
                except Exception:
                    continue

        # Load any affected files not yet included
        already_loaded = {str(item[0]).replace("\\", "/") for item in normalized_files}
        for f in files_to_load:
            norm_f = f.replace("\\", "/")
            if norm_f not in already_loaded:
                try:
                    resolved = self._workspace.resolve_path(norm_f)
                    if resolved.is_file():
                        content = resolved.read_text(encoding="utf-8", errors="replace")
                        normalized_files.append((norm_f, content))
                except Exception:
                    continue

        patch_instructions = (
            f"FIX FORMULATION OBJECTIVE:\n"
            f"Change intent: {fix_proposal.change_intent}\n\n"
            f"PROPOSED MODIFICATIONS:\n"
            + "\n".join(f"- {m}" for m in fix_proposal.proposed_modifications)
            + "\n\n"
            f"TECHNICAL RATIONALE:\n{fix_proposal.rationale}\n\n"
            f"EXPECTED EFFECT:\n{fix_proposal.expected_effect}\n\n"
            f"AFFECTED FILES:\n"
            + "\n".join(f"- {f}" for f in fix_proposal.affected_files)
            + "\n\n"
            f"TASK OBJECTIVE:\n{task_objective}"
        )

        secure_ctx = self._assembler.build_context(
            task_objective=task_objective,
            task_instructions=patch_instructions,
            repository_files=normalized_files,
            output_format_instructions=PATCH_FORMAT_INSTRUCTIONS,
            workspace_root=self._workspace.repository_root,
            stage="patch_synthesis",
            execution_identity=execution_identity,
        )

        model_req = secure_ctx.to_model_request(
            structured_output=True,
            response_format={"type": "json_object"},
            request_id=str(execution_id) if execution_id else None,
        )

        try:
            response = self._runtime.generate(self._config, model_req)
        except Exception as exc:
            sanitized = sanitize_error_message(str(exc))
            if fallback_on_error:
                return self.create_fallback_patch(
                    fix_proposal=fix_proposal,
                    task_id=task_id,
                    execution_id=execution_id,
                    reason=f"Model generation error: {sanitized}",
                )
            raise CognitiveModelUnavailableError(
                f"Model provider failed during patch synthesis: {sanitized}"
            ) from exc

        try:
            return self._validator.validate_patch(
                raw=response.text,
                workspace=self._workspace,
                task_id=task_id,
                execution_id=execution_id,
                provider_name=self._config.provider_name,
                model_name=self._config.model_name,
            )
        except (InvalidPatchError, PatchSynthesisError) as exc:
            if fallback_on_error:
                return self.create_fallback_patch(
                    fix_proposal=fix_proposal,
                    task_id=task_id,
                    execution_id=execution_id,
                    reason=f"Proposal validation failure: {exc}",
                )
            raise

    @staticmethod
    def create_fallback_patch(
        fix_proposal: FixProposal,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        reason: str = "Deterministic fallback patch",
    ) -> PatchProposal:
        """Create a safe, unapplied fallback patch proposal indicating manual review is needed."""
        return PatchProposal(
            affected_files=fix_proposal.affected_files,
            operations=(),
            rationale=f"Deterministic fallback proposal: {reason}. Manual patch review required.",
            validation_steps=("Manual verification required",),
            confidence=0.0,
            task_id=task_id,
            execution_id=execution_id,
            total_lines_added=0,
            total_lines_removed=0,
            unified_diff="",
            provider_name="deterministic_fallback",
            model_name="fallback",
            metadata={"fallback": True, "reason": reason},
        )
