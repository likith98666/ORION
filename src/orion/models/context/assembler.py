"""Secure Context Assembler for ORION cognitive operations.

Enforces:
- Strict separation between trusted instructions and untrusted repository/execution data
- Deterministic context fencing with explicit provenance tags
- Absolute path stripping / repo-relative normalization
- Resource bounds (per-file, per-command, total files, total untrusted size)
- Truncation markers preserving provenance
- Secret redaction preventing credential leakage
- Advisory prompt injection detection without corrupting legitimate source code
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orion.core.security.redaction import RedactionEngine
from orion.core.swe.evidence import EvidenceItem
from orion.core.tools.repository.security import is_protected_path
from orion.core.workspace.models import ExecutionIdentity
from orion.models.context.detector import InjectionSignal, PromptInjectionDetector
from orion.models.context.models import (
    DEFAULT_SYSTEM_POLICY,
    FencedEvidenceItem,
    SecureModelContext,
    UntrustedExecutionOutput,
    UntrustedFileContent,
)

TRUNCATION_MARKER = "\n[CONTENT TRUNCATED BY ORION CONTEXT BOUNDARY]"


@dataclass(frozen=True)
class ContextLimits:
    """Configurable security boundaries for assembled cognitive context."""

    max_file_chars: int = 20_000
    max_files: int = 20
    max_execution_output_chars: int = 10_000
    max_total_untrusted_chars: int = 60_000
    max_total_prompt_chars: int = 80_000

    def __post_init__(self) -> None:
        if self.max_file_chars <= 0:
            raise ValueError("max_file_chars must be greater than zero.")
        if self.max_files <= 0:
            raise ValueError("max_files must be greater than zero.")
        if self.max_execution_output_chars <= 0:
            raise ValueError("max_execution_output_chars must be greater than zero.")
        if self.max_total_untrusted_chars <= 0:
            raise ValueError("max_total_untrusted_chars must be greater than zero.")
        if self.max_total_prompt_chars <= 0:
            raise ValueError("max_total_prompt_chars must be greater than zero.")


def relativize_path(path: str | Path, workspace_root: Path | str | None = None) -> str:
    """Normalize any path to a repository-relative string, stripping absolute host roots."""
    path_str = str(path).strip().replace("\\", "/")
    if "\0" in path_str:
        raise ValueError("Path contains null byte.")

    if not path_str:
        raise ValueError("Path cannot be empty.")

    if workspace_root is not None:
        root_path = Path(workspace_root).resolve()
        try:
            target_path = Path(path).resolve()
            if target_path.is_relative_to(root_path):
                rel = target_path.relative_to(root_path)
                return str(rel).replace("\\", "/")
        except (ValueError, OSError):
            pass

    # Strip Windows drive letters (e.g. C:, D:)
    if len(path_str) >= 2 and path_str[1] == ":":
        path_str = path_str[2:]

    # Strip leading slashes
    path_str = path_str.lstrip("/")

    # Normalize redundant parts
    parts = [p for p in path_str.split("/") if p and p != "."]
    cleaned = "/".join(parts)
    return cleaned or "."


class ContextAssembler:
    """Assembles untrusted repository artifacts and execution outputs into SecureModelContext."""

    def __init__(
        self,
        limits: ContextLimits | None = None,
        redaction_engine: RedactionEngine | None = None,
        detector: PromptInjectionDetector | None = None,
    ) -> None:
        self._limits = limits or ContextLimits()
        self._redactor = redaction_engine or RedactionEngine()
        self._detector = detector or PromptInjectionDetector()

    @property
    def limits(self) -> ContextLimits:
        return self._limits

    def build_context(
        self,
        task_objective: str,
        task_instructions: str = "",
        repository_files: Sequence[tuple[str | Path, str]] | Sequence[dict[str, Any]] = (),
        execution_outputs: Sequence[tuple[str, str]] | Sequence[dict[str, Any]] = (),
        evidence_items: Sequence[EvidenceItem | FencedEvidenceItem] = (),
        system_policy: str = DEFAULT_SYSTEM_POLICY,
        output_format_instructions: str = "",
        workspace_root: Path | str | None = None,
        stage: str = "",
        execution_identity: ExecutionIdentity | None = None,
        secrets: tuple[str, ...] = (),
    ) -> SecureModelContext:
        """Deterministically assemble and fence model context within strict security boundaries."""
        # Register any transient secrets with redactor
        for secret in secrets:
            if secret and secret.strip():
                self._redactor.register(secret.strip())

        advisory_signals: list[InjectionSignal] = []
        untrusted_budget = self._limits.max_total_untrusted_chars
        current_untrusted_len = 0

        # 1. Process Repository Files
        processed_files: list[UntrustedFileContent] = []
        files_count = 0

        for item in repository_files:
            if files_count >= self._limits.max_files:
                break

            if isinstance(item, tuple) and len(item) >= 2:
                raw_path, raw_content = item[0], item[1]
                file_stage = stage
            elif isinstance(item, dict):
                raw_path = item.get("path", "")
                raw_content = item.get("content", "")
                file_stage = item.get("stage", stage)
            else:
                continue

            rel_path = relativize_path(raw_path, workspace_root=workspace_root)

            # Block protected files (.env, private keys, etc.) from leaking into context
            if is_protected_path(rel_path):
                content = "[ACCESS DENIED: PROTECTED CREDENTIAL PATH]"
                orig_len = len(content)
                is_trunc = False
            else:
                # Redact known secrets
                content = self._redactor.redact(raw_content)
                orig_len = len(content)
                is_trunc = False

                # Scan for advisory prompt injection signals
                sig = self._detector.analyze(content)
                if sig.is_flagged:
                    advisory_signals.append(sig)

                # Enforce per-file character bound
                if len(content) > self._limits.max_file_chars:
                    content = content[: self._limits.max_file_chars] + TRUNCATION_MARKER
                    is_trunc = True

            # Enforce total untrusted budget
            if current_untrusted_len + len(content) > untrusted_budget:
                remaining_budget = max(0, untrusted_budget - current_untrusted_len)
                if remaining_budget > 100:
                    content = content[:remaining_budget] + TRUNCATION_MARKER
                    is_trunc = True
                    processed_files.append(
                        UntrustedFileContent(
                            path=rel_path,
                            content=content,
                            stage=file_stage,
                            truncated=is_trunc,
                            original_length=orig_len,
                        )
                    )
                break

            processed_files.append(
                UntrustedFileContent(
                    path=rel_path,
                    content=content,
                    stage=file_stage,
                    truncated=is_trunc,
                    original_length=orig_len,
                )
            )
            current_untrusted_len += len(content)
            files_count += 1

        # 2. Process Execution Outputs (pytest, linters, commands)
        processed_outputs: list[UntrustedExecutionOutput] = []

        for item in execution_outputs:
            if isinstance(item, tuple) and len(item) >= 2:
                tool_name, raw_output = item[0], item[1]
                exit_code = item[2] if len(item) >= 3 and isinstance(item[2], int) else None
                out_stage = stage
            elif isinstance(item, dict):
                tool_name = item.get("tool_name", "")
                raw_output = item.get("output", "")
                exit_code = item.get("exit_code")
                out_stage = item.get("stage", stage)
            else:
                continue

            clean_output = self._redactor.redact(raw_output)
            orig_len = len(clean_output)
            is_trunc = False

            # Scan for advisory injection signals in output
            sig = self._detector.analyze(clean_output)
            if sig.is_flagged:
                advisory_signals.append(sig)

            # Enforce per-output character bound
            if len(clean_output) > self._limits.max_execution_output_chars:
                bound = self._limits.max_execution_output_chars
                clean_output = clean_output[:bound] + TRUNCATION_MARKER
                is_trunc = True

            # Enforce total untrusted budget
            if current_untrusted_len + len(clean_output) > untrusted_budget:
                remaining_budget = max(0, untrusted_budget - current_untrusted_len)
                if remaining_budget > 100:
                    clean_output = clean_output[:remaining_budget] + TRUNCATION_MARKER
                    is_trunc = True
                    processed_outputs.append(
                        UntrustedExecutionOutput(
                            tool_name=tool_name,
                            output=clean_output,
                            exit_code=exit_code,
                            stage=out_stage,
                            truncated=is_trunc,
                            original_length=orig_len,
                        )
                    )
                break

            processed_outputs.append(
                UntrustedExecutionOutput(
                    tool_name=tool_name,
                    output=clean_output,
                    exit_code=exit_code,
                    stage=out_stage,
                    truncated=is_trunc,
                    original_length=orig_len,
                )
            )
            current_untrusted_len += len(clean_output)

        # 3. Process Evidence Items (Preserve EvidenceLevel)
        processed_evidence: list[FencedEvidenceItem] = []
        for ev in evidence_items:
            if isinstance(ev, EvidenceItem):
                fenced = FencedEvidenceItem.from_evidence_item(ev)
            elif isinstance(ev, FencedEvidenceItem):
                fenced = ev
            else:
                continue

            redacted_content = self._redactor.redact(fenced.content)
            if redacted_content != fenced.content:
                fenced = FencedEvidenceItem(
                    evidence_id=fenced.evidence_id,
                    level=fenced.level,
                    category=fenced.category,
                    source=fenced.source,
                    stage=fenced.stage,
                    content=redacted_content,
                    summary=fenced.summary,
                    timestamp=fenced.timestamp,
                    metadata=fenced.metadata,
                )
            processed_evidence.append(fenced)

        return SecureModelContext(
            system_policy=system_policy,
            task_objective=task_objective,
            task_instructions=task_instructions,
            repository_files=tuple(processed_files),
            execution_outputs=tuple(processed_outputs),
            evidence_items=tuple(processed_evidence),
            output_format_instructions=output_format_instructions,
            execution_identity=execution_identity,
            advisory_signals=tuple(advisory_signals),
        )
