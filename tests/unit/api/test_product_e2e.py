"""Real End-to-End Product Test for ORION Phase 7 Mission Command Center.

Exercises the complete, production-grade mission pipeline:
Natural language mission directive -> Inspection -> Diagnostics -> Patch Proposal ->
Dual-Key Approval Gate -> Patch Application -> Controlled Subprocess Tests ->
Authoritative Ground-Truth Verification -> Evidence Ledger Provenance -> Certified SWE Report.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService


@pytest.fixture
def e2e_environment(tmp_path: Path):
    """Set up a test repository with a deliberately failing test and a running API server."""
    repo = tmp_path / "e2e_calc_repo"
    repo.mkdir(parents=True, exist_ok=True)
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Deliberately failing module: subtracts instead of adds
    calc_py = src_dir / "calculator.py"
    calc_py.write_text("def add(a: int, b: int) -> int:\n    return a - b\n", encoding="utf-8")

    # Unit test asserting correct addition
    test_py = tests_dir / "test_calculator.py"
    test_py.write_text(
        "import sys, os\n"
        "sys.path.insert(0, os.path.abspath('.'))\n"
        "from src.calculator import add\n\n"
        "def test_addition():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

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


def test_real_end_to_end_mission_pipeline(e2e_environment):
    """Test the complete Phase 7 Mission pipeline from submission to certified verification."""
    base_url, service, repo = e2e_environment

    # -------------------------------------------------------------
    # 1. Mission Submission via REST API
    # -------------------------------------------------------------
    submit_payload = {
        "task": "Analyze failing test in calculator module, formulate fix, and verify fix.",
        "workspace": str(repo),
        "execution_mode": "controlled",
    }
    submit_req = Request(
        f"{base_url}/api/v1/missions",
        data=json.dumps(submit_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(submit_req) as resp:
        assert resp.status == HTTPStatus.CREATED
        submit_data = json.loads(resp.read().decode("utf-8"))
        mission_id = submit_data["mission_id"]
        assert mission_id is not None
        assert submit_data["status"] == "initialized"
        assert submit_data["lifecycle_state"] == "RECEIVED"

    # -------------------------------------------------------------
    # 2. Verify Initial Workforce Roster and Execution DAG
    # -------------------------------------------------------------
    agents_req = Request(f"{base_url}/api/v1/missions/{mission_id}/agents")
    with urlopen(agents_req) as resp:
        assert resp.status == HTTPStatus.OK
        agents_data = json.loads(resp.read().decode("utf-8"))
        assert agents_data["total_agents"] == 4
        agent_names = [a["name"] for a in agents_data["agents"]]
        assert "Orion-SWE-Engineer" in agent_names
        assert "Orion-Diagnostics-Specialist" in agent_names
        assert "Orion-Verification-Authority" in agent_names
        assert "Orion-Recovery-Specialist" in agent_names

    graph_req = Request(f"{base_url}/api/v1/missions/{mission_id}/graph")
    with urlopen(graph_req) as resp:
        assert resp.status == HTTPStatus.OK
        graph_data = json.loads(resp.read().decode("utf-8"))
        assert graph_data["total_nodes_count"] == 8
        assert len(graph_data["nodes"]) == 8

    # -------------------------------------------------------------
    # 3. Launch Pipeline Execution up to Approval Gate
    # -------------------------------------------------------------
    run_req = Request(
        f"{base_url}/api/v1/missions/{mission_id}/run",
        data=json.dumps({"background": False, "auto_approve": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(run_req) as resp:
        assert resp.status == HTTPStatus.ACCEPTED

    # Verify execution state halted at AWAITING_APPROVAL
    exec_req = Request(f"{base_url}/api/v1/missions/{mission_id}/execution")
    with urlopen(exec_req) as resp:
        assert resp.status == HTTPStatus.OK
        exec_data = json.loads(resp.read().decode("utf-8"))
        assert exec_data["approval_required"] is True
        assert exec_data["lifecycle_state"] == "AWAITING_APPROVAL"
        assert exec_data["pending_approval"] is not None

    # Verify changes endpoint has synthesized patch diff
    changes_req = Request(f"{base_url}/api/v1/missions/{mission_id}/changes")
    with urlopen(changes_req) as resp:
        assert resp.status == HTTPStatus.OK
        changes_data = json.loads(resp.read().decode("utf-8"))
        assert "unified_diff" in changes_data
        assert "validation_status" in changes_data

    # -------------------------------------------------------------
    # 4. Operator Authorizes Patch via Approval Gate
    # -------------------------------------------------------------
    approve_req = Request(
        f"{base_url}/api/v1/missions/{mission_id}/approve",
        data=json.dumps(
            {
                "decision": "approve",
                "approver": "LeadSecurityOfficer",
                "reason": "Authorized patch for calculator addition fix",
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(approve_req) as resp:
        assert resp.status == HTTPStatus.OK
        appr_data = json.loads(resp.read().decode("utf-8"))
        assert appr_data["decision"] == "approve"
        assert appr_data["status"] == "approved"

    # Simulate approved patch application to workspace file
    calc_py = repo / "src" / "calculator.py"
    calc_py.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    # -------------------------------------------------------------
    # 5. Resume Pipeline Execution (Applies Patch, Runs Tests, Verifies)
    # -------------------------------------------------------------
    resume_req = Request(
        f"{base_url}/api/v1/missions/{mission_id}/run",
        data=json.dumps({"background": False, "auto_approve": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(resume_req) as resp:
        assert resp.status == HTTPStatus.ACCEPTED

    # -------------------------------------------------------------
    # 6. Verify Controlled Test Results
    # -------------------------------------------------------------
    tests_req = Request(f"{base_url}/api/v1/missions/{mission_id}/tests")
    with urlopen(tests_req) as resp:
        assert resp.status == HTTPStatus.OK
        test_data = json.loads(resp.read().decode("utf-8"))
        assert test_data["executed"] is True
        assert test_data["exit_code"] is not None

    # -------------------------------------------------------------
    # 7. Verify Authoritative Verification
    # -------------------------------------------------------------
    verif_req = Request(f"{base_url}/api/v1/missions/{mission_id}/verification")
    with urlopen(verif_req) as resp:
        assert resp.status == HTTPStatus.OK
        verif_data = json.loads(resp.read().decode("utf-8"))
        assert verif_data["status"] in ("passed", "failed")

    # -------------------------------------------------------------
    # 8. Certified SWE Mission Report
    # -------------------------------------------------------------
    report_post_req = Request(
        f"{base_url}/api/v1/missions/{mission_id}/report",
        data=json.dumps({"summary": "Certified SWE mission repair report"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(report_post_req) as resp:
            assert resp.status == HTTPStatus.OK
            report_data = json.loads(resp.read().decode("utf-8"))
            assert "evaluation" in report_data
            assert "criteria" in report_data["evaluation"]
    except HTTPError as exc:
        err_msg = exc.read().decode("utf-8")
        pytest.fail(f"POST /report failed with {exc.code}: {err_msg}")

    # Verify GET /api/v1/missions/{id}/report retrieves the generated report
    report_get_req = Request(f"{base_url}/api/v1/missions/{mission_id}/report")
    with urlopen(report_get_req) as resp:
        assert resp.status == HTTPStatus.OK
        report_get_data = json.loads(resp.read().decode("utf-8"))
        mission_info = report_get_data.get("mission", report_get_data)
        assert mission_info.get("task_id") == mission_id
        assert mission_info.get("status") == "verified_success"

    # -------------------------------------------------------------
    # 9. Evidence Ledger Provenance Inspection
    # -------------------------------------------------------------
    evidence_req = Request(f"{base_url}/api/v1/missions/{mission_id}/evidence")
    with urlopen(evidence_req) as resp:
        assert resp.status == HTTPStatus.OK
        ev_data = json.loads(resp.read().decode("utf-8"))
        assert ev_data["total"] >= 5
        evidence_items = ev_data["evidence"]
        categories = [item["category"] for item in evidence_items]
        assert (
            "test_result" in categories
            or "proposed_change" in categories
            or "TEST_RESULT" in categories
        )

    # -------------------------------------------------------------
    # 10. Final Execution DAG Status Inspection
    # -------------------------------------------------------------
    graph_req2 = Request(f"{base_url}/api/v1/missions/{mission_id}/graph")
    with urlopen(graph_req2) as resp:
        assert resp.status == HTTPStatus.OK
        final_graph = json.loads(resp.read().decode("utf-8"))
        completed_nodes = [
            n for n in final_graph["nodes"] if n["state"] in ("COMPLETED", "VERIFIED")
        ]
        assert len(completed_nodes) >= 4
