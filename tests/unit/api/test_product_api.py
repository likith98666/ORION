"""Unit and integration tests for Phase 7 Product API, Task Lifecycle, and Observability."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest

from orion.api.dto import (
    TaskSubmissionRequest,
)
from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService, validate_workspace_path


@pytest.fixture
def product_server(tmp_path: Path):
    """Fixture providing a running Orion API server backed by a temporary repository."""
    repo = tmp_path / "valid_workspace"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    test_service = MissionAPIService()

    class CustomHandler(OrionAPIHandler):
        service = test_service

    server = HTTPServer(("127.0.0.1", 0), CustomHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_service, repo

    server.shutdown()
    server.server_close()


# ---------------------------------------------------------------------------
# Workspace Validation Tests
# ---------------------------------------------------------------------------


def test_validate_workspace_path_rejections(tmp_path: Path):
    """Verify validate_workspace_path rejects empty, non-existent, and forbidden paths."""
    # 1. Empty string
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_workspace_path("")

    # 2. Non-existent path
    with pytest.raises(ValueError, match="does not exist"):
        validate_workspace_path(str(tmp_path / "non_existent_dir_12345"))

    # 3. File instead of directory
    f = tmp_path / "some_file.txt"
    f.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        validate_workspace_path(str(f))

    # 4. Valid directory passes
    valid = validate_workspace_path(str(tmp_path))
    assert valid == tmp_path.resolve()


def test_task_submission_model_validation():
    """Verify TaskSubmissionRequest enforces minimum task length and valid execution modes."""
    with pytest.raises(ValueError, match="task must contain at least 3"):
        TaskSubmissionRequest(task="hi", workspace="C:/some/path")

    with pytest.raises(ValueError, match="workspace path cannot be empty"):
        TaskSubmissionRequest(task="Valid engineering task", workspace="")

    with pytest.raises(ValueError, match="Unsupported execution_mode"):
        TaskSubmissionRequest(
            task="Valid engineering task",
            workspace="C:/some/path",
            execution_mode="unrestricted_shell",
        )


# ---------------------------------------------------------------------------
# API Task Submission & Retrieval Tests
# ---------------------------------------------------------------------------


def test_api_submit_task_success(product_server):
    """Test POST /api/tasks creates task with proper metadata and lifecycle state."""
    base_url, _, repo = product_server

    payload = {
        "task": "Analyze authentication tests and fix defect",
        "workspace": str(repo),
        "execution_mode": "controlled",
    }
    req = Request(
        f"{base_url}/api/tasks",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.CREATED
        data = json.loads(resp.read().decode("utf-8"))
        assert "task_id" in data
        assert "execution_id" in data
        assert data["objective"] == "Analyze authentication tests and fix defect"
        assert data["workspace_root"] == str(repo.resolve())
        assert data["lifecycle_state"] == "RECEIVED"
        assert data["stages_total"] == 7
        assert data["stages_completed_count"] == 0

    task_id = data["task_id"]

    # Verify GET /api/tasks/{task_id}
    req_get = Request(f"{base_url}/api/tasks/{task_id}")
    with urlopen(req_get) as resp_get:
        assert resp_get.status == HTTPStatus.OK
        fetched = json.loads(resp_get.read().decode("utf-8"))
        assert fetched["task_id"] == task_id
        assert fetched["lifecycle_state"] == "RECEIVED"


def test_api_submit_task_rejection(product_server):
    """Test POST /api/tasks rejects invalid task or workspace."""
    base_url, _, _ = product_server

    # Reject non-existent workspace
    bad_payload = {
        "task": "Fix the issue",
        "workspace": "C:/invalid_path_does_not_exist_987654321",
    }
    req = Request(
        f"{base_url}/api/tasks",
        data=json.dumps(bad_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == HTTPStatus.BAD_REQUEST


# ---------------------------------------------------------------------------
# API Execution, Changes, Tests, and Recovery Observability Endpoints
# ---------------------------------------------------------------------------


def test_api_execution_and_observability_endpoints(product_server):
    """Test execution, changes, tests, recovery, and verification endpoints."""
    base_url, service, repo = product_server

    sub = TaskSubmissionRequest(
        task="Investigate performance degradation",
        workspace=str(repo),
        execution_mode="controlled",
    )
    mission = service.submit_task(sub)
    task_id = mission.mission_id

    # 1. GET /api/tasks/{id}/execution
    req_exec = Request(f"{base_url}/api/tasks/{task_id}/execution")
    with urlopen(req_exec) as resp:
        assert resp.status == HTTPStatus.OK
        ex_data = json.loads(resp.read().decode("utf-8"))
        assert ex_data["task_id"] == str(mission.task_id)
        assert ex_data["lifecycle_state"] == "RECEIVED"
        assert ex_data["stages_total"] == 7
        assert ex_data["approval_required"] is False

    # 2. GET /api/tasks/{id}/changes
    req_changes = Request(f"{base_url}/api/tasks/{task_id}/changes")
    with urlopen(req_changes) as resp:
        assert resp.status == HTTPStatus.OK
        ch_data = json.loads(resp.read().decode("utf-8"))
        assert "affected_files" in ch_data
        assert "unified_diff" in ch_data
        assert ch_data["validation_status"] == "PENDING"

    # 3. GET /api/tasks/{id}/tests
    req_tests = Request(f"{base_url}/api/tasks/{task_id}/tests")
    with urlopen(req_tests) as resp:
        assert resp.status == HTTPStatus.OK
        t_data = json.loads(resp.read().decode("utf-8"))
        assert "executed" in t_data
        assert t_data["executed"] is False

    # 4. GET /api/tasks/{id}/recovery
    req_rec = Request(f"{base_url}/api/tasks/{task_id}/recovery")
    with urlopen(req_rec) as resp:
        assert resp.status == HTTPStatus.OK
        r_data = json.loads(resp.read().decode("utf-8"))
        assert "remaining_budget" in r_data
        assert r_data["remaining_attempts"] >= 1
        assert "attempts_remaining" in r_data["remaining_budget"]

    # 5. GET /api/tasks/{id}/verification
    req_verif = Request(f"{base_url}/api/tasks/{task_id}/verification")
    with urlopen(req_verif) as resp:
        assert resp.status == HTTPStatus.OK
        v_data = json.loads(resp.read().decode("utf-8"))
        assert "status" in v_data
        assert v_data["passed"] is False


# ---------------------------------------------------------------------------
# Interactive Approval Flow Tests
# ---------------------------------------------------------------------------


def test_api_approval_flow(product_server):
    """Test interactive operator approval endpoint: approve and deny."""
    base_url, service, repo = product_server

    sub = TaskSubmissionRequest(
        task="Repair failing assertion",
        workspace=str(repo),
        execution_mode="controlled",
    )
    mission = service.submit_task(sub)
    mission_id = UUID(mission.mission_id)
    record = service._missions[mission_id]

    # Advance to FORMULATE_FIX and synthesize patch proposal
    service.advance_stage(mission_id, "inspect_repository")
    service.complete_stage(mission_id, "inspect_repository")
    service.advance_stage(mission_id, "analyze_failure")
    record.coordinator.analyze_failure(agent=record.agent, fallback_on_error=True)
    service.complete_stage(mission_id, "analyze_failure")
    service.advance_stage(mission_id, "formulate_fix")
    fix_prop = record.coordinator.formulate_fix(agent=record.agent, fallback_on_error=True)
    patch_prop = record.coordinator.synthesize_patch(
        agent=record.agent, fix_proposal=fix_prop, fallback_on_error=True
    )
    pkg = record.coordinator.request_patch_approval(patch_proposal=patch_prop, agent=record.agent)
    record.pending_approval = pkg
    record.lifecycle_state = "AWAITING_APPROVAL"

    # Query execution state — verify approval_required is True
    ex_info = service.get_task_execution(mission_id)
    assert ex_info is not None
    assert ex_info.approval_required is True
    assert ex_info.lifecycle_state == "AWAITING_APPROVAL"

    # POST /api/tasks/{id}/approve with "approve"
    approval_body = {
        "decision": "approve",
        "approver": "LeadSecurityOfficer",
        "reason": "Verified fix matches test scope",
    }
    req_appr = Request(
        f"{base_url}/api/tasks/{mission_id}/approve",
        data=json.dumps(approval_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req_appr) as resp:
        assert resp.status == HTTPStatus.OK
        appr_resp = json.loads(resp.read().decode("utf-8"))
        assert appr_resp["decision"] == "approve"
        assert appr_resp["status"] == "approved"
        assert appr_resp["approver"] == "LeadSecurityOfficer"

    # Verify refreshed record state
    assert record.pending_approval is not None
    assert record.pending_approval.is_approved is True
    assert record.lifecycle_state == "APPLYING"


def test_api_approval_denial(product_server):
    """Test denying approval terminates the task cleanly."""
    base_url, service, repo = product_server

    sub = TaskSubmissionRequest(
        task="Deny test",
        workspace=str(repo),
        execution_mode="controlled",
    )
    mission = service.submit_task(sub)
    mission_id = UUID(mission.mission_id)
    record = service._missions[mission_id]

    service.advance_stage(mission_id, "inspect_repository")
    service.complete_stage(mission_id, "inspect_repository")
    service.advance_stage(mission_id, "analyze_failure")
    record.coordinator.analyze_failure(agent=record.agent, fallback_on_error=True)
    service.complete_stage(mission_id, "analyze_failure")
    service.advance_stage(mission_id, "formulate_fix")
    fix_prop = record.coordinator.formulate_fix(agent=record.agent, fallback_on_error=True)
    patch_prop = record.coordinator.synthesize_patch(
        agent=record.agent, fix_proposal=fix_prop, fallback_on_error=True
    )
    pkg = record.coordinator.request_patch_approval(patch_proposal=patch_prop, agent=record.agent)
    record.pending_approval = pkg

    # POST /api/tasks/{id}/approve with "deny"
    deny_body = {
        "decision": "deny",
        "approver": "Operator",
        "reason": "Patch contains unauthorized file scope",
    }
    req_deny = Request(
        f"{base_url}/api/tasks/{mission_id}/approve",
        data=json.dumps(deny_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req_deny) as resp:
        assert resp.status == HTTPStatus.OK
        deny_resp = json.loads(resp.read().decode("utf-8"))
        assert deny_resp["decision"] == "deny"
        assert deny_resp["status"] == "denied"

    assert record.pending_approval is not None
    assert record.pending_approval.is_denied is True
    assert record.lifecycle_state == "TERMINATED"


# ---------------------------------------------------------------------------
# Pipeline Execution & SSE Streaming Tests
# ---------------------------------------------------------------------------


def test_api_run_pipeline_execution(product_server):
    """Test POST /api/tasks/{id}/run initiates execution pipeline."""
    base_url, service, repo = product_server

    sub = TaskSubmissionRequest(
        task="Full pipeline execution test",
        workspace=str(repo),
        execution_mode="controlled",
    )
    mission = service.submit_task(sub)
    task_id = mission.task_id

    # Run with auto_approve=True and background=False for deterministic test
    payload = {"auto_approve": True, "background": False}
    req = Request(
        f"{base_url}/api/tasks/{task_id}/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.ACCEPTED
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "executing"

    # Verify execution advanced
    rec = service._get_record(UUID(task_id))
    assert rec is not None
    assert len(rec.coordinator.completed_stages) >= 3


def test_api_sse_event_streaming(product_server):
    """Test GET /api/tasks/{id}/events provides live Server-Sent Events stream."""
    base_url, service, repo = product_server

    sub = TaskSubmissionRequest(
        task="SSE streaming verification",
        workspace=str(repo),
        execution_mode="controlled",
    )
    mission = service.submit_task(sub)
    task_id = mission.task_id

    # Connect to SSE stream
    req = Request(f"{base_url}/api/tasks/{task_id}/events")
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        assert "text/event-stream" in resp.headers.get("Content-Type", "")

        # Read first event (CONNECTED)
        line1 = resp.readline().decode("utf-8").strip()
        line2 = resp.readline().decode("utf-8").strip()
        assert line1.startswith("event: CONNECTED") or line1.startswith("data:")
        assert "connected" in (line1 + line2)


def test_api_error_handling(product_server):
    """Test API error handling for malformed JSON, invalid UUIDs, and unknown resources."""
    base_url, _, _ = product_server

    # 1. Malformed JSON
    req_malformed = Request(
        f"{base_url}/api/tasks",
        data=b"{not_valid_json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_malformed:
        urlopen(req_malformed)
    assert exc_malformed.value.code == HTTPStatus.BAD_REQUEST

    # 2. Invalid UUID
    req_bad_uuid = Request(f"{base_url}/api/tasks/not-a-valid-uuid")
    with pytest.raises(HTTPError) as exc_bad_uuid:
        urlopen(req_bad_uuid)
    assert exc_bad_uuid.value.code == HTTPStatus.NOT_FOUND

    # 3. Non-existent task UUID
    random_uuid = str(uuid4())
    req_missing = Request(f"{base_url}/api/tasks/{random_uuid}")
    with pytest.raises(HTTPError) as exc_missing:
        urlopen(req_missing)
    assert exc_missing.value.code == HTTPStatus.NOT_FOUND

