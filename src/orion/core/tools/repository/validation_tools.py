import importlib.util
import os
import subprocess
import sys
import time
from typing import Any

from orion.core.agents.permissions import AgentPermission
from orion.core.security.risk import ToolRiskLevel
from orion.core.tools.definition import ToolDefinition
from orion.core.tools.input_schema import (
    ToolInputField,
    ToolInputSchema,
    ToolInputType,
)
from orion.core.tools.repository.common import get_effective_workspace
from orion.core.tools.repository.models import ValidationResult
from orion.core.workspace.models import Workspace

DEFAULT_VALIDATION_TIMEOUT = 30
MAX_VALIDATION_TIMEOUT = 120
MAX_OUTPUT_CHARS = 65536

SENSITIVE_ENV_PREFIXES = (
    "AWS_",
    "GITHUB_",
    "GITLAB_",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "PASSWORD",
    "PRIVATE_KEY",
    "ACCESS_KEY",
)


def _get_sanitized_environment() -> dict[str, str]:
    """Create a sanitized environment dictionary excluding sensitive credential variables."""
    return {
        key: val
        for key, val in os.environ.items()
        if not any(key.upper().startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES)
    }


def execute_validation_command(
    operation: str,
    cmd: list[str],
    workspace: Workspace,
    timeout_seconds: int = DEFAULT_VALIDATION_TIMEOUT,
) -> ValidationResult:
    """Execute a strictly allowlisted validation command without shell execution."""
    start_time = time.monotonic()
    timed_out = False
    stdout = ""
    stderr = ""
    exit_code = 0
    status = "passed"

    bounded_timeout = max(1, min(timeout_seconds, MAX_VALIDATION_TIMEOUT))
    env = _get_sanitized_environment()

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace.repository_root),
            capture_output=True,
            text=True,
            timeout=bounded_timeout,
            shell=False,  # Enforce NO shell execution
            env=env,
        )
        duration = time.monotonic() - start_time
        exit_code = proc.returncode
        stdout = proc.stdout[:MAX_OUTPUT_CHARS] if proc.stdout else ""
        stderr = proc.stderr[:MAX_OUTPUT_CHARS] if proc.stderr else ""
        status = "passed" if exit_code == 0 else "failed"

    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start_time
        timed_out = True
        exit_code = -1
        status = "timeout"
        stdout = exc.stdout[:MAX_OUTPUT_CHARS] if exc.stdout else ""
        timeout_msg = f"\nValidation execution timed out after {bounded_timeout} seconds."
        stderr = (exc.stderr[:MAX_OUTPUT_CHARS] if exc.stderr else "") + timeout_msg

    except Exception as exc:
        duration = time.monotonic() - start_time
        exit_code = -1
        status = "error"
        stderr = f"Validation command failed: {exc}"

    return ValidationResult(
        operation=operation,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration=round(duration, 3),
        timed_out=timed_out,
        workspace_id=str(workspace.workspace_id),
    )


def build_run_tests_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the run_tests ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="target",
                input_type=ToolInputType.STRING,
                required=False,
            ),
            ToolInputField(
                name="fail_fast",
                input_type=ToolInputType.BOOLEAN,
                required=False,
            ),
            ToolInputField(
                name="verbose",
                input_type=ToolInputType.BOOLEAN,
                required=False,
            ),
            ToolInputField(
                name="timeout_seconds",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="workspace",
                input_type=ToolInputType.ANY,
                required=False,
                nullable=True,
            ),
        ),
        allow_unknown_fields=False,
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        target = (arguments.get("target") or "").strip()
        fail_fast = bool(arguments.get("fail_fast", False))
        verbose = bool(arguments.get("verbose", False))
        timeout_seconds = int(arguments.get("timeout_seconds", DEFAULT_VALIDATION_TIMEOUT))

        cmd = [sys.executable, "-m", "pytest"]
        cmd.append("-v" if verbose else "-q")

        if fail_fast:
            cmd.append("-x")

        if target:
            target_path = ws.validate_path(target)
            rel_target = str(ws.relative_path(target_path))
            cmd.append(rel_target)

        result = execute_validation_command(
            operation="test",
            cmd=cmd,
            workspace=ws,
            timeout_seconds=timeout_seconds,
        )
        return result.to_dict()

    return ToolDefinition(
        name="run_tests",
        description="Execute automated tests within the workspace repository root using allowlisted pytest invocation.",
        permission=AgentPermission.CODE_EXECUTION,
        risk_level=ToolRiskLevel.MEDIUM,
        input_schema=schema,
        handler=handler,
    )


def build_run_lint_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the run_lint ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="target",
                input_type=ToolInputType.STRING,
                required=False,
            ),
            ToolInputField(
                name="timeout_seconds",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="workspace",
                input_type=ToolInputType.ANY,
                required=False,
                nullable=True,
            ),
        ),
        allow_unknown_fields=False,
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        target = (arguments.get("target") or ".").strip()
        timeout_seconds = int(arguments.get("timeout_seconds", DEFAULT_VALIDATION_TIMEOUT))

        target_path = ws.validate_path(target)
        rel_target = str(ws.relative_path(target_path))

        # Check if ruff is available, else fallback to py_compile
        has_ruff = importlib.util.find_spec("ruff") is not None
        if has_ruff:
            cmd = [sys.executable, "-m", "ruff", "check", rel_target]
        else:
            cmd = [sys.executable, "-m", "py_compile", rel_target]

        result = execute_validation_command(
            operation="lint",
            cmd=cmd,
            workspace=ws,
            timeout_seconds=timeout_seconds,
        )
        return result.to_dict()

    return ToolDefinition(
        name="run_lint",
        description="Execute lint analysis within the workspace repository root using allowlisted linting tool.",
        permission=AgentPermission.CODE_EXECUTION,
        risk_level=ToolRiskLevel.MEDIUM,
        input_schema=schema,
        handler=handler,
    )


def build_run_typecheck_tool(workspace: Workspace | None = None) -> ToolDefinition:
    """Build the run_typecheck ToolDefinition."""

    schema = ToolInputSchema(
        fields=(
            ToolInputField(
                name="target",
                input_type=ToolInputType.STRING,
                required=False,
            ),
            ToolInputField(
                name="timeout_seconds",
                input_type=ToolInputType.INTEGER,
                required=False,
            ),
            ToolInputField(
                name="workspace",
                input_type=ToolInputType.ANY,
                required=False,
                nullable=True,
            ),
        ),
        allow_unknown_fields=False,
    )

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        ws = get_effective_workspace(workspace, arguments)
        target = (arguments.get("target") or ".").strip()
        timeout_seconds = int(arguments.get("timeout_seconds", DEFAULT_VALIDATION_TIMEOUT))

        target_path = ws.validate_path(target)
        rel_target = str(ws.relative_path(target_path))

        cmd = [sys.executable, "-m", "mypy", rel_target]

        result = execute_validation_command(
            operation="typecheck",
            cmd=cmd,
            workspace=ws,
            timeout_seconds=timeout_seconds,
        )
        return result.to_dict()

    return ToolDefinition(
        name="run_typecheck",
        description="Execute type check analysis within the workspace repository root using allowlisted mypy invocation.",
        permission=AgentPermission.CODE_EXECUTION,
        risk_level=ToolRiskLevel.MEDIUM,
        input_schema=schema,
        handler=handler,
    )
