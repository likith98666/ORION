"""Unit tests for ORION Mission State & Evidence Ledger Persistence.

Verifies:
1. Missions are persisted to disk in data_dir / missions / <mission_id>.json upon creation.
2. A newly instantiated MissionAPIService (simulating a container restart) successfully
   restores all persisted missions from disk.
3. The restored mission preserves mission_id, task_id, objective, status, and timeline.
4. Readiness check verifies data_dir writeability when configured.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from orion.api.dto import TaskSubmissionRequest
from orion.api.service import MissionAPIService


def test_mission_persistence_save_and_reload(tmp_path: Path) -> None:
    """Verify that missions persist to disk and reload on service restart."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "orion_state"
    data_dir.mkdir()

    # Step 1: Initial Service Instance
    service_1 = MissionAPIService(default_workspace_path=workspace, data_dir=data_dir)
    assert service_1.missions_count == 0

    # Step 2: Submit a mission
    req = TaskSubmissionRequest(
        task="Audit repository documentation and check readiness status",
        workspace=str(workspace),
        execution_mode="controlled",
    )
    resp = service_1.submit_task(req)
    mission_id = UUID(resp.mission_id)
    assert service_1.missions_count == 1

    # Step 3: Verify the serialized file exists on disk
    persisted_file = data_dir / "missions" / f"{mission_id}.json"
    assert persisted_file.exists(), f"Expected persistence file {persisted_file} to exist"

    # Step 4: Simulate Container Restart by creating a fresh Service Instance
    service_2 = MissionAPIService(default_workspace_path=workspace, data_dir=data_dir)

    # Step 5: Verify the mission is restored in memory
    assert service_2.missions_count == 1
    reloaded = service_2.get_mission(mission_id)
    assert reloaded is not None
    assert reloaded.mission_id == str(mission_id)
    assert reloaded.task_id == str(mission_id)
    assert reloaded.objective == req.task
    assert reloaded.status == "initialized"

    # Step 6: Verify list_missions includes the restored mission
    all_missions = service_2.list_missions()
    assert len(all_missions) == 1
    assert all_missions[0].mission_id == str(mission_id)

    # Step 7: Verify timeline events are preserved
    timeline = service_2.get_mission_timeline(mission_id)
    assert timeline is not None
    assert len(timeline) >= 1
    assert timeline[0].title == "Task Created"


def test_service_readiness_checks_data_dir(tmp_path: Path) -> None:
    """Verify that readiness probe validates data_dir writeability when configured."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_dir = tmp_path / "orion_state"
    data_dir.mkdir()

    service = MissionAPIService(default_workspace_path=workspace, data_dir=data_dir)
    readiness = service.check_readiness()

    assert readiness.status == "ready"
    assert readiness.checks["workspace_writable"] is True
    assert readiness.checks.get("data_dir_writable") is True
