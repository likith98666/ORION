"""Deterministic syntax validation for proposed patch modifications."""

from __future__ import annotations

import ast
from pathlib import Path

from orion.core.swe.cognitive.patch_contracts import PatchOperation, SyntaxValidationResult


class PatchSyntaxValidator:
    """Validates the syntax of proposed code changes before approval or application."""

    PYTHON_EXTENSIONS: frozenset[str] = frozenset({".py", ".pyw"})

    def validate_syntax(self, path: str, content: str) -> SyntaxValidationResult:
        """Validate source code syntax according to file extension."""
        suffix = Path(path).suffix.lower()

        if suffix in self.PYTHON_EXTENSIONS:
            return self._validate_python(path, content)

        # Explicit validation-unavailable state for unsupported languages
        return SyntaxValidationResult(
            path=path,
            language="unsupported",
            valid=True,
            supported=False,
            error_message=f"Syntax validation unavailable for file type '{suffix}'",
        )

    def validate_operation(self, op: PatchOperation) -> SyntaxValidationResult | None:
        """Validate syntax for a single patch operation if applicable."""
        if op.new_content is None:
            return None
        return self.validate_syntax(op.path, op.new_content)

    def _validate_python(self, path: str, content: str) -> SyntaxValidationResult:
        """Parse Python source using the standard ast library."""
        try:
            ast.parse(content, filename=path)
            return SyntaxValidationResult(
                path=path,
                language="python",
                valid=True,
                supported=True,
            )
        except SyntaxError as exc:
            msg = exc.msg or "Syntax error"
            return SyntaxValidationResult(
                path=path,
                language="python",
                valid=False,
                supported=True,
                error_message=f"{msg} at line {exc.lineno}, column {exc.offset}",
                line_number=exc.lineno,
                column_number=exc.offset,
            )
        except Exception as exc:
            return SyntaxValidationResult(
                path=path,
                language="python",
                valid=False,
                supported=True,
                error_message=f"AST parsing exception: {exc}",
            )
