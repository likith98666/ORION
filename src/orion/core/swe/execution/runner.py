"""Controlled test execution authority enforcing strict allowlists and sandbox boundaries."""

from __future__ import annotations

import os
import subprocess
import sys
import time
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
        target: str = "",
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

        # Validate target path strictly within workspace
        if target and target.strip():
            target_str = target.strip()
            # Prohibit traversal and absolute paths outside workspace
            if "\0" in target_str or ".." in target_str.split("/"):
                raise ControlledExecutionError(
                    f"Target path '{target_str}' contains forbidden sequences."
                )
            try:
                resolved_target = self._workspace.validate_path(target_str)
                rel_target = str(self._workspace.relative_path(resolved_target))
                cmd.append(rel_target)
            except (PathOutsideWorkspaceError, PathSecurityError, ValueError) as exc:
                raise ControlledExecutionError(
                    f"Test target '{target_str}' escapes workspace boundary: {exc}"
                ) from exc

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
            target=target,
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
                f"Controlled tests target='{target}' status={status} exit_code={exit_code} "
                f"({duration_seconds}s)"
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
                    "target": target,
                    "exit_code": exit_code,
                    "status": status,
                    "duration_seconds": duration_seconds,
                    "timed_out": timed_out,
                },
            )

        return result
