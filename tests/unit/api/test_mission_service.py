from pathlib import Path
from uuid import UUID

import pytest

from orion.api.dto import CreateMissionRequest
from orion.api.service import MissionAPIService


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Fixture creating a temporary repository."""
    repo = tmp_path / "sample_repo"
    repo.mkdir(parents=True, exist_ok=True)
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("def hello(): return 'world'\n", encoding="utf-8")
    return repo


def test_service_create_and_get_mission(temp_repo: Path):
    """Verify MissionAPIService can create and retrieve a mission."""
    service = MissionAPIService()

    req = CreateMissionRequest(
        objective="Inspect and verify app",
        workspace_path=str(temp_repo),
    )

    mission = service.create_mission(req)
    assert mission.mission_id is not None
    assert mission.objective == "Inspect and verify app"
    assert mission.status == "initialized"
    assert mission.workspace_root == str(temp_repo.resolve())

    # Get mission
    fetched = service.get_mission(UUID(mission.mission_id))
    assert fetched is not None
    assert fetched.mission_id == mission.mission_id

    # List missions
    missions = service.list_missions()
    assert len(missions) == 1


def test_service_advance_stage_and_timeline(temp_repo: Path):
    """Verify MissionAPIService advances stage and logs timeline events."""
    service = MissionAPIService()
    req = CreateMissionRequest(
        objective="Advance workflow",
        workspace_path=str(temp_repo),
    )
    mission = service.create_mission(req)
    mission_id = UUID(mission.mission_id)

    advanced = service.advance_stage(mission_id, "inspect_repository")
    assert advanced.current_stage == "inspect_repository"
    assert "running_inspect_repository" in advanced.status

    timeline = service.get_mission_timeline(mission_id)
    assert timeline is not None
    assert len(timeline) >= 2  # initialized + advanced


def test_service_execute_tool(temp_repo: Path):
    """Verify MissionAPIService executes a stage-controlled tool."""
    service = MissionAPIService()
    req = CreateMissionRequest(
        objective="List files in repo",
        workspace_path=str(temp_repo),
    )
    mission = service.create_mission(req)
    mission_id = UUID(mission.mission_id)

    service.advance_stage(mission_id, "inspect_repository")

    result = service.execute_tool(
        mission_id=mission_id,
        stage="inspect_repository",
        tool_name="list_files",
        arguments={"path": "."},
    )

    assert result["success"] is True
    assert result["tool_name"] == "list_files"

    evidence = service.get_mission_evidence(mission_id)
    assert evidence is not None
    assert len(evidence) >= 1
    assert evidence[0].category == "repository_state"
