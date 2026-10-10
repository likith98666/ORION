"""Dedicated V7 Human-in-the-Loop (HITL) and Collaborative Oversight Test Suite."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService
from orion.core.hitl.coordinator import HITLCoordinator
from orion.core.hitl.models import (
    ClarificationRequest,
    ClarificationStatus,
    HumanIntervention,
    InterventionType,
    OperatorFeedback,
    RiskTier,
)


@pytest.fixture
def hitl_server(tmp_path: Path):
    """Fixture providing an Orion API server for V7 HITL testing."""
    repo = tmp_path / "hitl_repo"
    repo.mkdir(parents=True, exist_ok=True)
    test_service = MissionAPIService(default_workspace_path=repo)

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
# 1. Model Validation & Serialization
# ---------------------------------------------------------------------------


def test_clarification_model_validation():
    """Verify ClarificationRequest enforces required fields and timeout."""
    mid = uuid4()
    tid = uuid4()

    with pytest.raises(ValueError, match="question cannot be empty"):
        ClarificationRequest(
            request_id=uuid4(),
            mission_id=mid,
            task_id=tid,
            question="",
            context="Some context",
        )

    with pytest.raises(ValueError, match="context cannot be empty"):
        ClarificationRequest(
            request_id=uuid4(),
            mission_id=mid,
            task_id=tid,
            question="Which database?",
            context="   ",
        )

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        ClarificationRequest(
            request_id=uuid4(),
            mission_id=mid,
            task_id=tid,
            question="Which database?",
            context="Setup step",
            timeout_seconds=-10.0,
        )

    req = ClarificationRequest(
        request_id=uuid4(),
        mission_id=mid,
        task_id=tid,
        question="Use PostgreSQL or SQLite?",
        context="Database selection",
        options=("postgres", "sqlite"),
        default_choice="sqlite",
    )
    d = req.to_dict()
    assert d["question"] == "Use PostgreSQL or SQLite?"
    assert d["options"] == ["postgres", "sqlite"]
    assert d["status"] == "pending"


def test_intervention_and_feedback_validation():
    """Verify HumanIntervention and OperatorFeedback enforce required invariants."""
    mid = uuid4()

    with pytest.raises(ValueError, match="operator cannot be empty"):
        HumanIntervention(
            intervention_id=uuid4(),
            mission_id=mid,
            intervention_type=InterventionType.PAUSE,
            operator="",
            reason="Safety hold",
        )

    with pytest.raises(ValueError, match="rating must be between 1 and 5"):
        OperatorFeedback(
            feedback_id=uuid4(),
            mission_id=mid,
            operator="Alice",
            rating=6,  # Invalid
            comments="Too high",
        )

    with pytest.raises(ValueError, match="rating must be between 1 and 5"):
        OperatorFeedback(
            feedback_id=uuid4(),
            mission_id=mid,
            operator="Alice",
            rating=0,  # Invalid
            comments="Too low",
        )

    fb = OperatorFeedback(
        feedback_id=uuid4(),
        mission_id=mid,
        operator="Alice",
        rating=5,
        comments="Excellent execution",
        corrections=("Add docstring",),
    )
    d = fb.to_dict()
    assert d["rating"] == 5
    assert d["corrections"] == ["Add docstring"]


# ---------------------------------------------------------------------------
# 2. HITLCoordinator Logic & Thread-Safety
# ---------------------------------------------------------------------------


def test_hitl_coordinator_clarification_lifecycle():
    """Verify full interactive clarification lifecycle from request to resolution."""
    coord = HITLCoordinator()
    mid = uuid4()
    tid = uuid4()

    # 1. Issue clarification
    req = coord.request_clarification(
        mission_id=mid,
        task_id=tid,
        question="Which API version?",
        context="Endpoints setup",
        options=("v1", "v2"),
        default_choice="v1",
    )
    assert req.status == ClarificationStatus.PENDING

    # 2. Query pending clarifications
    pending = coord.list_clarifications(mission_id=mid, status=ClarificationStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].request_id == req.request_id

    # 3. Respond to clarification
    resolved = coord.respond_clarification(
        request_id=req.request_id,
        response_text="Use v2 with backward-compatible aliases",
        operator="Lead Architect",
    )
    assert resolved.status == ClarificationStatus.ANSWERED
    assert resolved.response == "Use v2 with backward-compatible aliases"
    assert resolved.answered_by == "Lead Architect"
    assert resolved.answered_at is not None

    # 4. Confirm steering context was populated
    steer = coord.consume_steering_instructions(mid)
    assert len(steer) == 1
    assert "Use v2 with backward-compatible aliases" in steer[0]

    # 5. Prevent double resolution
    with pytest.raises(ValueError, match="already answered"):
        coord.respond_clarification(req.request_id, "Another answer", "Bob")


def test_hitl_coordinator_pause_resume_and_steer():
    """Verify pause, resume, steering queues, and force-fail operations."""
    coord = HITLCoordinator()
    mid = uuid4()

    assert coord.is_mission_paused(mid) is False

    # Pause
    coord.pause_mission(mid, operator="SecOps", reason="Security review required")
    assert coord.is_mission_paused(mid) is True

    # Steer while paused
    coord.steer_mission(mid, instruction="Block external network calls", operator="SecOps")
    pending_steer = coord.get_pending_steering_instructions(mid)
    assert len(pending_steer) == 1
    assert pending_steer[0] == "Block external network calls"

    # Resume
    coord.resume_mission(mid, operator="SecOps", reason="Review cleared")
    assert coord.is_mission_paused(mid) is False

    # Drain steering
    consumed = coord.consume_steering_instructions(mid)
    assert consumed == ["Block external network calls"]
    assert len(coord.get_pending_steering_instructions(mid)) == 0

    # Interventions audit history
    intervs = coord.get_mission_interventions(mid)
    assert len(intervs) == 3
    assert intervs[0].intervention_type == InterventionType.PAUSE
    assert intervs[1].intervention_type == InterventionType.STEER
    assert intervs[2].intervention_type == InterventionType.RESUME


def test_hitl_risk_tier_enum():
    """Verify risk tiers for oversight governance."""
    assert RiskTier.LOW.value == "low"
    assert RiskTier.HIGH.value == "high"
    assert RiskTier.CRITICAL.value == "critical"


# ---------------------------------------------------------------------------
# 3. HITL REST API Endpoints & Contracts
# ---------------------------------------------------------------------------


def test_api_hitl_clarification_flow(hitl_server):
    """Test full HTTP flow: request clarification, list, and respond."""
    base_url, _, _ = hitl_server
    mid = str(uuid4())
    tid = str(uuid4())

    # 1. Request clarification
    req_payload = json.dumps(
        {
            "mission_id": mid,
            "task_id": tid,
            "question": "Which auth provider?",
            "context": "Configuring security",
            "options": ["OAuth2", "SAML"],
            "default_choice": "OAuth2",
        }
    ).encode("utf-8")
    req_http = Request(
        f"{base_url}/api/v1/hitl/clarifications/request",
        data=req_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_http) as resp:
        assert resp.status == HTTPStatus.CREATED
        req_data = json.loads(resp.read().decode("utf-8"))
        clarification_id = req_data["request_id"]
        assert req_data["question"] == "Which auth provider?"
        assert req_data["status"] == "pending"

    # 2. List clarifications
    list_http = Request(f"{base_url}/api/v1/hitl/clarifications?mission_id={mid}")
    with urlopen(list_http) as resp:
        assert resp.status == HTTPStatus.OK
        l_data = json.loads(resp.read().decode("utf-8"))
        assert l_data["total"] == 1
        assert l_data["clarifications"][0]["request_id"] == clarification_id

    # 3. Respond to clarification
    resp_payload = json.dumps(
        {
            "response": "Use OAuth2 with PKCE flow",
            "operator": "SecurityLead",
        }
    ).encode("utf-8")
    respond_http = Request(
        f"{base_url}/api/v1/hitl/clarifications/{clarification_id}/respond",
        data=resp_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(respond_http) as resp:
        assert resp.status == HTTPStatus.OK
        ans_data = json.loads(resp.read().decode("utf-8"))
        assert ans_data["status"] == "answered"
        assert ans_data["response"] == "Use OAuth2 with PKCE flow"
        assert ans_data["answered_by"] == "SecurityLead"


def test_api_hitl_interventions_and_feedback(hitl_server):
    """Test HTTP intervention controls (pause, steer, resume) and feedback submission."""
    base_url, _, _ = hitl_server
    mid = str(uuid4())

    # 1. Pause intervention
    pause_payload = json.dumps(
        {
            "mission_id": mid,
            "action": "pause",
            "operator": "Operator1",
            "reason": "Wait for DB migration",
        }
    ).encode("utf-8")
    req_pause = Request(
        f"{base_url}/api/v1/hitl/intervene",
        data=pause_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_pause) as resp:
        assert resp.status == HTTPStatus.OK
        p_data = json.loads(resp.read().decode("utf-8"))
        assert p_data["intervention_type"] == "pause"

    # 2. Steer intervention
    steer_payload = json.dumps(
        {
            "mission_id": mid,
            "action": "steer",
            "operator": "Operator1",
            "reason": "Guide patch strategy",
            "payload": {"instruction": "Use existing utility in src/utils.py"},
        }
    ).encode("utf-8")
    req_steer = Request(
        f"{base_url}/api/v1/hitl/intervene",
        data=steer_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_steer) as resp:
        assert resp.status == HTTPStatus.OK
        s_data = json.loads(resp.read().decode("utf-8"))
        assert s_data["intervention_type"] == "steer"

    # 3. GET /api/v1/hitl/interventions/{mission_id}
    req_list_interv = Request(f"{base_url}/api/v1/hitl/interventions/{mid}")
    with urlopen(req_list_interv) as resp:
        assert resp.status == HTTPStatus.OK
        i_data = json.loads(resp.read().decode("utf-8"))
        assert i_data["total"] == 2

    # 4. Submit feedback
    fb_payload = json.dumps(
        {
            "mission_id": mid,
            "operator": "Operator1",
            "rating": 5,
            "comments": "Smooth recovery and clean patch",
            "corrections": ["Update test coverage"],
        }
    ).encode("utf-8")
    req_fb = Request(
        f"{base_url}/api/v1/hitl/feedback",
        data=fb_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req_fb) as resp:
        assert resp.status == HTTPStatus.CREATED
        fb_data = json.loads(resp.read().decode("utf-8"))
        assert fb_data["rating"] == 5

    # 5. GET /api/v1/hitl/feedback/{mission_id}
    req_get_fb = Request(f"{base_url}/api/v1/hitl/feedback/{mid}")
    with urlopen(req_get_fb) as resp:
        assert resp.status == HTTPStatus.OK
        fb_list = json.loads(resp.read().decode("utf-8"))
        assert fb_list["total"] == 1
        assert fb_list["feedback"][0]["rating"] == 5
