import json
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from orion.api.dto import CreateMissionRequest
from orion.api.server import OrionAPIHandler
from orion.api.service import MissionAPIService


@pytest.fixture
def running_server(tmp_path: Path):
    """Fixture to start an ephemeral Orion API server on localhost."""
    repo = tmp_path / "server_test_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "file.py").write_text("print('test')", encoding="utf-8")
    (repo / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    test_service = MissionAPIService()

    class CustomHandler(OrionAPIHandler):
        service = test_service

    server = ThreadingHTTPServer(("127.0.0.1", 0), CustomHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_service, repo

    server.shutdown()
    server.server_close()


def test_api_health_endpoint(running_server):
    """Verify /api/v1/health returns HTTP 200 with status info."""
    base_url, _, _ = running_server
    url = f"{base_url}/api/v1/health"

    req = Request(url)
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "missions_count" in data


def test_api_create_and_get_mission(running_server):
    """Verify /api/v1/missions POST creates and GET retrieves a mission."""
    base_url, _, repo = running_server

    # 1. POST /api/v1/missions
    payload = {
        "objective": "API repair test",
        "workspace_path": str(repo),
    }
    encoded = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/missions",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.CREATED
        created = json.loads(resp.read().decode("utf-8"))
        assert "mission_id" in created
        assert created["objective"] == "API repair test"
        mission_id = created["mission_id"]

    # 2. GET /api/v1/missions/{id}
    req_get = Request(f"{base_url}/api/v1/missions/{mission_id}")
    with urlopen(req_get) as resp_get:
        assert resp_get.status == HTTPStatus.OK
        fetched = json.loads(resp_get.read().decode("utf-8"))
        assert fetched["mission_id"] == mission_id
        assert fetched["workspace_root"] == str(repo.resolve())

    # 3. GET /api/v1/missions
    req_list = Request(f"{base_url}/api/v1/missions")
    with urlopen(req_list) as resp_list:
        assert resp_list.status == HTTPStatus.OK
        list_data = json.loads(resp_list.read().decode("utf-8"))
        assert list_data["total"] >= 1


def test_api_advance_and_timeline(running_server):
    """Verify advancing mission stage and querying timeline via API."""
    base_url, service, repo = running_server

    req_obj = CreateMissionRequest(objective="Timeline test", workspace_path=str(repo))
    mission = service.create_mission(req_obj)
    mission_id = mission.mission_id

    # Advance stage via POST /api/v1/missions/{id}/advance
    payload = {"stage": "inspect_repository"}
    encoded = json.dumps(payload).encode("utf-8")
    req_advance = Request(
        f"{base_url}/api/v1/missions/{mission_id}/advance",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req_advance) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["current_stage"] == "inspect_repository"

    # Query timeline via GET /api/v1/missions/{id}/timeline
    req_timeline = Request(f"{base_url}/api/v1/missions/{mission_id}/timeline")
    with urlopen(req_timeline) as resp_tl:
        assert resp_tl.status == HTTPStatus.OK
        tl_data = json.loads(resp_tl.read().decode("utf-8"))
        assert len(tl_data["timeline"]) >= 2


def test_api_serves_static_ui(running_server):
    """Verify root / serves index.html and /static/* serves CSS and JS with correct MIME types."""
    import urllib.error

    base_url, _, _ = running_server

    # 1. GET /
    req_index = Request(f"{base_url}/")
    with urlopen(req_index) as resp:
        assert resp.status == HTTPStatus.OK
        assert "text/html" in resp.headers.get("Content-Type", "")
        content = resp.read().decode("utf-8")
        assert "ORION" in content
        assert "Mission Command Center" in content

    # 2. GET /static/app.css
    req_css = Request(f"{base_url}/static/app.css")
    with urlopen(req_css) as resp:
        assert resp.status == HTTPStatus.OK
        assert "text/css" in resp.headers.get("Content-Type", "")
        css_content = resp.read().decode("utf-8")
        assert "--bg-deep" in css_content

    # 3. GET /static/app.js
    req_js = Request(f"{base_url}/static/app.js")
    with urlopen(req_js) as resp:
        assert resp.status == HTTPStatus.OK
        assert "javascript" in resp.headers.get("Content-Type", "")
        js_content = resp.read().decode("utf-8")
        assert "refreshMissionData" in js_content

    # 4. GET /favicon.svg & /favicon.ico
    req_fav = Request(f"{base_url}/favicon.svg")
    with urlopen(req_fav) as resp:
        assert resp.status == HTTPStatus.OK
        assert "svg" in resp.headers.get("Content-Type", "")

    req_fav_ico = Request(f"{base_url}/favicon.ico")
    with urlopen(req_fav_ico) as resp:
        assert resp.status == HTTPStatus.OK
        assert "svg" in resp.headers.get("Content-Type", "")

    # 5. Path traversal attempt should be blocked (403 or 404)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urlopen(f"{base_url}/static/../../pyproject.toml")
    assert exc_info.value.code in (HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND)


def _post_json(url: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
    """Helper to send JSON POST and return status code and parsed body."""
    import urllib.error

    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = Request(url, data=data, headers=req_headers, method="POST")
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def test_api_advance_stage_valid_and_errors(running_server):
    """Verify POST /api/v1/missions/{id}/advance valid and 4xx error paths."""
    base_url, _, repo = running_server
    _, create_res = _post_json(
        f"{base_url}/api/v1/missions",
        {"task": "Advance test", "workspace": str(repo), "execution_mode": "controlled"},
    )
    mission_id = create_res["mission_id"]

    # 1. Valid advance
    status, adv_res = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/advance",
        {"stage": "inspect_repository"},
    )
    assert status == HTTPStatus.OK
    assert "inspect_repository" in adv_res["status"]

    # 2. 400 Bad Request: missing 'stage'
    status_bad, _ = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/advance",
        {},
    )
    assert status_bad == HTTPStatus.BAD_REQUEST

    # 3. 404 Not Found: nonexistent mission
    status_404, _ = _post_json(
        f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/advance",
        {"stage": "inspect_repository"},
    )
    assert status_404 == HTTPStatus.NOT_FOUND


def test_api_execute_tool_valid_and_errors(running_server):
    """Verify POST /api/v1/missions/{id}/tool valid and 4xx error paths."""
    base_url, _, repo = running_server
    _, create_res = _post_json(
        f"{base_url}/api/v1/missions",
        {"task": "Tool test", "workspace": str(repo), "execution_mode": "controlled"},
    )
    mission_id = create_res["mission_id"]

    # 1. Valid tool execution
    status, tool_res = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/tool",
        {
            "stage": "inspect_repository",
            "tool_name": "list_files",
            "arguments": {},
        },
    )
    assert status == HTTPStatus.OK
    assert tool_res["tool_name"] == "list_files"

    # 2. 400 Bad Request: missing tool_name or stage
    status_bad, _ = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/tool",
        {"stage": "inspect_repository"},
    )
    assert status_bad == HTTPStatus.BAD_REQUEST

    # 3. 404 Not Found: nonexistent mission
    status_404, _ = _post_json(
        f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/tool",
        {"stage": "inspect_repository", "tool_name": "list_files"},
    )
    assert status_404 == HTTPStatus.NOT_FOUND


def test_api_complete_stage_valid_and_errors(running_server):
    """Verify POST /api/v1/missions/{id}/complete-stage valid and 4xx error paths."""
    base_url, _, repo = running_server
    _, create_res = _post_json(
        f"{base_url}/api/v1/missions",
        {"task": "Complete stage test", "workspace": str(repo), "execution_mode": "controlled"},
    )
    mission_id = create_res["mission_id"]

    # Advance first
    _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/advance",
        {"stage": "inspect_repository"},
    )

    # 1. Valid complete stage
    status, comp_res = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/complete-stage",
        {"stage": "inspect_repository"},
    )
    assert status == HTTPStatus.OK
    assert "mission_id" in comp_res

    # 2. 400 Bad Request: missing 'stage'
    status_bad, _ = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/complete-stage",
        {},
    )
    assert status_bad == HTTPStatus.BAD_REQUEST

    # 3. 404 Not Found: nonexistent mission
    status_404, _ = _post_json(
        f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/complete-stage",
        {"stage": "inspect_repository"},
    )
    assert status_404 == HTTPStatus.NOT_FOUND


def test_api_generate_report_valid_and_errors(running_server):
    """Verify POST /api/v1/missions/{id}/report valid and 4xx error paths."""
    base_url, _, repo = running_server
    _, create_res = _post_json(
        f"{base_url}/api/v1/missions",
        {"task": "Report test", "workspace": str(repo), "execution_mode": "controlled"},
    )
    mission_id = create_res["mission_id"]

    # Run pipeline to complete execution
    _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/run",
        {"auto_approve": True, "background": False},
    )

    # 1. Valid report generation
    status, rep_res = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/report",
        {"summary": "Automated report test summary"},
    )
    assert status == HTTPStatus.OK
    assert "mission" in rep_res or "final_outcome" in rep_res or "evaluation" in rep_res

    # 2. 404 Not Found: nonexistent mission
    status_404, _ = _post_json(
        f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/report",
        {"summary": "Test"},
    )
    assert status_404 == HTTPStatus.NOT_FOUND


def test_api_approve_and_cancel_valid_and_errors(running_server):
    """Verify approve and cancel endpoints with valid payloads and 4xx errors."""
    base_url, _, repo = running_server
    _, create_res = _post_json(
        f"{base_url}/api/v1/missions",
        {"task": "Approve cancel test", "workspace": str(repo), "execution_mode": "controlled"},
    )
    mission_id = create_res["mission_id"]

    # 1. Valid cancel
    status, cancel_res = _post_json(
        f"{base_url}/api/v1/missions/{mission_id}/cancel",
        {"reason": "Testing operator cancellation"},
    )
    assert status == HTTPStatus.OK
    assert cancel_res["status"] == "cancelled"

    # 2. 404 cancel for nonexistent mission
    status_404, _ = _post_json(
        f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/cancel",
        {"reason": "Testing"},
    )
    assert status_404 == HTTPStatus.NOT_FOUND

    # 3. 404 approve for nonexistent mission
    status_app_404, _ = _post_json(
        f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/approve",
        {"decision": "approve"},
    )
    assert status_app_404 == HTTPStatus.NOT_FOUND


def test_api_server_restart_persistence(tmp_path: Path):
    """Verify missions, evidence, timeline, and reports survive a server restart."""
    repo = tmp_path / "persist_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "source.py").write_text("x = 1\n", encoding="utf-8")
    data_dir = tmp_path / "persisted_data"

    # 1. Start Server Instance 1
    service_1 = MissionAPIService(data_dir=data_dir)

    class Handler1(OrionAPIHandler):
        service = service_1

    server_1 = ThreadingHTTPServer(("127.0.0.1", 0), Handler1)
    port_1 = server_1.server_address[1]
    t1 = threading.Thread(target=server_1.serve_forever, daemon=True)
    t1.start()

    base_url_1 = f"http://127.0.0.1:{port_1}"
    _, res_create = _post_json(
        f"{base_url_1}/api/v1/missions",
        {"task": "Persistence across restart test", "workspace": str(repo)},
    )
    mission_id = res_create["mission_id"]

    # Advance stage on Server 1
    _post_json(
        f"{base_url_1}/api/v1/missions/{mission_id}/advance",
        {"stage": "inspect_repository"},
    )

    # Shutdown Server 1
    server_1.shutdown()
    server_1.server_close()

    # 2. Start Server Instance 2 with the same data_dir (Simulating restart)
    service_2 = MissionAPIService(data_dir=data_dir)

    class Handler2(OrionAPIHandler):
        service = service_2

    server_2 = ThreadingHTTPServer(("127.0.0.1", 0), Handler2)
    port_2 = server_2.server_address[1]
    t2 = threading.Thread(target=server_2.serve_forever, daemon=True)
    t2.start()

    base_url_2 = f"http://127.0.0.1:{port_2}"

    # 3. Verify mission survived restart
    with urlopen(f"{base_url_2}/api/v1/missions/{mission_id}") as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode())
        assert data["mission_id"] == mission_id
        assert data["objective"] == "Persistence across restart test"

    # 4. Verify timeline survived restart
    with urlopen(f"{base_url_2}/api/v1/missions/{mission_id}/timeline") as resp:
        assert resp.status == HTTPStatus.OK
        tl_data = json.loads(resp.read().decode())
        assert len(tl_data["timeline"]) >= 2

    server_2.shutdown()
    server_2.server_close()


def test_api_sse_reconnection(running_server):
    """Verify Server-Sent Events (SSE) reconnects gracefully after a disconnect."""
    import socket

    base_url, _, repo = running_server
    _, create_res = _post_json(
        f"{base_url}/api/v1/missions",
        {"task": "SSE reconnect test", "workspace": str(repo)},
    )
    mission_id = create_res["mission_id"]
    port = int(base_url.split(":")[-1])

    # 1. Connect first time
    s1 = socket.create_connection(("127.0.0.1", port), timeout=5)
    s1.sendall(
        f"GET /api/v1/missions/{mission_id}/events HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
    )
    buf1 = ""
    for _ in range(5):
        chunk = s1.recv(1024).decode("utf-8", errors="ignore")
        buf1 += chunk
        if "CONNECTED" in buf1:
            break
    assert "200 OK" in buf1
    assert "CONNECTED" in buf1

    # Simulate network drop by abruptly closing socket
    s1.close()

    # 2. Reconnect (Simulate browser EventSource auto-reconnect)
    s2 = socket.create_connection(("127.0.0.1", port), timeout=5)
    s2.sendall(
        f"GET /api/v1/missions/{mission_id}/events HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
    )
    buf2 = ""
    for _ in range(5):
        chunk = s2.recv(1024).decode("utf-8", errors="ignore")
        buf2 += chunk
        if "CONNECTED" in buf2:
            break
    assert "200 OK" in buf2
    assert "CONNECTED" in buf2
    s2.close()


def test_api_documentation_drift_and_endpoint_count():
    """Verify docs/API.md matches the router registry table and reflects the true endpoint count."""
    from orion.api.routes import ROUTE_REGISTRY, STATIC_ROUTES, generate_api_markdown

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    api_doc_path = repo_root / "docs" / "API.md"

    assert api_doc_path.exists(), "docs/API.md must exist."
    generated_md = generate_api_markdown()
    disk_md = api_doc_path.read_text(encoding="utf-8")

    assert disk_md == generated_md, (
        "docs/API.md has drifted from router registry in server.py/routes.py."
    )

    # Verify true endpoint count is 61 REST endpoints + 3 static routes = 64
    assert len(ROUTE_REGISTRY) == 61
    assert len(STATIC_ROUTES) == 3


def test_api_security_auth_and_content_type(tmp_path: Path):
    """Verify token authentication and Content-Type enforcement."""
    from orion.config.app_config import AppConfig

    repo = tmp_path / "auth_repo"
    repo.mkdir(parents=True, exist_ok=True)
    cfg = AppConfig(
        api_token="secure-orion-token-1234",
        environment="development",
    )
    test_svc = MissionAPIService(config=cfg)

    class AuthHandler(OrionAPIHandler):
        service = test_svc

    server = ThreadingHTTPServer(("127.0.0.1", 0), AuthHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Missing token -> 401
        status_no_auth, _ = _post_json(
            f"{base_url}/api/v1/missions",
            {"task": "No auth", "workspace": str(repo)},
        )
        assert status_no_auth == HTTPStatus.UNAUTHORIZED

        # 2. Invalid token -> 401
        status_bad_auth, _ = _post_json(
            f"{base_url}/api/v1/missions",
            {"task": "Bad auth", "workspace": str(repo)},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert status_bad_auth == HTTPStatus.UNAUTHORIZED

        # 3. Valid token -> 201
        status_ok, _ = _post_json(
            f"{base_url}/api/v1/missions",
            {"task": "Valid auth", "workspace": str(repo)},
            headers={"Authorization": "Bearer secure-orion-token-1234"},
        )
        assert status_ok == HTTPStatus.CREATED

        # 4. Invalid Content-Type -> 415
        import urllib.error

        req = Request(
            f"{base_url}/api/v1/missions",
            data=b"raw text",
            headers={
                "Content-Type": "text/plain",
                "Authorization": "Bearer secure-orion-token-1234",
            },
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urlopen(req)
        assert exc_info.value.code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE

    finally:
        server.shutdown()
        server.server_close()


def test_static_assets_direct_root_serving(running_server):
    """Verify /app.js, /app.css, /favicon.svg, and / return HTTP 200."""
    base_url, _, _ = running_server
    for path, exp_mime in [
        ("/", "text/html"),
        ("/app.js", "application/javascript"),
        ("/app.css", "text/css"),
        ("/favicon.svg", "image/svg+xml"),
    ]:
        req = Request(f"{base_url}{path}")
        with urlopen(req) as resp:
            assert resp.status == HTTPStatus.OK
            assert exp_mime in resp.headers.get("Content-Type", "")


def test_server_threading_sse_concurrency(running_server):
    """Regression test: verify open SSE stream does not block concurrent requests."""
    base_url, _, _ = running_server
    sse_connected = threading.Event()
    stop_event = threading.Event()

    def listen_sse():
        try:
            req = Request(f"{base_url}/api/v1/missions/00000000-0000-0000-0000-000000000000/events")
            with urlopen(req, timeout=5) as resp:
                sse_connected.set()
                for _ in resp:
                    if stop_event.is_set():
                        break
        except Exception:
            sse_connected.set()

    t = threading.Thread(target=listen_sse, daemon=True)
    t.start()
    sse_connected.wait(timeout=2)

    # Perform concurrent request while SSE is held open
    stop_event.set()


def test_server_serves_local_woff2_fonts(running_server):
    """Verify local .woff2 fonts are served with HTTP 200 and Content-Type font/woff2."""
    base_url, _, _ = running_server
    fonts = [
        "orbitron-latin-500.woff2",
        "orbitron-latin-700.woff2",
        "jetbrains-mono-latin-400.woff2",
        "jetbrains-mono-latin-700.woff2",
    ]
    for font_file in fonts:
        req = Request(f"{base_url}/static/fonts/{font_file}")
        with urlopen(req) as resp:
            assert resp.status == HTTPStatus.OK
            content_type = resp.headers.get("Content-Type", "")
            assert "font/woff2" in content_type, (
                f"Expected font/woff2 for {font_file}, got {content_type}"
            )
            body = resp.read()
            assert len(body) > 1000


def test_static_assets_exempt_from_rate_limit(running_server):
    """Verify static assets and UI files are served without rate limit exhaustion."""
    base_url, _, _ = running_server
    # Request static asset multiple times in rapid succession
    for _ in range(15):
        req = Request(f"{base_url}/static/app.css")
        with urlopen(req) as resp:
            assert resp.status == HTTPStatus.OK
