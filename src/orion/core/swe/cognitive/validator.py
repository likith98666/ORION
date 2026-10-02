"""Strict schema, path, and security validator for model-generated SWE proposals."""

from __future__ import annotations

import json
import re
from typing import Any

from orion.core.swe.cognitive.contracts import FailureAnalysisProposal, FixProposal
from orion.core.swe.cognitive.errors import InvalidProposalError, UnsafeProposalPathError
from orion.core.tools.repository.security import is_protected_path
from orion.core.workspace.errors import PathOutsideWorkspaceError, PathSecurityError
from orion.core.workspace.models import Workspace

MAX_STRING_LENGTH = 5000
MAX_LIST_LENGTH = 30

DANGEROUS_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-[rf]{1,2}\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fqs]\b", re.IGNORECASE),
    re.compile(r"\b(curl|wget)\b[^\n|]*\|\s*(sh|bash|powershell|cmd)", re.IGNORECASE),
    re.compile(r"\bpowershell\b[^\n]*-e(nc(odedcommand)?)?", re.IGNORECASE),
    re.compile(r"\b(shutdown|reboot)\b", re.IGNORECASE),
)


class ProposalValidator:
    """Validates structured model proposals against strict schemas and workspace security."""

    def parse_json_payload(self, text: str) -> dict[str, Any]:
        """Safely parse model output text into a JSON dictionary."""
        if len(text) > 65_536:
            raise InvalidProposalError(
                f"Model response length ({len(text)}) exceeds maximum "
                "allowed length of 65536 characters."
            )

        cleaned = text.strip()
        # Handle markdown-wrapped JSON code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
        except Exception as exc:
            raise InvalidProposalError(f"Model output is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise InvalidProposalError(f"Expected JSON object, got {type(parsed).__name__}.")

        return parsed

    def validate_failure_analysis(
        self,
        raw: dict[str, Any] | str,
        workspace: Workspace,
    ) -> FailureAnalysisProposal:
        """Validate model output for failure analysis and construct FailureAnalysisProposal."""
        data = self.parse_json_payload(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            raise InvalidProposalError("Failure analysis must be a dictionary.")

        # Required fields
        failure_class = self._validate_str(
            data.get("failure_class") or data.get("failure_classification"),
            "failure_class",
            required=True,
            max_len=200,
        )
        root_cause = self._validate_str(
            data.get("root_cause_hypothesis") or data.get("root_cause"),
            "root_cause_hypothesis",
            required=True,
            max_len=MAX_STRING_LENGTH,
        )

        observations = self._validate_str_list(
            data.get("observations") or data.get("supporting_observations", ()),
            "observations",
        )

        raw_files = data.get("affected_files") or data.get("relevant_files", ())
        validated_files = self._validate_and_sanitize_paths(raw_files, workspace)

        confidence = self._validate_confidence(data.get("confidence", 0.0))
        proposed_action = self._validate_str(
            data.get("proposed_action") or data.get("proposed_next_action", ""),
            "proposed_action",
            required=False,
            max_len=1000,
        )
        reasoning = self._validate_str(
            data.get("reasoning_summary") or data.get("reasoning", ""),
            "reasoning_summary",
            required=False,
            max_len=MAX_STRING_LENGTH,
        )

        self._check_for_dangerous_commands(root_cause, proposed_action, reasoning)

        return FailureAnalysisProposal(
            failure_classification=failure_class,
            root_cause_hypothesis=root_cause,
            supporting_observations=observations,
            relevant_files=validated_files,
            confidence=confidence,
            proposed_next_action=proposed_action,
            reasoning_summary=reasoning,
        )

    def validate_fix_proposal(
        self,
        raw: dict[str, Any] | str,
        workspace: Workspace,
    ) -> FixProposal:
        """Validate model output for fix formulation and construct FixProposal."""
        data = self.parse_json_payload(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            raise InvalidProposalError("Fix proposal must be a dictionary.")

        change_intent = self._validate_str(
            data.get("change_intent") or data.get("intended_modification"),
            "change_intent",
            required=True,
            max_len=1000,
        )

        raw_files = data.get("affected_files") or data.get("target_files", ())
        validated_files = self._validate_and_sanitize_paths(raw_files, workspace)
        if not validated_files:
            raise InvalidProposalError(
                "Fix proposal must specify at least one valid affected file."
            )

        modifications = self._validate_str_list(
            data.get("modifications") or data.get("proposed_modifications", ()),
            "modifications",
        )
        rationale = self._validate_str(
            data.get("rationale", ""),
            "rationale",
            required=False,
            max_len=MAX_STRING_LENGTH,
        )
        expected_effect = self._validate_str(
            data.get("expected_effect") or data.get("expected_behavior", ""),
            "expected_effect",
            required=False,
            max_len=1000,
        )
        validation_plan = self._validate_str_list(
            data.get("validation_plan") or data.get("validation_strategy", ()),
            "validation_plan",
        )
        confidence = self._validate_confidence(data.get("confidence", 0.0))

        self._check_for_dangerous_commands(change_intent, rationale, *modifications)

        return FixProposal(
            change_intent=change_intent,
            affected_files=validated_files,
            proposed_modifications=modifications,
            rationale=rationale,
            expected_effect=expected_effect,
            validation_plan=validation_plan,
            confidence=confidence,
        )

    def _validate_str(
        self,
        val: Any,
        field_name: str,
        required: bool = True,
        max_len: int = MAX_STRING_LENGTH,
    ) -> str:
        if val is None or not isinstance(val, str):
            if required:
                raise InvalidProposalError(f"Field '{field_name}' must be a non-empty string.")
            return ""

        stripped = val.strip()
        if required and not stripped:
            raise InvalidProposalError(f"Field '{field_name}' must be a non-empty string.")

        if len(stripped) > max_len:
            raise InvalidProposalError(
                f"Field '{field_name}' length ({len(stripped)}) exceeds maximum limit of {max_len}."
            )
        return str(stripped)

    def _validate_str_list(self, val: Any, field_name: str) -> tuple[str, ...]:
        if val is None:
            return ()
        if not isinstance(val, (list, tuple)):
            raise InvalidProposalError(f"Field '{field_name}' must be a list of strings.")

        if len(val) > MAX_LIST_LENGTH:
            raise InvalidProposalError(
                f"List '{field_name}' contains {len(val)} items, "
                f"exceeding limit of {MAX_LIST_LENGTH}."
            )

        cleaned: list[str] = []
        for idx, item in enumerate(val):
            if not isinstance(item, str):
                raise InvalidProposalError(
                    f"Item {idx} in '{field_name}' must be a string, got {type(item).__name__}."
                )
            s = item.strip()
            if s:
                cleaned.append(s[:MAX_STRING_LENGTH])
        return tuple(cleaned)

    def _validate_confidence(self, val: Any) -> float:
        try:
            conf = float(val)
        except (ValueError, TypeError) as exc:
            raise InvalidProposalError(f"Confidence must be a numeric value: {exc}") from exc

        if not 0.0 <= conf <= 1.0:
            raise InvalidProposalError(f"Confidence must be between 0.0 and 1.0, got {conf}.")
        return round(conf, 4)

    def _validate_and_sanitize_paths(
        self,
        raw_paths: Any,
        workspace: Workspace,
    ) -> tuple[str, ...]:
        """Validate paths strictly: must be workspace-relative, unescaped, and unprotected."""
        if not raw_paths:
            return ()
        if isinstance(raw_paths, str):
            raw_paths = [raw_paths]
        if not isinstance(raw_paths, (list, tuple)):
            raise InvalidProposalError("Paths must be a sequence of strings.")

        validated: list[str] = []
        for raw in raw_paths:
            if not isinstance(raw, str) or not raw.strip():
                continue
            path_str = raw.strip().replace("\\", "/")

            if "\0" in path_str:
                raise UnsafeProposalPathError(f"Path '{path_str}' contains forbidden null bytes.")

            # Reject Windows drive letters (e.g. C:, D:)
            if len(path_str) >= 2 and path_str[1] == ":":
                raise UnsafeProposalPathError(
                    f"Absolute drive path '{path_str}' is forbidden in model proposals."
                )

            # Reject leading slashes
            if path_str.startswith("/"):
                raise UnsafeProposalPathError(
                    f"Absolute root path '{path_str}' is forbidden in model proposals."
                )

            # Reject traversal
            parts = path_str.split("/")
            if ".." in parts:
                raise UnsafeProposalPathError(
                    f"Path traversal sequence '..' in '{path_str}' is strictly rejected."
                )

            # Reject protected files (.env, private keys, .git)
            if is_protected_path(path_str):
                raise UnsafeProposalPathError(
                    f"Access to protected credential path '{path_str}' is forbidden."
                )

            # Enforce workspace containment
            try:
                workspace.resolve_path(path_str)
            except (PathOutsideWorkspaceError, PathSecurityError) as exc:
                raise UnsafeProposalPathError(
                    f"Proposed path '{path_str}' escapes workspace boundary: {exc}"
                ) from exc

            validated.append(path_str)

        return tuple(validated)

    def _check_for_dangerous_commands(self, *texts: str) -> None:
        """Scan proposal text fields for dangerous destructive shell execution patterns."""
        for text in texts:
            if not text:
                continue
            for pattern in DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(text):
                    raise InvalidProposalError(
                        f"Model proposal contains prohibited destructive command pattern: "
                        f"{pattern.pattern}"
                    )
