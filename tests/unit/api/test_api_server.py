import json
import threading
from http import HTTPStatus
from http.server import HTTPServer
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

    # 4. Path traversal attempt should be blocked (403 or 404)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urlopen(f"{base_url}/static/../../pyproject.toml")
    assert exc_info.value.code in (HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND)

