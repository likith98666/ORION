"""13-class failure taxonomy and deterministic failure classifier for V5."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class FailureCategory(str, Enum):
    """The 13 formal failure categories in ORION V5 Advanced Self-Healing."""

    SYNTAX_FAILURE = "syntax_failure"
    ASSERTION_FAILURE = "assertion_failure"
    TYPE_FAILURE = "type_failure"
    IMPORT_FAILURE = "import_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    ENVIRONMENT_FAILURE = "environment_failure"
    TIMEOUT = "timeout"
    RESOURCE_FAILURE = "resource_failure"
    PATCH_CONFLICT = "patch_conflict"
    STALE_STATE = "stale_state"
    SECURITY_FAILURE = "security_failure"
    TEST_REGRESSION = "test_regression"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureDiagnosis:
    """Structured diagnosis of an encountered error or test failure."""

    failure_id: UUID
    category: FailureCategory
    error_message: str
    target_file: str | None = None
    line_number: int | None = None
    traceback_snippet: str | None = None
    raw_details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert failure diagnosis to dictionary."""
        return {
            "failure_id": str(self.failure_id),
            "category": self.category.value,
            "error_message": self.error_message,
            "target_file": self.target_file,
            "line_number": self.line_number,
            "traceback_snippet": self.traceback_snippet,
            "raw_details": dict(self.raw_details),
        }


class FailureClassifier:
    """Classifies raw execution errors, pytest outputs, and tracebacks into formal categories."""

    @staticmethod
    def classify(
        output_text: str,
        target_file: str | None = None,
        exit_code: int | None = None,
    ) -> FailureDiagnosis:
        """Analyze stdout/stderr or exception message and extract failure category."""
        fid = uuid4()
        text = output_text or ""
        text_lower = text.lower()

        category = FailureCategory.UNKNOWN
        line_num: int | None = None
        extracted_file = target_file

        # 1. Syntax Error
        if "syntaxerror:" in text_lower or "indentationerror:" in text_lower:
            category = FailureCategory.SYNTAX_FAILURE
            match = re.search(r'File "([^"]+)", line (\d+)', text)
            if match:
                extracted_file = extracted_file or match.group(1)
                line_num = int(match.group(2))

        # 2. Type Error
        elif (
            "typeerror:" in text_lower or "mypy" in text_lower or "incompatible type" in text_lower
        ):
            category = FailureCategory.TYPE_FAILURE

        # 3. Import Error
        elif "importerror:" in text_lower or "modulenotfounderror:" in text_lower:
            category = FailureCategory.IMPORT_FAILURE

        # 4. Assertion / Test Failure
        elif "assertionerror" in text_lower or "assert " in text_lower or "failed (" in text_lower:
            category = FailureCategory.ASSERTION_FAILURE

        # 5. Timeout
        elif "timeout" in text_lower or "timed out" in text_lower:
            category = FailureCategory.TIMEOUT

        # 6. Patch Conflict
        elif (
            "patch conflict" in text_lower
            or "hunk failed" in text_lower
            or "merge conflict" in text_lower
        ):
            category = FailureCategory.PATCH_CONFLICT

        # 7. Security Failure
        elif (
            "permissiondenied" in text_lower
            or "security" in text_lower
            or "forbidden" in text_lower
        ):
            category = FailureCategory.SECURITY_FAILURE

        # 8. Dependency Failure
        elif "no matching distribution" in text_lower or "versionconflict" in text_lower:
            category = FailureCategory.DEPENDENCY_FAILURE

        # 9. Resource Failure
        elif (
            "memoryerror" in text_lower
            or "out of memory" in text_lower
            or "disk full" in text_lower
        ):
            category = FailureCategory.RESOURCE_FAILURE

        # 10. Test Regression
        elif "regression" in text_lower:
            category = FailureCategory.TEST_REGRESSION

        # Extract first line of error or traceback summary
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        err_msg = lines[-1] if lines else "Unknown failure encountered."
        traceback_snippet = "\n".join(lines[-15:]) if len(lines) > 1 else err_msg

        return FailureDiagnosis(
            failure_id=fid,
            category=category,
            error_message=err_msg,
            target_file=extracted_file,
            line_number=line_num,
            traceback_snippet=traceback_snippet,
            raw_details={"exit_code": exit_code} if exit_code is not None else {},
        )
