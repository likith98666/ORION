from uuid import uuid4

import pytest

from orion.api.dto import (
    CreateMissionRequest,
    EvidenceItemDTO,
    HealthResponse,
    MissionResponse,
)
from orion.core.swe.evidence import EvidenceCategory, EvidenceItem, EvidenceLevel
from orion.core.swe.stages import SWETaskStage


def test_create_mission_request_validation():
    """Verify CreateMissionRequest validates objective and workspace_path."""
    with pytest.raises(ValueError):
        CreateMissionRequest(objective="", workspace_path="/some/path")

    with pytest.raises(ValueError):
        CreateMissionRequest(objective="Fix bug", workspace_path="")

    req = CreateMissionRequest(
        objective="Repair math lib",
        workspace_path="/workspace/repo",
        target_files=("src/math.py",),
    )
    assert req.objective == "Repair math lib"
    assert req.workspace_path == "/workspace/repo"
    assert req.target_files == ("src/math.py",)


def test_evidence_item_dto_conversion():
    """Verify domain EvidenceItem converts cleanly to EvidenceItemDTO."""
    item = EvidenceItem(
        id=uuid4(),
        level=EvidenceLevel.OBSERVED,
        category=EvidenceCategory.TEST_RESULT,
        stage=SWETaskStage.RUN_TESTS,
        source="tool:run_tests",
        content="Tests passed: 5",
        summary="Passed",
        metadata={"exit_code": 0},
    )

    dto = EvidenceItemDTO.from_domain(item)
    assert dto.level == "observed"
    assert dto.category == "test_result"
    assert dto.stage == "run_tests"
    assert dto.content == "Tests passed: 5"
    assert dto.metadata["exit_code"] == 0

    dto_dict = dto.to_dict()
    assert dto_dict["level"] == "observed"
    assert dto_dict["id"] == str(item.id)


def test_mission_response_serialization():
    """Verify MissionResponse serializes properly to dictionary."""
    mission_id = str(uuid4())
    task_id = str(uuid4())

    resp = MissionResponse(
        mission_id=mission_id,
        task_id=task_id,
        objective="Repair test failure",
        workspace_root="/ws",
        status="running",
        current_stage="inspect_repository",
        completed_stages=(),
        stages_total=7,
        stages_completed_count=0,
        created_at="2026-10-02T12:00:00Z",
        summary="Active mission",
    )
    data = resp.to_dict()
    assert data["mission_id"] == mission_id
    assert data["objective"] == "Repair test failure"
    assert data["stages_total"] == 7


def test_health_response_serialization():
    """Verify HealthResponse serializes accurately."""
    health = HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime_seconds=42.5,
        missions_count=3,
        timestamp="2026-10-02T12:00:00Z",
    )
    data = health.to_dict()
    assert data["status"] == "healthy"
    assert data["missions_count"] == 3
