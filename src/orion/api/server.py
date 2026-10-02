from __future__ import annotations

import json
import mimetypes
import queue
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from orion.api.dto import (
    HealthResponse,
    TaskApprovalRequest,
    TaskSubmissionRequest,
)
from orion.api.service import MissionAPIService

ORION_VERSION = "1.0.0"
STATIC_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"


class OrionAPIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API, SSE streams, and UI static assets."""

    service: MissionAPIService = MissionAPIService()

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """Route GET requests to API endpoints, event streams, or static assets."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Health endpoint
        if path == "/api/v1/health" or path == "/api/health":
            self._handle_health()
            return

        # Collection endpoints: list missions/tasks
        if path in ("/api/tasks", "/api/v1/tasks", "/api/v1/missions"):
            self._handle_list_missions()
            return

        # Resource endpoints: /api/tasks/{id}/... or /api/v1/missions/{id}/...
        resource_id, sub_resource = self._extract_resource_params(path)
        if resource_id is not None:
            if sub_resource is None:
                self._handle_get_mission(resource_id)
            elif sub_resource == "events":
                self._handle_events_stream(resource_id)
            elif sub_resource == "execution":
                self._handle_get_execution(resource_id)
            elif sub_resource == "timeline":
                self._handle_get_timeline(resource_id)
            elif sub_resource == "evidence":
                self._handle_get_evidence(resource_id, query)
            elif sub_resource == "changes":
                self._handle_get_changes(resource_id)
            elif sub_resource == "tests":
                self._handle_get_tests(resource_id)
            elif sub_resource == "recovery":
                self._handle_get_recovery_detail(resource_id)
            elif sub_resource == "verification":
                self._handle_get_verification(resource_id)
            elif sub_resource == "evaluation":
                self._handle_get_evaluation(resource_id)
            elif sub_resource == "report":
                self._handle_get_report(resource_id)
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Resource '{sub_resource}' not found.")
            return

        # Serve UI HTML / Static files
        if path == "/" or path == "/index.html":
            self._serve_static_file("index.html", "text/html; charset=utf-8")
            return
        elif path.startswith("/static/"):
            rel_file = path[len("/static/"):]
            self._serve_static_file(rel_file)
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def do_POST(self) -> None:
        """Route POST requests to API action endpoints."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Create mission / task submission
        if path in ("/api/tasks", "/api/v1/tasks", "/api/v1/missions"):
            body = self._read_json_body()
            if body is None:
                return
            self._handle_submit_task(body)
            return

        # Resource action endpoints
        resource_id, sub_resource = self._extract_resource_params(path)
        if resource_id is not None:
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return

            if sub_resource == "approve":
                self._handle_approve_task(resource_id, body)
            elif sub_resource == "run":
                self._handle_run_task(resource_id, body)
            elif sub_resource == "advance":
                self._handle_advance_stage(resource_id, body)
            elif sub_resource == "tool":
                self._handle_execute_tool(resource_id, body)
            elif sub_resource == "complete-stage":
                self._handle_complete_stage(resource_id, body)
            elif sub_resource == "report":
                self._handle_generate_report(resource_id, body)
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Action '{sub_resource}' not found.")
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "Action endpoint not found.")

    # -------------------------------------------------------------
    # GET Handlers
    # -------------------------------------------------------------
    def _handle_health(self) -> None:
        resp = HealthResponse(
            status="healthy",
            version=ORION_VERSION,
            uptime_seconds=self.service.uptime_seconds,
            missions_count=self.service.missions_count,
            timestamp=self._current_time_iso(),
        )
        self._send_json(HTTPStatus.OK, resp.to_dict())

    def _handle_list_missions(self) -> None:
        missions = self.service.list_missions()
        self._send_json(
            HTTPStatus.OK,
            {
                "tasks": [m.to_dict() for m in missions],
                "missions": [m.to_dict() for m in missions],
                "total": len(missions),
            },
        )

    def _handle_get_mission(self, mission_id: UUID) -> None:
        mission = self.service.get_mission(mission_id)
        if not mission:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, mission.to_dict())

    def _handle_get_execution(self, mission_id: UUID) -> None:
        exec_info = self.service.get_task_execution(mission_id)
        if not exec_info:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Task '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, exec_info.to_dict())

    def _handle_get_timeline(self, mission_id: UUID) -> None:
        timeline = self.service.get_mission_timeline(mission_id)
        if timeline is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, {"timeline": [e.to_dict() for e in timeline]})

    def _handle_get_evidence(self, mission_id: UUID, query: dict[str, list[str]]) -> None:
        level = query.get("level", [None])[0]
        cat = query.get("category", [None])[0]
        stage = query.get("stage", [None])[0]

        evidence = self.service.get_mission_evidence(
            mission_id, level=level, category=cat, stage=stage
        )
        if evidence is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
            return
        self._send_json(
            HTTPStatus.OK,
            {"evidence": [item.to_dict() for item in evidence], "total": len(evidence)},
        )

    def _handle_get_changes(self, mission_id: UUID) -> None:
        changes = self.service.get_task_changes(mission_id)
        if changes is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Task '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, changes.to_dict())

    def _handle_get_tests(self, mission_id: UUID) -> None:
        tests = self.service.get_task_tests(mission_id)
        if tests is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Task '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, tests.to_dict())

    def _handle_get_recovery_detail(self, mission_id: UUID) -> None:
        recovery = self.service.get_task_recovery_detail(mission_id)
        if recovery is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Task '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, recovery.to_dict())

    def _handle_get_verification(self, mission_id: UUID) -> None:
        verif = self.service.get_mission_verification(mission_id)
        if verif is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, verif.to_dict())

    def _handle_get_evaluation(self, mission_id: UUID) -> None:
        evaluation = self.service.get_mission_evaluation(mission_id)
        if evaluation is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, evaluation.to_dict())

    def _handle_get_report(self, mission_id: UUID) -> None:
        report = self.service.get_mission_report(mission_id)
        if report is None:
            self._send_error_json(
                HTTPStatus.NOT_FOUND,
                f"Report for mission '{mission_id}' not generated yet.",
            )
            return
        self._send_json(HTTPStatus.OK, report)

    def _handle_events_stream(self, mission_id: UUID) -> None:
        """Handle Server-Sent Events (SSE) streaming."""
        try:
            q = self.service.subscribe_events(mission_id)
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Task '{mission_id}' not found.")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._send_cors_headers()
        self.end_headers()

        # Send initial connected message
        init_json = json.dumps({"status": "connected", "mission_id": str(mission_id)})
        try:
            self.wfile.write(f"event: CONNECTED\ndata: {init_json}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.service.unsubscribe_events(mission_id, q)
            return

        try:
            while True:
                try:
                    item = q.get(timeout=1.0)
                    ev_name = item.get("event", "MESSAGE")
                    ev_data = json.dumps(item)
                    payload = f"event: {ev_name}\ndata: {ev_data}\n\n".encode()
                    self.wfile.write(payload)
                    self.wfile.flush()
                    if ev_name in ("TASK_COMPLETED", "TASK_TERMINATED"):
                        break
                except queue.Empty:
                    # Keep-alive comment line
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.service.unsubscribe_events(mission_id, q)

    # -------------------------------------------------------------
    # POST Handlers
    # -------------------------------------------------------------
    def _handle_submit_task(self, body: dict[str, Any]) -> None:
        task_text = body.get("task") or body.get("objective")
        ws_path = body.get("workspace") or body.get("workspace_path")
        exec_mode = body.get("execution_mode", "controlled")
        target_files = tuple(body.get("target_files", ()))
        expected_requirements = tuple(body.get("expected_requirements", ()))
        parameters = dict(body.get("parameters", {}))

        if not task_text or not str(task_text).strip():
            self._send_error_json(
                HTTPStatus.BAD_REQUEST, "Field 'task' (or 'objective') is required."
            )
            return
        if not ws_path or not str(ws_path).strip():
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Field 'workspace' (or 'workspace_path') is required.",
            )
            return

        try:
            req = TaskSubmissionRequest(
                task=str(task_text),
                workspace=str(ws_path),
                execution_mode=str(exec_mode),
                target_files=target_files,
                expected_requirements=expected_requirements,
                parameters=parameters,
            )
            mission = self.service.submit_task(req)
            self._send_json(HTTPStatus.CREATED, mission.to_dict())
        except ValueError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal error: {exc}")

    def _handle_approve_task(self, mission_id: UUID, body: dict[str, Any]) -> None:
        decision = body.get("decision", "approve")
        approver = body.get("approver", "Operator")
        reason = body.get("reason")
        request_id = body.get("request_id")

        try:
            req = TaskApprovalRequest(
                decision=str(decision),
                approver=str(approver),
                reason=str(reason) if reason else None,
                request_id=str(request_id) if request_id else None,
            )
            resp = self.service.approve_task(mission_id, req)
            self._send_json(HTTPStatus.OK, resp.to_dict())
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except ValueError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def _handle_run_task(self, mission_id: UUID, body: dict[str, Any]) -> None:
        auto_approve = bool(body.get("auto_approve", False))
        background = bool(body.get("background", True))

        try:
            self.service.run_pipeline(mission_id, auto_approve=auto_approve, background=background)
            self._send_json(HTTPStatus.ACCEPTED, {
                "status": "executing",
                "mission_id": str(mission_id),
                "message": "Pipeline execution initiated.",
            })
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def _handle_advance_stage(self, mission_id: UUID, body: dict[str, Any]) -> None:
        target_stage = body.get("stage")
        if not target_stage:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'stage' is required.")
            return

        try:
            mission = self.service.advance_stage(mission_id, str(target_stage))
            self._send_json(HTTPStatus.OK, mission.to_dict())
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def _handle_execute_tool(self, mission_id: UUID, body: dict[str, Any]) -> None:
        stage = body.get("stage")
        tool_name = body.get("tool_name")
        arguments = body.get("arguments", {})
        approval_id_raw = body.get("approval_id")

        if not stage or not tool_name:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST, "Fields 'stage' and 'tool_name' are required."
            )
            return

        approval_id = UUID(approval_id_raw) if approval_id_raw else None

        try:
            result = self.service.execute_tool(
                mission_id=mission_id,
                stage=str(stage),
                tool_name=str(tool_name),
                arguments=dict(arguments),
                approval_id=approval_id,
            )
            self._send_json(HTTPStatus.OK, result)
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def _handle_complete_stage(self, mission_id: UUID, body: dict[str, Any]) -> None:
        stage = body.get("stage")
        if not stage:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'stage' is required.")
            return

        try:
            mission = self.service.complete_stage(mission_id, str(stage))
            self._send_json(HTTPStatus.OK, mission.to_dict())
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def _handle_generate_report(self, mission_id: UUID, body: dict[str, Any]) -> None:
        summary = body.get("summary", "")
        try:
            report_data = self.service.generate_final_report(mission_id, summary=str(summary))
            self._send_json(HTTPStatus.OK, report_data)
        except KeyError:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    # -------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------
    def _extract_resource_params(self, path: str) -> tuple[UUID | None, str | None]:
        """Extract resource UUID and sub-resource from supported routing paths."""
        parts = path.strip("/").split("/")

        # Path: /api/tasks/{uuid}[/{sub}]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "tasks":
            try:
                res_id = UUID(parts[2])
                sub = parts[3] if len(parts) > 3 else None
                return res_id, sub
            except ValueError:
                return None, None

        # Path: /api/v1/missions/{uuid}[/{sub}] or /api/v1/tasks/{uuid}[/{sub}]
        is_api_v1 = (
            len(parts) >= 4
            and parts[0] == "api"
            and parts[1] == "v1"
            and parts[2] in ("missions", "tasks")
        )
        if is_api_v1:
            try:
                res_id = UUID(parts[3])
                sub = parts[4] if len(parts) > 4 else None
                return res_id, sub
            except ValueError:
                return None, None

        return None, None

    def _read_json_body(self) -> dict[str, Any] | None:
        """Parse incoming JSON payload."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}

        raw_data = self.rfile.read(content_length)
        try:
            parsed = json.loads(raw_data.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except json.JSONDecodeError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"Malformed JSON: {exc}")
            return None

    def _has_body(self) -> bool:
        return int(self.headers.get("Content-Length", 0)) > 0

    def _send_json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        """Send a JSON HTTP response."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error_json(self, status: HTTPStatus, error: str) -> None:
        """Send a standardized JSON error response."""
        self._send_json(status, {"error": error, "status": status.value})

    def _send_cors_headers(self) -> None:
        """Include standard CORS headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _serve_static_file(self, filename: str, content_type: str | None = None) -> None:
        """Serve static file from the static asset directory."""
        file_path = (STATIC_DIR / filename).resolve()

        # Prevent directory traversal
        try:
            file_path.relative_to(STATIC_DIR)
        except ValueError:
            self._send_error_json(HTTPStatus.FORBIDDEN, "Access forbidden.")
            return

        if not file_path.exists() or file_path.is_dir():
            self._send_error_json(HTTPStatus.NOT_FOUND, f"File '{filename}' not found.")
            return

        mime = content_type or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        content = file_path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _current_time_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr HTTP request logging for quiet operation."""
        pass


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    service: MissionAPIService | None = None,
) -> ThreadingHTTPServer:
    """Create and return an initialized multi-threaded HTTP server."""
    active_service = service or MissionAPIService()

    class CustomBoundHandler(OrionAPIHandler):
        service = active_service

    return ThreadingHTTPServer((host, port), CustomBoundHandler)
