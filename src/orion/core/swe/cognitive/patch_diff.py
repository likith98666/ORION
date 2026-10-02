"""Deterministic unified diff generation for proposed patch operations."""

from __future__ import annotations

import difflib
from collections.abc import Sequence

from orion.core.swe.cognitive.patch_contracts import PatchOperation, PatchOperationType


class PatchDiffGenerator:
    """Generates inspectable unified diffs and computes line-change metrics."""

    @staticmethod
    def compute_operation_diff(
        operation_type: PatchOperationType,
        path: str,
        original_content: str | None,
        new_content: str | None,
    ) -> tuple[str, int, int]:
        """Compute unified diff and line change counts for a single operation."""
        norm_path = path.replace("\\", "/")

        if operation_type == PatchOperationType.CREATE_FILE:
            curr_lines: list[str] = []
            new_lines = (new_content or "").splitlines(keepends=True)
            from_file = "/dev/null"
            to_file = f"b/{norm_path}"
        elif operation_type == PatchOperationType.DELETE_FILE:
            curr_lines = (original_content or "").splitlines(keepends=True)
            new_lines = []
            from_file = f"a/{norm_path}"
            to_file = "/dev/null"
        else:  # MODIFY_FILE
            curr_lines = (original_content or "").splitlines(keepends=True)
            new_lines = (new_content or "").splitlines(keepends=True)
            from_file = f"a/{norm_path}"
            to_file = f"b/{norm_path}"

        diff_lines = list(
            difflib.unified_diff(
                curr_lines,
                new_lines,
                fromfile=from_file,
                tofile=to_file,
            )
        )

        lines_added = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        lines_removed = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )

        diff_text = "".join(diff_lines)
        return diff_text, lines_added, lines_removed

    @staticmethod
    def aggregate_proposal_diff(
        operations: Sequence[PatchOperation],
    ) -> tuple[str, int, int]:
        """Combine diffs from all operations and return total lines added and removed."""
        diff_chunks: list[str] = []
        total_added = 0
        total_removed = 0

        for op in operations:
            if op.diff:
                diff_chunks.append(op.diff)
            total_added += op.lines_added
            total_removed += op.lines_removed

        combined_diff = "\n".join(chunk.strip() for chunk in diff_chunks if chunk.strip())
        return combined_diff, total_added, total_removed
