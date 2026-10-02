"""Unit and integration test suite for ORION V4 Advanced Multi-Agent Engineering."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from orion.api.server import create_server
from orion.api.service import MissionAPIService
from orion.core.agents.workforce.conflict import AgentConflictResolver
from orion.core.agents.workforce.contracts import WorkforceContractRegistry
from orion.core.agents.workforce.models import (
    AgentPermissionLevel,
    AgentProposal,
    WorkforceAgentContract,
    WorkforcePermissionError,
    WorkforceRole,
)
from orion.core.agents.workforce.orchestrator import WorkforceOrchestrator
from orion.core.agents.workforce.reviewer import IndependentReviewer


def test_workforce_contract_tool_authorization():
    """Verify WorkforceAgentContract enforces strict tool access boundaries."""
    aid = uuid4()
    contract = WorkforceAgentContract(
        agent_id=aid,
        role=WorkforceRole.INVESTIGATOR,
        permission_level=AgentPermissionLevel.READ_ONLY,
        allowed_tools=frozenset({"list_files", "read_file"}),
    )

    # Authorized tool call
    contract.validate_tool("read_file")

    # Unauthorized tool call
    with pytest.raises(WorkforcePermissionError, match="forbidden from using tool 'write_file'"):
        contract.validate_tool("write_file")


def test_workforce_contract_registry_roster():
    """Verify WorkforceContractRegistry creates standard roster with all 7 roles."""
    registry = WorkforceContractRegistry.create_default_roster()
    summary = registry.get_roster_summary()
    assert len(summary) == 7

    roles_in_roster = {item["role"] for item in summary}
    expected_roles = {r.value for r in WorkforceRole}
    assert roles_in_roster == expected_roles

    architects = registry.get_agents_by_role(WorkforceRole.ARCHITECT)
    assert len(architects) == 1
    assert architects[0].permission_level == AgentPermissionLevel.READ_ONLY


def test_workforce_orchestrator_parallel_execution():
    """Verify WorkforceOrchestrator executes multiple agent tasks concurrently."""
    registry = WorkforceContractRegistry.create_default_roster()
    orchestrator = WorkforceOrchestrator(registry=registry, max_workers=3)

    tasks = [
        (WorkforceRole.INVESTIGATOR, lambda c: f"Investigated by {c.role.value}"),
        (WorkforceRole.SECURITY_ANALYST, lambda c: f"Sec-checked by {c.role.value}"),
        (WorkforceRole.TESTER, lambda c: f"Tests verified by {c.role.value}"),
    ]

    results = orchestrator.execute_parallel(tasks, timeout_seconds=10.0)
    assert len(results) == 3
    assert all(r.success for r in results)
    returned_roles = {r.role for r in results}
    assert returned_roles == {
        WorkforceRole.INVESTIGATOR,
        WorkforceRole.SECURITY_ANALYST,
        WorkforceRole.TESTER,
    }


def test_workforce_orchestrator_cancellation():
    """Verify cancellation halts in-flight work."""
    registry = WorkforceContractRegistry.create_default_roster()
    orchestrator = WorkforceOrchestrator(registry=registry)

    orchestrator.cancel_all()
    tasks = [
        (WorkforceRole.INVESTIGATOR, lambda c: "done"),
    ]
    results = orchestrator.execute_parallel(tasks)
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "Cancelled"


def test_independent_reviewer_security_rejection():
    """Verify IndependentReviewer detects unsafe shell constructs and rejects."""
    reviewer = IndependentReviewer()
    unsafe_proposal = AgentProposal(
        proposal_id=uuid4(),
        agent_id=uuid4(),
        role=WorkforceRole.IMPLEMENTER,
        target_files=("src/dangerous.py",),
        patch_content="import os\nos.system('rmdir -rf /')\n",
        rationale="Clean temporary files",
    )

    verdict = reviewer.review(unsafe_proposal)
    assert verdict.status == "REJECTED"
    assert verdict.security_clean is False
    assert verdict.risk_level == "critical"
    assert any("Security Alert" in c for c in verdict.comments)


def test_independent_reviewer_syntax_error():
    """Verify IndependentReviewer catches syntax errors and requests changes."""
    reviewer = IndependentReviewer()
    syntax_error_proposal = AgentProposal(
        proposal_id=uuid4(),
        agent_id=uuid4(),
        role=WorkforceRole.IMPLEMENTER,
        target_files=("src/bad.py",),
        patch_content="def unclosed_fn(:\n    pass\n",
        rationale="Fix logic",
    )

    verdict = reviewer.review(syntax_error_proposal)
    assert verdict.status == "CHANGES_REQUESTED"
    assert verdict.code_quality_clean is False
    assert any("Syntax Error" in c for c in verdict.comments)


def test_independent_reviewer_clean_approval():
    """Verify clean, valid proposal with tests passes review."""
    reviewer = IndependentReviewer()
    clean_proposal = AgentProposal(
        proposal_id=uuid4(),
        agent_id=uuid4(),
        role=WorkforceRole.IMPLEMENTER,
        target_files=("src/calc.py", "tests/test_calc.py"),
        patch_content="def add(a: int, b: int) -> int:\n    return a + b\n",
        rationale="Fix addition logic and include tests/test_calc.py",
    )

    verdict = reviewer.review(clean_proposal)
    assert verdict.status == "APPROVED"
    assert verdict.security_clean is True
    assert verdict.code_quality_clean is True


def test_agent_conflict_resolver():
    """Verify AgentConflictResolver arbitrates proposals and flags human approval when close."""
    resolver = AgentConflictResolver()

    # Proposal A: high confidence, supported by 3 evidence items
    prop_a = AgentProposal(
        proposal_id=uuid4(),
        agent_id=uuid4(),
        role=WorkforceRole.IMPLEMENTER,
        target_files=("src/calc.py",),
        patch_content="return a + b",
        rationale="Canonical fix",
        confidence_score=0.95,
        evidence_items=("ev_test_pass", "ev_ast_clean", "ev_diff"),
    )

    # Proposal B: lower confidence, no evidence items
    prop_b = AgentProposal(
        proposal_id=uuid4(),
        agent_id=uuid4(),
        role=WorkforceRole.IMPLEMENTER,
        target_files=("src/calc.py", "src/extra.py", "src/third.py"),
        patch_content="return a + b + 0",
        rationale="Alternative fix",
        confidence_score=0.60,
    )

    # Decisive resolution
    res_decisive = resolver.resolve([prop_a, prop_b])
    assert res_decisive.selected_proposal_id == prop_a.proposal_id
    assert res_decisive.requires_human_approval is False

    # Close competition triggers human approval
    prop_c = AgentProposal(
        proposal_id=uuid4(),
        agent_id=uuid4(),
        role=WorkforceRole.IMPLEMENTER,
        target_files=("src/calc.py",),
        patch_content="return b + a",
        rationale="Commutative fix",
        confidence_score=0.94,
        evidence_items=("ev_test_pass", "ev_ast_clean", "ev_diff"),
    )

    res_close = resolver.resolve([prop_a, prop_c])
    assert res_close.requires_human_approval is True
    assert res_close.selected_proposal_id is None


@pytest.fixture
def workforce_server(tmp_path: Path):
    """Spin up server instance for workforce API verification."""
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


def test_api_v4_workforce_endpoints(workforce_server):
    """Test GET roster, POST review, and POST resolve-conflict endpoints."""
    base_url, _ = workforce_server

    # 1. GET /api/v1/workforce/roster
    with urlopen(f"{base_url}/api/v1/workforce/roster") as resp:
        assert resp.status == HTTPStatus.OK
        roster_data = json.loads(resp.read().decode("utf-8"))
        assert "roster" in roster_data
        assert roster_data["total"] == 7

    # 2. POST /api/v1/workforce/review
    review_payload = json.dumps({
        "role": "implementer",
        "target_files": ["src/math.py", "tests/test_math.py"],
        "patch_content": "def square(n: int) -> int:\n    return n * n\n",
        "rationale": "Add square function with tests",
    }).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/workforce/review",
        data=review_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        review_data = json.loads(resp.read().decode("utf-8"))
        assert review_data["status"] == "APPROVED"
        assert review_data["security_clean"] is True

    # 3. POST /api/v1/workforce/resolve-conflict
    p1_id = str(uuid4())
    p2_id = str(uuid4())
    conflict_payload = json.dumps({
        "proposals": [
            {
                "proposal_id": p1_id,
                "role": "implementer",
                "target_files": ["src/fix.py"],
                "patch_content": "def f(): pass\n",
                "rationale": "Fix 1",
                "confidence_score": 0.9,
                "evidence_items": ["e1", "e2"],
            },
            {
                "proposal_id": p2_id,
                "role": "implementer",
                "target_files": ["src/fix.py"],
                "patch_content": "def f(): return True\n",
                "rationale": "Fix 2",
                "confidence_score": 0.5,
                "evidence_items": [],
            },
        ]
    }).encode("utf-8")
    req_c = Request(
        f"{base_url}/api/v1/workforce/resolve-conflict",
        data=conflict_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_c) as resp:
        assert resp.status == HTTPStatus.OK
        conflict_data = json.loads(resp.read().decode("utf-8"))
        assert conflict_data["selected_proposal_id"] == p1_id
        assert conflict_data["requires_human_approval"] is False
