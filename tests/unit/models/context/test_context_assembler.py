"""Unit tests for ContextAssembler configuration, bounds, and edge cases."""

from __future__ import annotations

from uuid import uuid4

import pytest

from orion.core.swe.evidence import EvidenceCategory, EvidenceItem, EvidenceLevel
from orion.core.swe.stages import SWETaskStage
from orion.core.workspace.models import ExecutionIdentity
from orion.models.context.assembler import (
    ContextAssembler,
    ContextLimits,
    relativize_path,
)
from orion.models.context.models import (
    FencedEvidenceItem,
    UntrustedExecutionOutput,
    UntrustedFileContent,
)
from orion.models.contracts import ModelRequest


def test_context_limits_validation() -> None:
    with pytest.raises(ValueError, match="max_file_chars must be greater than zero"):
        ContextLimits(max_file_chars=0)

    with pytest.raises(ValueError, match="max_files must be greater than zero"):
        ContextLimits(max_files=-1)

    with pytest.raises(ValueError, match="max_execution_output_chars must be greater than zero"):
        ContextLimits(max_execution_output_chars=0)

    with pytest.raises(ValueError, match="max_total_untrusted_chars must be greater than zero"):
        ContextLimits(max_total_untrusted_chars=-5)

    with pytest.raises(ValueError, match="max_total_prompt_chars must be greater than zero"):
        ContextLimits(max_total_prompt_chars=0)


def test_relativize_path_validations() -> None:
    with pytest.raises(ValueError, match="Path contains null byte"):
        relativize_path("src/foo\0bar.py")

    with pytest.raises(ValueError, match="Path cannot be empty"):
        relativize_path("   ")

    assert relativize_path("./src/./foo.py") == "src/foo.py"
    assert relativize_path(r"\\host\share\repo\file.txt") == "host/share/repo/file.txt"
    assert relativize_path("/") == "."


def test_untrusted_file_content_validations() -> None:
    with pytest.raises(ValueError, match="Repository-relative path cannot be empty"):
        UntrustedFileContent(path="   ", content="data")

    with pytest.raises(ValueError, match="Path contains null byte"):
        UntrustedFileContent(path="src/\0bad.py", content="data")


def test_untrusted_execution_output_validations() -> None:
    with pytest.raises(ValueError, match="tool_name cannot be empty"):
        UntrustedExecutionOutput(tool_name="   ", output="data")


def test_assembler_build_empty_context() -> None:
    assembler = ContextAssembler()
    ctx = assembler.build_context(
        task_objective="Empty context test",
    )
    assert ctx.task_objective == "Empty context test"
    assert len(ctx.repository_files) == 0
    assert len(ctx.execution_outputs) == 0
    assert len(ctx.evidence_items) == 0

    req = ctx.to_model_request()
    assert isinstance(req, ModelRequest)
    assert "# TASK OBJECTIVE" in req.prompt
    assert "Empty context test" in req.prompt
    assert "UNTRUSTED DATA BOUNDARY" not in req.prompt


def test_assembler_build_with_dict_items() -> None:
    assembler = ContextAssembler()
    files = [
        {"path": "src/a.py", "content": "print('a')", "stage": "inspect"},
    ]
    outputs = [
        {"tool_name": "git_status", "output": "clean", "exit_code": 0},
    ]
    ctx = assembler.build_context(
        task_objective="Dict item test",
        repository_files=files,
        execution_outputs=outputs,
    )
    assert len(ctx.repository_files) == 1
    assert ctx.repository_files[0].path == "src/a.py"
    assert len(ctx.execution_outputs) == 1
    assert ctx.execution_outputs[0].tool_name == "git_status"


def test_assembler_caps_max_files() -> None:
    limits = ContextLimits(max_files=3)
    assembler = ContextAssembler(limits=limits)
    files = [(f"src/file_{i}.py", f"content {i}") for i in range(10)]
    ctx = assembler.build_context(
        task_objective="Max files test",
        repository_files=files,
    )
    assert len(ctx.repository_files) == 3


def test_assembler_includes_execution_identity_telemetry() -> None:
    assembler = ContextAssembler()
    ws_id = uuid4()
    task_id = uuid4()
    exec_id = uuid4()
    req_id = uuid4()
    identity = ExecutionIdentity(
        workspace_id=ws_id,
        task_id=task_id,
        execution_id=exec_id,
        request_id=req_id,
    )
    ctx = assembler.build_context(
        task_objective="Identity test",
        execution_identity=identity,
    )
    req = ctx.to_model_request()
    assert req.metadata is not None
    assert req.metadata["workspace_id"] == str(ws_id)
    assert req.metadata["task_id"] == str(task_id)
    assert req.metadata["execution_id"] == str(exec_id)
    assert req.request_id == str(req_id)


def test_fenced_evidence_item_conversion() -> None:
    item = EvidenceItem(
        id=uuid4(),
        level=EvidenceLevel.OBSERVED,
        category=EvidenceCategory.COMMAND_RESULT,
        stage=SWETaskStage.RUN_TESTS,
        source="linter",
        content="No issues found",
        summary="Clean lint",
    )
    fenced = FencedEvidenceItem.from_evidence_item(item)
    assert fenced.evidence_id == str(item.id)
    assert fenced.level == EvidenceLevel.OBSERVED
    assert fenced.category == "command_result"
    assert fenced.stage == "run_tests"
    assert fenced.summary == "Clean lint"
