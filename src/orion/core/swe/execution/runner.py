"""Controlled test execution authority enforcing strict allowlists and sandbox boundaries."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from orion.core.observability.context import TelemetryContext
from orion.core.swe.evidence import EvidenceCategory, EvidenceLedger
from orion.core.swe.execution.contracts import ControlledTestResult
from orion.core.swe.execution.errors import ControlledExecutionError
from orion.core.swe.stages import SWETaskStage
from orion.core.workspace.errors import PathOutsideWorkspaceError, PathSecurityError
from orion.core.workspace.models import Workspace

DEFAULT_TEST_TIMEOUT: int = 60
MAX_TEST_TIMEOUT: int = 300
MAX_OUTPUT_CHARS: int = 65536


def _get_sanitized_environment() -> dict[str, str]:
    """Provide a minimal, sanitized environment for subprocess execution."""
    safe_keys = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TMP",
        "TEMP",
        "HOME",
        "USERPROFILE",
        "LANG",
        "LC_ALL",
        "PYTHONPATH",
        "PYTHONIOENCODING",
        "VIRTUAL_ENV",
    }
    return {k: v for k, v in os.environ.items() if k.upper() in safe_keys}


class ControlledExecutionAuthority:
    """Authoritative service executing policy-controlled, allowlisted tests."""

    def __init__(
        self,
        workspace: Workspace,
        ledger: EvidenceLedger | None = None,
        telemetry_context: TelemetryContext | None = None,
    ) -> None:
        if not isinstance(workspace, Workspace):
            raise TypeError("workspace must be a Workspace instance.")

        self._workspace = workspace
        self._ledger = ledger
        self._telemetry_context = telemetry_context or TelemetryContext()

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    def run_tests(
        self,
        target: str | Sequence[str] = "",
        timeout_seconds: int = DEFAULT_TEST_TIMEOUT,
        fail_fast: bool = False,
        verbose: bool = False,
        execution_id: UUID | None = None,
        task_id: UUID | None = None,
    ) -> ControlledTestResult:
        """Execute allowlisted pytest invocation within workspace boundary."""
        effective_execution_id = execution_id or uuid4()
        effective_task_id = task_id or self._workspace.task_id or uuid4()

        started_at = datetime.now(UTC)
        start_mono = time.monotonic()
        bounded_timeout = max(1, min(timeout_seconds, MAX_TEST_TIMEOUT))

        cmd = [sys.executable, "-m", "pytest"]
        cmd.append("-v" if verbose else "-q")
        if fail_fast:
            cmd.append("-x")

        # Collect target strings
        target_list: list[str] = []
        if isinstance(target, str):
            target_str = target.strip()
            if target_str:
                has_space = " " in target_str
                exists_with_space = (self._workspace.repository_root / target_str).exists()
                if has_space and not exists_with_space:
                    target_list.extend(target_str.split())
                else:
                    target_list.append(target_str)
        elif isinstance(target, (list, tuple, set)):
            for item in target:
                if isinstance(item, str) and item.strip():
                    target_list.append(item.strip())

        # Validate target path(s) strictly within workspace
        validated_targets: list[str] = []
        for t in target_list:
            norm_slashes = t.replace("\\", "/")
            if "\0" in t or ".." in norm_slashes.split("/"):
                raise ControlledExecutionError(
                    f"Target path '{t}' contains forbidden sequences or directory traversal."
                )
            base_part = norm_slashes.split("::")[0] if "::" in norm_slashes else norm_slashes
            sub_part = f"::{norm_slashes.split('::', 1)[1]}" if "::" in norm_slashes else ""
            try:
                resolved_target = self._workspace.validate_path(base_part)
                rel_target = str(self._workspace.relative_path(resolved_target)).replace("\\", "/")
                effective_target = f"{rel_target}{sub_part}"
                validated_targets.append(effective_target)
                cmd.append(effective_target)
            except (PathOutsideWorkspaceError, PathSecurityError, ValueError) as exc:
                raise ControlledExecutionError(
                    f"Test target '{t}' escapes workspace boundary: {exc}"
                ) from exc

        effective_target_display = (
            " ".join(validated_targets)
            if validated_targets
            else (target if isinstance(target, str) else "")
        )

        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = 0
        status = "passed"

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._workspace.repository_root),
                capture_output=True,
                text=True,
                timeout=bounded_timeout,
                shell=False,  # Strictly NO shell execution
                env=_get_sanitized_environment(),
            )
            exit_code = proc.returncode
            stdout = proc.stdout[:MAX_OUTPUT_CHARS] if proc.stdout else ""
            stderr = proc.stderr[:MAX_OUTPUT_CHARS] if proc.stderr else ""
            status = "passed" if exit_code == 0 else "failed"

        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            status = "timeout"
            raw_out = (
                exc.stdout.decode("utf-8", errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            raw_err = (
                exc.stderr.decode("utf-8", errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            stdout = str(raw_out)[:MAX_OUTPUT_CHARS]
            timeout_msg = f"\nTest execution timed out after {bounded_timeout} seconds."
            stderr = str(raw_err)[:MAX_OUTPUT_CHARS] + timeout_msg

        except Exception as exc:
            exit_code = -1
            status = "error"
            stderr = f"Subprocess invocation error: {exc}"

        duration_seconds = round(time.monotonic() - start_mono, 3)
        completed_at = datetime.now(UTC)

        result = ControlledTestResult(
            execution_id=effective_execution_id,
            target=effective_target_display,
            exit_code=exit_code,
            status=status,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration_seconds,
            started_at=started_at,
            completed_at=completed_at,
            timed_out=timed_out,
        )

        # Record OBSERVED test evidence into EvidenceLedger
        if self._ledger is not None:
            summary = (
                f"Controlled tests target='{effective_target_display}' status={status} "
                f"exit_code={exit_code} ({duration_seconds}s)"
            )
            content = f"{stdout}\n{stderr}".strip()[:MAX_OUTPUT_CHARS]
            self._ledger.record_observed(
                stage=SWETaskStage.RUN_TESTS,
                source="ControlledExecutionAuthority",
                content=content or summary,
                category=EvidenceCategory.TEST_RESULT,
                summary=summary,
                task_id=effective_task_id,
                execution_id=effective_execution_id,
                request_id=self._telemetry_context.request_id,
                trace_id=self._telemetry_context.trace_id,
                workspace_root=str(self._workspace.repository_root),
                metadata={
                    "target": effective_target_display,
                    "exit_code": exit_code,
                    "status": status,
                    "duration_seconds": duration_seconds,
                    "timed_out": timed_out,
                    "passed": result.passed,
                },
            )

        return result
