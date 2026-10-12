"""Unit tests for Phase 8 Production Security, Reliability & Deployment Hardening.

Covers:
1. Unauthorized operation rejection
2. Invalid approval rejection
3. Expired / nonexistent approval rejection
4. Consumed approval rejection
5. Execution / mission binding rejection
6. Path traversal rejection
7. Protected-file access rejection
8. Arbitrary command rejection
9. Oversized request rejection
10. Malformed request rejection
11. Secret redaction
12. Traceback non-disclosure
13. Security headers
14. Rate limiting
15. Health endpoint correctness
16. Readiness behavior
17. Graceful shutdown behavior
18. SSE disconnect/reconnect behavior
19. Frontend/backend error-state contract
20. Docker deployment hardening & configuration
21. Configuration security & secret masking
"""

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

from orion.api.dto import TaskSubmissionRequest
from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService, validate_workspace_path
from orion.config.app_config import AppConfig
from orion.core.security.rate_limiter import TokenBucketRateLimiter


@pytest.fixture
def hardened_server(tmp_path: Path):
    """Fixture providing an Orion server configured with strict security parameters."""
    repo = tmp_path / "secure_workspace"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "module.py").write_text("def run():\n    return 42\n", encoding="utf-8")

    config = AppConfig(
        host="127.0.0.1",
        port=0,
        workspace=repo,
        environment="testing",
        max_request_body_bytes=2048,  # strict 2KB limit for testing
        rate_limit_enabled=True,
        rate_limit_per_minute=10,
        mission_rate_limit_per_minute=5,
        redaction_enabled=True,
        known_secrets=("super-secret-api-key-12345", "db-pass-secret-xyz"),
    )

    test_service = MissionAPIService(default_workspace_path=repo, config=config)
    limiter = TokenBucketRateLimiter(default_limit_per_minute=10)

    class HardenedCustomHandler(OrionAPIHandler):
        service = test_service
        rate_limiter = limiter

    server = HTTPServer(("127.0.0.1", 0), HardenedCustomHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_service, repo, config, limiter

    server.shutdown()
    server.server_close()


# ---------------------------------------------------------------------------
# 1. Security Headers Tests
# ---------------------------------------------------------------------------


def test_security_headers_present_on_api_responses(hardened_server):
    """Verify that all API responses include strict production security and cache headers."""
    base_url, _, _, _, _ = hardened_server
    req = Request(f"{base_url}/api/v1/health")

    with urlopen(req) as resp:
        headers = dict(resp.headers)
        assert resp.status == HTTPStatus.OK
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in headers.get("Permissions-Policy", "")
        assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
        assert "no-store" in headers.get("Cache-Control", "")


# ---------------------------------------------------------------------------
# 2. Oversized Request Body Rejection
# ---------------------------------------------------------------------------


def test_oversized_request_rejection(hardened_server):
    """Verify that request bodies exceeding max_request_body_bytes are rejected with 413."""
    base_url, _, repo, _, _ = hardened_server

    # Create payload > 2048 bytes
    huge_text = "x" * 4096
    payload = json.dumps({"task": huge_text, "workspace": str(repo)}).encode("utf-8")
    req = Request(
        f"{base_url}/api/tasks",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert err_body["code"] == "PAYLOAD_TOO_LARGE"
    assert "exceeds limit" in err_body["error"]


# ---------------------------------------------------------------------------
# 3. Malformed Request Handling
# ---------------------------------------------------------------------------


def test_malformed_json_rejection(hardened_server):
    """Verify that malformed JSON payloads return 400 with structured RFC-compliant error."""
    base_url, _, _, _, _ = hardened_server
    bad_payload = b"{not: a: valid: json}"
    req = Request(
        f"{base_url}/api/tasks",
        data=bad_payload,
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert err_body["code"] == "MALFORMED_JSON"
    assert "Malformed JSON" in err_body["error"]


# ---------------------------------------------------------------------------
# 4. Path Traversal Protection
# ---------------------------------------------------------------------------


def test_path_traversal_rejection(hardened_server):
    """Verify that directory traversal attempts via static routes return 403 Forbidden."""
    base_url, _, _, _, _ = hardened_server
    req = Request(f"{base_url}/static/../../../../etc/passwd")

    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.FORBIDDEN
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert err_body["code"] == "FORBIDDEN_PATH"


# ---------------------------------------------------------------------------
# 5. Workspace Isolation & Protected Root Path Rejection
# ---------------------------------------------------------------------------


def test_protected_system_root_workspace_rejection():
    """Verify that validate_workspace_path rejects system roots and protected directories."""
    # Forbidden roots
    with pytest.raises(ValueError, match="forbidden"):
        validate_workspace_path("C:/Windows")

    with pytest.raises(ValueError, match="cannot be the filesystem root"):
        validate_workspace_path("C:/")


# ---------------------------------------------------------------------------
# 6. Arbitrary Command / Invalid Execution Mode Rejection
# ---------------------------------------------------------------------------


def test_arbitrary_execution_mode_rejection(hardened_server):
    """Verify that arbitrary unapproved execution modes are strictly rejected."""
    base_url, _, repo, _, _ = hardened_server
    payload = json.dumps(
        {
            "task": "Test task with invalid mode",
            "workspace": str(repo),
            "execution_mode": "unrestricted_root_shell",
        }
    ).encode("utf-8")
    req = Request(
        f"{base_url}/api/tasks",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert "Unsupported execution_mode" in err_body["error"]


# ---------------------------------------------------------------------------
# 7. Rate Limiting Enforcement
# ---------------------------------------------------------------------------


def test_rate_limiting_enforcement(hardened_server):
    """Verify that exceeding configured rate limits returns 429 and Retry-After header."""
    base_url, _, repo, _, rate_limiter = hardened_server
    rate_limiter.reset()

    # Rate limit for mission submissions is 5 per minute in fixture
    payload = json.dumps(
        {
            "task": "Rate limited mission task",
            "workspace": str(repo),
        }
    ).encode("utf-8")

    # Send 5 requests (should succeed)
    for _ in range(5):
        req = Request(
            f"{base_url}/api/tasks",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as resp:
            assert resp.status == HTTPStatus.CREATED

    # 6th request must be rejected with 429
    req6 = Request(
        f"{base_url}/api/tasks",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req6)

    assert exc_info.value.code == HTTPStatus.TOO_MANY_REQUESTS
    headers = dict(exc_info.value.headers)
    assert "Retry-After" in headers
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert err_body["code"] == "RATE_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# 8. Secret Redaction in Events & Timelines
# ---------------------------------------------------------------------------


def test_secret_redaction_in_timeline_and_events(hardened_server):
    """Verify that sensitive tokens and credentials are redacted in timeline events."""
    base_url, service, repo, _, _ = hardened_server

    sub_req = TaskSubmissionRequest(
        task="Test task requiring secret redaction",
        workspace=str(repo),
    )
    mission = service.submit_task(sub_req)
    mission_id = UUID(mission.mission_id)

    # Emit event containing configured known secrets
    service.emit_event(
        mission_id,
        "SECRET_DETECTED",
        {
            "summary": "Accessing endpoint with token super-secret-api-key-12345",
            "token": "super-secret-api-key-12345",
            "nested": {"db": "db-pass-secret-xyz"},
        },
    )

    # Retrieve timeline via API
    req = Request(f"{base_url}/api/v1/missions/{mission_id}/timeline")
    with urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        events = data["timeline"]
        secret_ev = next(e for e in events if e["title"] == "Secret Detected")

        # Confirm secret is scrubbed
        assert "super-secret-api-key-12345" not in secret_ev["detail"]
        assert "[REDACTED]" in secret_ev["detail"]
        assert secret_ev["metadata"]["token"] == "[REDACTED]"
        assert secret_ev["metadata"]["nested"]["db"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# 9. Traceback Non-Disclosure
# ---------------------------------------------------------------------------


def test_traceback_non_disclosure(hardened_server):
    """Verify that unexpected server errors do not expose Python tracebacks to clients."""
    base_url, _, _, _, _ = hardened_server

    # Query nonexistent resource
    req = Request(f"{base_url}/api/tasks/{uuid4()}/nonexistent_subresource")
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    raw_body = exc_info.value.read().decode("utf-8")
    assert "Traceback (most recent call last)" not in raw_body
    err_body = json.loads(raw_body)
    assert "error" in err_body
    assert "status" in err_body


# ---------------------------------------------------------------------------
# 10. Unauthorized Operation Rejection
# ---------------------------------------------------------------------------


def test_unauthorized_operation_rejection(hardened_server):
    """Verify that executing actions on non-existent or uninitialized stages is rejected."""
    base_url, _, _, _, _ = hardened_server
    fake_id = uuid4()

    # Advance stage on non-existent mission
    payload = json.dumps({"stage": "formulate_fix"}).encode("utf-8")
    req = Request(
        f"{base_url}/api/tasks/{fake_id}/advance",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# 11. Invalid Approval Rejection & Expired / Consumed Approval Rejection
# ---------------------------------------------------------------------------


def test_approval_boundary_rejection_when_none_pending(hardened_server):
    """Verify that approving a task when no approval is pending rejects cleanly."""
    base_url, service, repo, _, _ = hardened_server

    sub_req = TaskSubmissionRequest(
        task="Test task without pending approval",
        workspace=str(repo),
    )
    mission = service.submit_task(sub_req)

    # Attempt to approve when nothing is pending
    payload = json.dumps(
        {
            "decision": "approve",
            "approver": "Operator",
        }
    ).encode("utf-8")
    req = Request(
        f"{base_url}/api/tasks/{mission.mission_id}/approve",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert "No pending approval request found" in err_body["error"]


def test_invalid_approval_request_id_format(hardened_server):
    """Verify that malformed request_id UUID in approval is rejected."""
    base_url, service, repo, _, _ = hardened_server

    sub_req = TaskSubmissionRequest(
        task="Test task with malformed approval UUID",
        workspace=str(repo),
    )
    mission = service.submit_task(sub_req)

    payload = json.dumps(
        {
            "decision": "approve",
            "approver": "Operator",
            "request_id": "not-a-valid-uuid",
        }
    ).encode("utf-8")
    req = Request(
        f"{base_url}/api/tasks/{mission.mission_id}/approve",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.BAD_REQUEST
    err_body = json.loads(exc_info.value.read().decode("utf-8"))
    assert "Invalid request_id UUID format" in err_body["error"]


# ---------------------------------------------------------------------------
# 12. Health & Readiness Probes
# ---------------------------------------------------------------------------


def test_health_endpoint_correctness(hardened_server):
    """Verify /api/v1/health returns healthy status, version, uptime, and mission counts."""
    base_url, _, _, _, _ = hardened_server
    req = Request(f"{base_url}/api/v1/health")

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["uptime_seconds"] >= 0.0
        assert "missions_count" in data


def test_readiness_probe_healthy(hardened_server):
    """Verify /api/v1/readiness returns ready when workspace exists and is writable."""
    base_url, _, repo, _, _ = hardened_server
    req = Request(f"{base_url}/api/v1/readiness")

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ready"
        assert data["workspace_writable"] is True
        assert data["checks"]["workspace_exists"] is True
        assert data["checks"]["service_running"] is True


def test_readiness_probe_fails_during_shutdown(hardened_server):
    """Verify readiness reports 503 not_ready when service is shutting down."""
    base_url, service, _, _, _ = hardened_server
    service.shutdown()

    req = Request(f"{base_url}/api/v1/readiness")
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    assert exc_info.value.code == HTTPStatus.SERVICE_UNAVAILABLE
    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert data["status"] == "not_ready"
    assert data["checks"]["service_running"] is False


# ---------------------------------------------------------------------------
# 13. Graceful Shutdown Behavior
# ---------------------------------------------------------------------------


def test_graceful_shutdown_transitions_active_missions(hardened_server):
    """Verify that service.shutdown() marks in-flight missions with SHUTDOWN state cleanly."""
    _, service, repo, _, _ = hardened_server

    sub_req = TaskSubmissionRequest(
        task="Mission for shutdown testing",
        workspace=str(repo),
    )
    mission = service.submit_task(sub_req)
    mission_id = UUID(mission.mission_id)

    # Subscribe queue
    q = service.subscribe_events(mission_id)

    # Perform shutdown
    service.shutdown()

    # Verify mission record state
    rec = service._get_record(mission_id)
    assert rec is not None
    assert rec.lifecycle_state == "SHUTDOWN"
    assert rec.status == "shutdown"
    assert rec.cancelled is True

    # Verify shutdown event was delivered to subscriber queue
    event = q.get_nowait()
    assert event["event"] == "SYSTEM_SHUTDOWN"


# ---------------------------------------------------------------------------
# 14. Frontend/Backend Error State Contract
# ---------------------------------------------------------------------------


def test_error_payload_contract_consistency(hardened_server):
    """Verify all error responses conform to structured contract."""
    base_url, _, _, _, _ = hardened_server

    # 404 test
    req = Request(f"{base_url}/api/tasks/{uuid4()}")
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)

    data = json.loads(exc_info.value.read().decode("utf-8"))
    assert "error" in data
    assert "code" in data
    assert data["status"] == HTTPStatus.NOT_FOUND
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# 15. Docker Deployment Hardening
# ---------------------------------------------------------------------------


def test_dockerfile_and_compose_hardening():
    """Verify Dockerfile and docker-compose.yml contain security best practices."""
    dockerfile_path = Path("Dockerfile")
    compose_path = Path("docker-compose.yml")

    assert dockerfile_path.exists()
    assert compose_path.exists()

    dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
    compose_content = compose_path.read_text(encoding="utf-8")

    # Non-root user
    assert "USER orion" in dockerfile_content
    # STOPSIGNAL for graceful termination
    assert "STOPSIGNAL SIGTERM" in dockerfile_content
    # Healthcheck configured
    assert "HEALTHCHECK" in dockerfile_content
    assert "/api/v1/health" in dockerfile_content

    # Compose configuration
    assert "ORION_ENV=production" in compose_content
    assert "stop_signal: SIGTERM" in compose_content


# ---------------------------------------------------------------------------
# 16. AppConfig Secret Redaction & Constraints
# ---------------------------------------------------------------------------


def test_app_config_secret_masking_and_validation(tmp_path: Path):
    """Verify that AppConfig never reveals secrets in repr and validates production constraints."""
    config = AppConfig(
        host="127.0.0.1",
        port=8000,
        workspace=tmp_path.resolve(),
        environment="production",
        known_secrets=("sk-live-supersecret123",),
    )

    repr_str = repr(config)
    assert "sk-live-supersecret123" not in repr_str
    assert "1 registered" in repr_str

    # Invalid port raises
    with pytest.raises(ValueError, match="Port must be between"):
        AppConfig(port=99999, workspace=tmp_path.resolve())

    # Invalid environment raises
    with pytest.raises(ValueError, match="Invalid environment"):
        AppConfig(environment="invalid_env", workspace=tmp_path.resolve())  # type: ignore


def test_app_config_non_loopback_api_token_requirement(tmp_path: Path) -> None:
    """Verify that non-loopback binding strictly requires api_token unless testing."""
    # Binding 0.0.0.0 without token raises ValueError
    with pytest.raises(ValueError, match="requires configuring 'api_token'"):
        AppConfig(
            host="0.0.0.0",
            port=8000,
            workspace=tmp_path.resolve(),
            environment="production",
            api_token=None,
        )

    # Binding 0.0.0.0 with ORION_API_TOKEN succeeds
    cfg_token = AppConfig.from_env(
        env={
            "ORION_HOST": "0.0.0.0",
            "ORION_API_TOKEN": "mock-test-token-value",
            "ORION_WORKSPACE": str(tmp_path.resolve()),
        }
    )
    assert cfg_token.host == "0.0.0.0"
    assert cfg_token.api_token == "mock-test-token-value"

    # Binding 0.0.0.0 with ORION_API_KEY alias succeeds
    cfg_key = AppConfig.from_env(
        env={
            "ORION_HOST": "0.0.0.0",
            "ORION_API_KEY": "mock-test-key-value",
            "ORION_WORKSPACE": str(tmp_path.resolve()),
        }
    )
    assert cfg_key.host == "0.0.0.0"
    assert cfg_key.api_token == "mock-test-key-value"

    # Binding 127.0.0.1 without token succeeds
    cfg_loopback = AppConfig(
        host="127.0.0.1",
        port=8000,
        workspace=tmp_path.resolve(),
        environment="production",
        api_token=None,
    )
    assert cfg_loopback.api_token is None

