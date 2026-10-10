"""Deterministic validator for model-proposed patches."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from orion.core.swe.cognitive.errors import (
    InvalidPatchError,
    PatchSyntaxError,
    PatchTooLargeError,
    StalePatchError,
    UnsafePatchPathError,
    UnsupportedPatchOperationError,
)
from orion.core.swe.cognitive.patch_config import PatchConfig
from orion.core.swe.cognitive.patch_contracts import (
    PatchOperation,
    PatchOperationType,
    PatchProposal,
    SyntaxValidationResult,
)
from orion.core.swe.cognitive.patch_diff import PatchDiffGenerator
from orion.core.swe.cognitive.patch_syntax import PatchSyntaxValidator
from orion.core.tools.repository.security import is_protected_path
from orion.core.workspace.errors import PathOutsideWorkspaceError, PathSecurityError
from orion.core.workspace.models import Workspace

DANGEROUS_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-[rf]{1,2}\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fsq]\b", re.IGNORECASE),
    re.compile(r"\b(?:curl|wget)\b[^\n|;&]+?\|\s*(?:sh|bash|python|powershell)\b", re.IGNORECASE),
    re.compile(r"\bpowershell\b[^\n|;&]+?-(?:e|enc|encodedcommand)\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
)


class PatchValidator:
    """Validates patch proposals against strict schemas, boundaries, syntax, and hashes."""

    def __init__(
        self,
        config: PatchConfig | None = None,
        syntax_validator: PatchSyntaxValidator | None = None,
        diff_generator: PatchDiffGenerator | None = None,
    ) -> None:
        self._config = config or PatchConfig()
        self._syntax_validator = syntax_validator or PatchSyntaxValidator()
        self._diff_generator = diff_generator or PatchDiffGenerator()

    @property
    def config(self) -> PatchConfig:
        return self._config

    def parse_json_payload(self, text: str) -> dict[str, Any]:
        """Safely parse model output text into a JSON dictionary with bounded length check."""
        if len(text) > self._config.max_payload_size:
            raise InvalidPatchError(
                f"Model response length ({len(text)}) exceeds maximum "
                f"allowed length of {self._config.max_payload_size} characters."
            )

        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise InvalidPatchError(
                f"Model response is not valid JSON: {exc.msg} at line {exc.lineno}"
            ) from exc

        if not isinstance(parsed, dict):
            raise InvalidPatchError(f"Expected JSON object, got {type(parsed).__name__}.")

        return parsed

    def validate_patch(
        self,
        raw: dict[str, Any] | str,
        workspace: Workspace,
        task_id: UUID | None = None,
        execution_id: UUID | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> PatchProposal:
        """Validate model output for a patch proposal and return a verified PatchProposal."""
        data = self.parse_json_payload(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            raise InvalidPatchError("Patch proposal must be a dictionary.")

        # 1. Validate rationale
        rationale = data.get("rationale")
        if rationale is None or not isinstance(rationale, str) or not rationale.strip():
            raise InvalidPatchError("Field 'rationale' must be a non-empty string.")
        rationale = rationale.strip()

        # 2. Validate confidence
        conf_val = data.get("confidence", 0.0)
        try:
            confidence = float(conf_val)
        except (ValueError, TypeError) as exc:
            raise InvalidPatchError(f"Confidence must be numeric: {exc}") from exc
        if not 0.0 <= confidence <= 1.0:
            raise InvalidPatchError(f"Confidence must be between 0.0 and 1.0, got {confidence}.")
        confidence = round(confidence, 4)

        # 3. Validate validation_steps
        raw_steps = data.get("validation_steps", ())
        if not isinstance(raw_steps, (list, tuple)):
            raise InvalidPatchError("Field 'validation_steps' must be a list of strings.")
        validation_steps: list[str] = []
        for s in raw_steps:
            if not isinstance(s, str):
                raise InvalidPatchError("Each item in 'validation_steps' must be a string.")
            if s.strip():
                validation_steps.append(s.strip())

        # Check for dangerous command injections in rationale or validation steps
        self._check_for_dangerous_commands(rationale, *validation_steps)

        # 4. Validate affected_files
        raw_affected = data.get("affected_files")
        if not raw_affected or not isinstance(raw_affected, (list, tuple)):
            raise InvalidPatchError("Field 'affected_files' must be a non-empty list of strings.")
        if len(raw_affected) > self._config.max_affected_files:
            raise PatchTooLargeError(
                f"Affected file count ({len(raw_affected)}) exceeds limit of "
                f"{self._config.max_affected_files}."
            )

        validated_affected: list[str] = []
        for f in raw_affected:
            if not isinstance(f, str) or not f.strip():
                raise InvalidPatchError("Items in 'affected_files' must be non-empty strings.")
            sanitized_path = self._validate_and_sanitize_path(f.strip(), workspace)
            validated_affected.append(sanitized_path)

        # 5. Validate operations
        raw_ops = data.get("operations")
        if not raw_ops or not isinstance(raw_ops, (list, tuple)):
            raise InvalidPatchError("Field 'operations' must be a non-empty list.")

        validated_ops: list[PatchOperation] = []
        syntax_results: list[SyntaxValidationResult] = []

        for idx, op_data in enumerate(raw_ops):
            if not isinstance(op_data, dict):
                raise InvalidPatchError(f"Operation at index {idx} must be a dictionary.")

            op = self._validate_operation(
                op_data,
                workspace,
                syntax_results,
            )
            validated_ops.append(op)

        # 6. Aggregate diff and check changed line boundaries
        combined_diff, total_added, total_removed = self._diff_generator.aggregate_proposal_diff(
            validated_ops
        )
        total_changed = total_added + total_removed
        if total_changed > self._config.max_changed_lines:
            raise PatchTooLargeError(
                f"Total changed lines ({total_changed}) exceeds limit of "
                f"{self._config.max_changed_lines} lines."
            )

        return PatchProposal(
            affected_files=tuple(validated_affected),
            operations=tuple(validated_ops),
            rationale=rationale,
            validation_steps=tuple(validation_steps),
            confidence=confidence,
            task_id=task_id,
            execution_id=execution_id,
            syntax_results=tuple(syntax_results),
            total_lines_added=total_added,
            total_lines_removed=total_removed,
            unified_diff=combined_diff,
            provider_name=provider_name,
            model_name=model_name,
            raw_response=raw if isinstance(raw, str) else None,
        )

    def _validate_operation(
        self,
        op_data: dict[str, Any],
        workspace: Workspace,
        syntax_results: list[SyntaxValidationResult],
    ) -> PatchOperation:
        """Validate an individual operation, check hashes, compute diff, and validate syntax."""
        raw_op_type = op_data.get("operation_type")
        if not raw_op_type or not isinstance(raw_op_type, str):
            raise InvalidPatchError("Operation missing required field 'operation_type'.")

        try:
            op_type = PatchOperationType(raw_op_type.lower())
        except ValueError as exc:
            raise UnsupportedPatchOperationError(
                f"Unsupported patch operation '{raw_op_type}'. "
                f"Supported operations: {[e.value for e in PatchOperationType]}."
            ) from exc

        raw_path = op_data.get("path")
        if not raw_path or not isinstance(raw_path, str) or not raw_path.strip():
            raise InvalidPatchError("Operation missing required non-empty field 'path'.")

        sanitized_path = self._validate_and_sanitize_path(raw_path.strip(), workspace)
        target_file = workspace.resolve_path(sanitized_path)

        new_content = op_data.get("new_content")
        expected_hash = op_data.get("expected_hash")
        if expected_hash is not None and isinstance(expected_hash, str):
            expected_hash = expected_hash.strip().lower()

        # Check content limits and dangerous commands in new content
        if new_content is not None:
            if not isinstance(new_content, str):
                raise InvalidPatchError(
                    f"Operation 'new_content' for '{sanitized_path}' must be a string."
                )
            encoded = new_content.encode("utf-8")
            if len(encoded) > self._config.max_file_size:
                raise PatchTooLargeError(
                    f"File '{sanitized_path}' modification size ({len(encoded)} bytes) "
                    f"exceeds limit of {self._config.max_file_size} bytes."
                )
            self._check_for_dangerous_commands(new_content)

        original_content: str | None = None
        current_hash: str | None = None

        if target_file.exists():
            if target_file.is_dir():
                raise InvalidPatchError(
                    f"Target path '{sanitized_path}' is an existing directory, not a file."
                )
            file_bytes = target_file.read_bytes()
            original_content = target_file.read_text(encoding="utf-8", errors="replace")
            current_hash = hashlib.sha256(file_bytes).hexdigest()

        # Operation-specific checks
        if op_type == PatchOperationType.CREATE_FILE:
            if target_file.exists():
                raise InvalidPatchError(
                    f"Cannot create file '{sanitized_path}': file already exists."
                )
            if new_content is None:
                raise InvalidPatchError(
                    f"Operation CREATE_FILE for '{sanitized_path}' requires 'new_content'."
                )
        elif op_type in (PatchOperationType.MODIFY_FILE, PatchOperationType.DELETE_FILE):
            if not target_file.exists():
                raise InvalidPatchError(
                    f"Cannot {op_type.value} non-existent file '{sanitized_path}'."
                )
            if op_type == PatchOperationType.MODIFY_FILE and new_content is None:
                raise InvalidPatchError(
                    f"Operation MODIFY_FILE for '{sanitized_path}' requires 'new_content'."
                )

            # Optimistic concurrency / hash locking check
            if expected_hash is not None and expected_hash:
                text_hash = (
                    hashlib.sha256((original_content or "").encode("utf-8")).hexdigest().lower()
                )
                if expected_hash not in (current_hash, text_hash):
                    raise StalePatchError(
                        f"Expected hash '{expected_hash}' does not match actual current hash "
                        f"'{current_hash}'. File '{sanitized_path}' has been modified concurrently."
                    )
            elif current_hash is not None:
                # Capture current hash if not supplied
                expected_hash = current_hash

        # Compute deterministic diff
        diff_text, added, removed = self._diff_generator.compute_operation_diff(
            operation_type=op_type,
            path=sanitized_path,
            original_content=original_content,
            new_content=new_content,
        )

        op = PatchOperation(
            operation_type=op_type,
            path=sanitized_path,
            new_content=new_content,
            expected_hash=expected_hash,
            expected_content=original_content,
            diff=diff_text,
            lines_added=added,
            lines_removed=removed,
        )

        # Run syntax validation if new content is present
        if new_content is not None:
            syn_result = self._syntax_validator.validate_operation(op)
            if syn_result is not None:
                syntax_results.append(syn_result)
                if not syn_result.valid:
                    raise PatchSyntaxError(
                        f"Syntax validation failed for '{sanitized_path}': "
                        f"{syn_result.error_message}"
                    )

        return op

    def _validate_and_sanitize_path(self, raw_path: str, workspace: Workspace) -> str:
        """Enforce strict workspace containment; reject traversal, absolute, UNC, and protected."""
        path_str = raw_path.strip().replace("\\", "/")

        if "\0" in path_str:
            raise UnsafePatchPathError(f"Path '{path_str}' contains forbidden null bytes.")

        # Reject Windows drive letters (e.g. C:, D:)
        if len(path_str) >= 2 and path_str[1] == ":":
            raise UnsafePatchPathError(
                f"Absolute drive path '{path_str}' is forbidden in patch proposals."
            )

        # Reject UNC paths (\\server\share or //server/share)
        if raw_path.strip().startswith(("\\\\", "//")):
            raise UnsafePatchPathError(f"UNC path '{raw_path}' is forbidden in patch proposals.")

        # Reject leading slashes (root paths)
        if path_str.startswith("/"):
            raise UnsafePatchPathError(
                f"Absolute root path '{path_str}' is forbidden in patch proposals."
            )

        # Reject traversal
        parts = path_str.split("/")
        if ".." in parts:
            raise UnsafePatchPathError(
                f"Path traversal sequence '..' in '{path_str}' is strictly rejected."
            )

        # Reject protected credential files (.env, private keys, .git)
        if is_protected_path(path_str):
            raise UnsafePatchPathError(
                f"Access to protected credential path '{path_str}' is forbidden."
            )

        # Enforce workspace boundary
        try:
            workspace.resolve_path(path_str)
        except (PathOutsideWorkspaceError, PathSecurityError) as exc:
            raise UnsafePatchPathError(
                f"Proposed patch path '{path_str}' escapes workspace boundary: {exc}"
            ) from exc

        return path_str

    def _check_for_dangerous_commands(self, *texts: str) -> None:
        """Scan patch text fields for destructive shell execution patterns."""
        for text in texts:
            if not text:
                continue
            for pattern in DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(text):
                    raise InvalidPatchError(
                        f"Patch contains prohibited destructive command pattern: {pattern.pattern}"
                    )
