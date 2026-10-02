"""Unit and integration test suite for ORION V2 Advanced Mission Intelligence."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from orion.api.server import create_server
from orion.api.service import MissionAPIService
from orion.core.missions.engine import (
    MissionCancelledError,
    MissionExecutionEngine,
)
from orion.core.missions.graph import (
    MissionGraphCycleError,
    MissionTaskGraph,
)
from orion.core.missions.memory import (
    MemoryEntryType,
    MissionMemory,
)
from orion.core.missions.models import (
    ResourceBudget,
    TaskNode,
    TaskPriority,
    TaskRisk,
    TaskState,
)
from orion.core.missions.planner import (
    MissionPlanner,
    PlanProposal,
    PlanValidator,
)


def test_task_node_lifecycle_and_validation():
    """Verify TaskNode attributes, validation rules, and state transitions."""
    tid = uuid4()
    node = TaskNode(
        task_id=tid,
        title="Refactor Session Auth",
        description="Replace deprecated tokens with HMAC.",
        priority=TaskPriority.HIGH,
        risk=TaskRisk.MEDIUM,
    )
    assert node.state == TaskState.PENDING
    assert node.completed_at is None

    node.mark_state(TaskState.RUNNING)
    assert node.state == TaskState.RUNNING
    assert node.completed_at is None

    node.mark_state(TaskState.SUCCEEDED)
    assert node.state == TaskState.SUCCEEDED
    assert node.completed_at is not None

    d = node.to_dict()
    assert d["task_id"] == str(tid)
    assert d["priority"] == "high"
    assert d["risk"] == "medium"
    assert d["state"] == "succeeded"


def test_resource_budget_validation():
    """Verify ResourceBudget boundary checks."""
    budget = ResourceBudget(max_duration_seconds=120.0, max_attempts=2, max_file_changes=5)
    assert budget.max_duration_seconds == 120.0

    with pytest.raises(ValueError, match="max_duration_seconds must be positive"):
        ResourceBudget(max_duration_seconds=0.0)

    with pytest.raises(ValueError, match="max_attempts must be positive"):
        ResourceBudget(max_attempts=-1)


def test_mission_task_graph_dag_and_topological_sort():
    """Verify MissionTaskGraph executes DAG operations, detects cycles, and sorts topologically."""
    mid = uuid4()
    graph = MissionTaskGraph(mission_id=mid)

    t1 = TaskNode(task_id=uuid4(), title="Task 1: Inspect Repo", description="Read repo")
    t2 = TaskNode(
        task_id=uuid4(),
        title="Task 2: Write Fix",
        description="Apply patch",
        dependencies={t1.task_id},
    )
    t3 = TaskNode(
        task_id=uuid4(),
        title="Task 3: Run Tests",
        description="Verify",
        dependencies={t2.task_id},
    )

    graph.add_task(t1)
    graph.add_task(t2)
    graph.add_task(t3)

    assert not graph.has_cycles()
    sorted_nodes = graph.topological_sort()
    assert [n.task_id for n in sorted_nodes] == [t1.task_id, t2.task_id, t3.task_id]

    ready = graph.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == t1.task_id

    # Marking t1 succeeded makes t2 ready
    graph.mark_task_state(t1.task_id, TaskState.SUCCEEDED)
    ready = graph.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == t2.task_id


def test_mission_task_graph_cycle_prevention():
    """Verify adding circular dependencies raises MissionGraphCycleError."""
    mid = uuid4()
    graph = MissionTaskGraph(mission_id=mid)

    t1 = TaskNode(task_id=uuid4(), title="Task A", description="A")
    t2 = TaskNode(task_id=uuid4(), title="Task B", description="B", dependencies={t1.task_id})
    graph.add_task(t1)
    graph.add_task(t2)

    # Creating cycle: t1 depends on t2
    with pytest.raises(MissionGraphCycleError):
        graph.add_dependency(t1.task_id, t2.task_id)


def test_mission_task_graph_cascade_blocked():
    """Verify failing an upstream task cascades BLOCKED to downstream dependents."""
    mid = uuid4()
    graph = MissionTaskGraph(mission_id=mid)

    t1 = TaskNode(task_id=uuid4(), title="Parent Task", description="P")
    t2 = TaskNode(
        task_id=uuid4(), title="Child Task", description="C", dependencies={t1.task_id}
    )
    t3 = TaskNode(
        task_id=uuid4(), title="Grandchild Task", description="GC", dependencies={t2.task_id}
    )

    graph.add_task(t1)
    graph.add_task(t2)
    graph.add_task(t3)

    graph.mark_task_state(t1.task_id, TaskState.FAILED, error_message="Fatal crash")
    assert graph.get_task(t1.task_id).state == TaskState.FAILED
    assert graph.get_task(t2.task_id).state == TaskState.BLOCKED
    assert graph.get_task(t3.task_id).state == TaskState.BLOCKED


def test_plan_validator_rules():
    """Verify PlanValidator catches empty objectives, duplicate IDs, and cycles."""
    validator = PlanValidator()

    # Empty objective
    bad_proposal = PlanProposal(objective="", proposed_tasks=[{"task_id": "1", "title": "A"}])
    is_valid, errs = validator.validate(bad_proposal)
    assert not is_valid
    assert any("objective" in e for e in errs)

    # Duplicate IDs
    dup_proposal = PlanProposal(
        objective="Test Duplicates",
        proposed_tasks=[
            {"task_id": "same_id", "title": "A"},
            {"task_id": "same_id", "title": "B"},
        ],
    )
    is_valid, errs = validator.validate(dup_proposal)
    assert not is_valid
    assert any("Duplicate" in e for e in errs)


def test_mission_planner_decomposition():
    """Verify MissionPlanner decomposes a high-level compound objective into a valid DAG."""
    planner = MissionPlanner()
    objective = (
        "Fix the authentication bug, add regression tests, "
        "update the API documentation, and verify the test suite."
    )

    plan, graph = planner.decompose_objective(objective)
    assert len(plan.tasks) >= 5
    assert not graph.has_cycles()

    # Verify topological order executes inspection first, verification last
    ordered = graph.topological_sort()
    assert "Diagnose" in ordered[0].title
    assert "Final Mission Verification" in ordered[-1].title


def test_mission_memory_scoping_and_eviction():
    """Verify MissionMemory bounds capacity, supports filtering, searching, and deletion."""
    mid = uuid4()
    mem = MissionMemory(mission_id=mid, max_entries=3)

    e1 = mem.record_decision("Decide Auth Model", "Selected OAuth2 PKCE")
    e2 = mem.record_failure("Token Parse Error", "Malformed JWT header")
    mem.record_constraint("Forbidden Migration", "Do not alter users table schema")

    assert len(mem.get_entries()) == 3

    # Add 4th entry; e1 should be evicted (FIFO)
    mem.record(MemoryEntryType.OBSERVATION, "Telemetry Check", "Latency 42ms")
    entries = mem.get_entries()
    assert len(entries) == 3
    assert e1.entry_id not in [e.entry_id for e in entries]

    # Search
    search_res = mem.search("JWT")
    assert len(search_res) == 1
    assert search_res[0].entry_id == e2.entry_id

    # Filter
    failures = mem.get_entries(entry_type=MemoryEntryType.FAILURE)
    assert len(failures) == 1
    assert failures[0].entry_id == e2.entry_id

    # Delete entry
    deleted = mem.delete_entry(e2.entry_id)
    assert deleted is True
    assert len(mem.get_entries()) == 2

    # Clear
    cleared_count = mem.clear()
    assert cleared_count == 2
    assert len(mem.get_entries()) == 0


def test_mission_execution_engine_run_all():
    """Verify MissionExecutionEngine runs all tasks to successful completion."""
    planner = MissionPlanner()
    plan, graph = planner.decompose_objective("Fix calc addition bug and run tests")
    engine = MissionExecutionEngine(plan=plan, graph=graph)

    summary = engine.run_all()
    assert summary.status in (TaskState.VERIFIED, TaskState.SUCCEEDED)
    assert summary.succeeded_tasks > 0
    assert summary.failed_tasks == 0
    assert summary.blocked_tasks == 0


def test_mission_execution_engine_cancellation():
    """Verify cancellation stops execution and marks downstream tasks CANCELLED."""
    planner = MissionPlanner()
    plan, graph = planner.decompose_objective("Fix security flaw in token handler")
    engine = MissionExecutionEngine(plan=plan, graph=graph)

    engine.cancel(reason="Aborted by operator")
    with pytest.raises(MissionCancelledError):
        engine.execute_next_ready_task()

    for task in graph.tasks.values():
        assert task.state == TaskState.CANCELLED


@pytest.fixture
def mission_server(tmp_path: Path):
    """Spin up ephemeral test server with MissionAPIService."""
    service = MissionAPIService(default_workspace_path=tmp_path)
    server = create_server(host="127.0.0.1", port=0, service=service)
    server_port = server.server_address[1]

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server_port}"
    yield base_url, service
    server.shutdown()
    server.server_close()


def test_api_v2_mission_endpoints(mission_server):
    """Test POST /api/v1/missions/plan, GET graph, GET memory, and POST cancel."""
    base_url, _ = mission_server

    # 1. Plan Mission
    plan_payload = json.dumps({
        "objective": "Fix SQL injection in search endpoint, add tests, and update docs."
    }).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/missions/plan",
        data=plan_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.CREATED
        data = json.loads(resp.read().decode("utf-8"))
        assert "mission_id" in data
        assert "tasks" in data
        mission_id = data["mission_id"]

    # 2. Get Mission Graph
    with urlopen(f"{base_url}/api/v1/missions/{mission_id}/graph") as resp:
        assert resp.status == HTTPStatus.OK
        graph_data = json.loads(resp.read().decode("utf-8"))
        assert graph_data["mission_id"] == mission_id
        assert len(graph_data["ready_tasks"]) >= 1

    # 3. Get Mission Memory
    with urlopen(f"{base_url}/api/v1/missions/{mission_id}/memory") as resp:
        assert resp.status == HTTPStatus.OK
        mem_data = json.loads(resp.read().decode("utf-8"))
        assert mem_data["mission_id"] == mission_id

    # 4. Cancel Mission
    cancel_payload = json.dumps({"reason": "Test abort"}).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/missions/{mission_id}/cancel",
        data=cancel_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        cancel_resp = json.loads(resp.read().decode("utf-8"))
        assert cancel_resp["status"] == "cancelled"
