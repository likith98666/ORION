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
    TaskCancellationRequest,
    TaskSubmissionRequest,
)
from orion.api.service import MissionAPIService
from orion.core.security.rate_limiter import TokenBucketRateLimiter

ORION_VERSION = "1.0.0"
STATIC_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"

# Register font MIME types for standards compliance across platforms
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")


class OrionAPIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API, SSE streams, and UI static assets."""

    service: MissionAPIService = MissionAPIService()
    rate_limiter: TokenBucketRateLimiter = TokenBucketRateLimiter()

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self._send_security_headers()
        self.end_headers()

    def _check_rate_limit(self, is_submission: bool = False) -> bool:
        """Check sliding window rate limits. Returns True if allowed, False if exceeded."""
        if not self.service.config.rate_limit_enabled:
            return True

        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        if is_submission:
            key = f"{client_ip}:submission"
            limit = self.service.config.mission_rate_limit_per_minute
        else:
            key = f"{client_ip}:api"
            limit = self.service.config.rate_limit_per_minute

        allowed, retry_after = self.rate_limiter.check_rate_limit(key, limit_per_minute=limit)
        if not allowed:
            retry_secs = max(1, int(retry_after))
            self._send_error_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                "Rate limit exceeded. Please retry later.",
                code="RATE_LIMIT_EXCEEDED",
                extra_headers={"Retry-After": str(retry_secs)},
            )
            return False
        return True

    def _check_auth(self) -> bool:
        """Verify API token authentication if configured or if binding to non-loopback host."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Health/Readiness probes and static UI assets are exempt from token authentication
        if path in (
            "/api/v1/health",
            "/api/health",
            "/api/v1/readiness",
            "/api/readiness",
            "/",
            "/index.html",
            "/favicon.ico",
            "/favicon.svg",
        ) or path.startswith("/static/"):
            return True

        config = self.service.config
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        is_loopback = client_ip in ("127.0.0.1", "::1", "localhost") and config.host in (
            "127.0.0.1",
            "localhost",
            "::1",
        )

        # Token is required if config.api_token is set, OR if binding non-loopback and not testing
        token_required = bool(config.api_token) or (not is_loopback and not config.is_testing)
        if not token_required:
            return True

        expected_token = config.api_token or ""
        auth_header = self.headers.get("Authorization", "")
        api_key_header = self.headers.get("X-API-Key", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif api_key_header:
            token = api_key_header.strip()

        if not token or token != expected_token:
            self._send_error_json(
                HTTPStatus.UNAUTHORIZED,
                "API token authentication required or invalid token provided.",
                code="UNAUTHORIZED",
            )
            return False

        return True

    def do_GET(self) -> None:
        """Route GET requests to API endpoints, event streams, or static assets."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Serve UI HTML / Static files directly (exempt from rate limiting and token auth)
        if path == "/" or path == "/index.html":
            self._serve_static_file("index.html", "text/html; charset=utf-8")
            return
        elif path == "/404.html":
            self._serve_static_file("404.html", "text/html; charset=utf-8")
            return
        elif path in ("/favicon.ico", "/favicon.svg"):
            self._serve_static_file("favicon.svg", "image/svg+xml")
            return
        elif path in ("/app.js", "/static/app.js"):
            self._serve_static_file("app.js", "application/javascript; charset=utf-8")
            return
        elif path in ("/app.css", "/static/app.css"):
            self._serve_static_file("app.css", "text/css; charset=utf-8")
            return
        elif path.startswith("/static/"):
            rel_file = path[len("/static/") :]
            self._serve_static_file(rel_file)
            return

        # Health & Readiness probes are exempt from rate limiting to prevent probe flapping
        if path in ("/api/v1/health", "/api/health"):
            self._handle_health()
            return

        if path in ("/api/v1/readiness", "/api/readiness"):
            self._handle_readiness()
            return

        # Check rate limit for general API requests
        if not self._check_rate_limit(is_submission=False):
            return

        # Check API token authentication
        if not self._check_auth():
            return

        # Collection endpoints: list missions/tasks
        if path in ("/api/tasks", "/api/v1/tasks", "/api/v1/missions"):
            self._handle_list_missions()
            return

        # Benchmark & V6 Evaluation suites endpoints
        if path in (
            "/api/v1/evaluation/benchmarks",
            "/api/evaluation/benchmarks",
            "/api/benchmarks",
            "/api/v1/benchmarks",
        ):
            self._handle_list_benchmarks()
            return

        # V6 Evaluation Runs collection endpoint
        if path in ("/api/v1/evaluation/runs", "/api/evaluation/runs"):
            self._handle_list_evaluation_runs()
            return

        # V6 Evaluation Compare endpoint (GET query)
        if path in ("/api/v1/evaluation/compare", "/api/evaluation/compare"):
            self._handle_compare_evaluation_runs_get(query)
            return

        # V6 Evaluation Run detail endpoints (/runs/{id}, /runs/{id}/metrics, /runs/{id}/failures)
        if path.startswith("/api/v1/evaluation/runs/") or path.startswith("/api/evaluation/runs/"):
            self._handle_get_evaluation_run_detail(path)
            return

        # V3 Repository Index endpoint
        if path in ("/api/repo/index", "/api/v1/repo/index"):
            self._handle_get_repo_index(query)
            return

        # V4 Workforce Roster endpoint
        if path in ("/api/workforce/roster", "/api/v1/workforce/roster"):
            self._handle_get_workforce_roster()
            return

        # V5 Recovery Strategy Metrics endpoint
        if path in ("/api/recovery/metrics", "/api/v1/recovery/metrics"):
            self._handle_get_recovery_metrics()
            return

        # V7 Human-in-the-Loop endpoints
        if path in ("/api/v1/hitl/clarifications", "/api/hitl/clarifications"):
            self._handle_list_clarifications(query)
            return

        if path.startswith("/api/v1/hitl/interventions/") or path.startswith(
            "/api/hitl/interventions/"
        ):
            self._handle_get_hitl_interventions(path)
            return

        if path.startswith("/api/v1/hitl/feedback/") or path.startswith("/api/hitl/feedback/"):
            self._handle_get_hitl_feedback(path)
            return

        # V8 Policy Engine endpoints
        if path in ("/api/v1/policy/rules", "/api/policy/rules"):
            self._handle_list_policy_rules()
            return

        if path in ("/api/v1/policy/decisions", "/api/policy/decisions"):
            self._handle_get_policy_decisions(query)
            return

        # V9 Advanced Observability endpoints
        if path.startswith("/api/v1/observability/spans/") or path.startswith(
            "/api/observability/spans/"
        ):
            self._handle_get_observability_spans(path)
            return

        if path in (
            "/api/v1/observability/metrics/cost",
            "/api/observability/metrics/cost",
        ):
            self._handle_get_cost_metrics(query)
            return

        if path in (
            "/api/v1/observability/bottlenecks",
            "/api/observability/bottlenecks",
        ):
            self._handle_get_system_bottlenecks(query)
            return

        if path in (
            "/api/v1/observability/optimize",
            "/api/observability/optimize",
        ):
            self._handle_get_optimization_recommendations(query)
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
            elif sub_resource == "agents":
                self._handle_get_agents(resource_id)
            elif sub_resource == "graph":
                self._handle_get_graph(resource_id)
            elif sub_resource == "memory":
                self._handle_get_mission_memory(resource_id)
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Resource '{sub_resource}' not found.")
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def do_POST(self) -> None:
        """Route POST requests to API action endpoints."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Check API token authentication
        if not self._check_auth():
            return

        # Check rate limit (stricter limit for mission submission)
        is_sub = path in ("/api/tasks", "/api/v1/tasks", "/api/v1/missions")
        if not self._check_rate_limit(is_submission=is_sub):
            return

        # Create mission / task submission
        if is_sub:
            body = self._read_json_body()
            if body is None:
                return
            self._handle_submit_task(body)
            return

        # Legacy Benchmark run endpoint
        if path in ("/api/benchmarks/run", "/api/v1/benchmarks/run"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_run_benchmark(body)
            return

        # V6 Evaluation run endpoint
        if path in ("/api/v1/evaluation/run", "/api/evaluation/run"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_run_evaluation(body)
            return

        # V6 Evaluation Compare endpoint (POST)
        if path in ("/api/v1/evaluation/compare", "/api/evaluation/compare"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_compare_evaluation_runs_post(body)
            return

        # V2 Mission Plan endpoint
        if path in ("/api/missions/plan", "/api/v1/missions/plan"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_plan_mission(body)
            return

        # V3 Repo Impact endpoint
        if path in ("/api/repo/impact", "/api/v1/repo/impact"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_repo_impact(body)
            return

        # V3 Repo Context endpoint
        if path in ("/api/repo/context", "/api/v1/repo/context"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_repo_context(body)
            return

        # V4 Workforce Review endpoint
        if path in ("/api/workforce/review", "/api/v1/workforce/review"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_workforce_review(body)
            return

        # V4 Workforce Conflict Resolution endpoint
        if path in (
            "/api/workforce/resolve-conflict",
            "/api/v1/workforce/resolve-conflict",
        ):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_workforce_resolve_conflict(body)
            return

        # V5 Recovery Classify endpoint
        if path in ("/api/recovery/classify", "/api/v1/recovery/classify"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_recovery_classify(body)
            return

        # V5 Recovery Simulate endpoint
        if path in ("/api/recovery/simulate", "/api/v1/recovery/simulate"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_recovery_simulate(body)
            return

        # V5 Recovery Plan endpoint
        if path in ("/api/recovery/plan", "/api/v1/recovery/plan"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_recovery_plan(body)
            return

        # V7 Human-in-the-Loop action endpoints
        if path in ("/api/v1/hitl/intervene", "/api/hitl/intervene"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_hitl_intervene(body)
            return

        if path in ("/api/v1/hitl/clarifications/request", "/api/hitl/clarifications/request"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_hitl_request_clarification(body)
            return

        if (
            path.startswith("/api/v1/hitl/clarifications/")
            or path.startswith("/api/hitl/clarifications/")
        ) and path.endswith("/respond"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_hitl_respond_clarification(path, body)
            return

        if path in ("/api/v1/hitl/feedback", "/api/hitl/feedback"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_hitl_feedback(body)
            return

        # V8 Policy Engine endpoints
        if path in ("/api/v1/policy/evaluate", "/api/policy/evaluate"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_evaluate_policy(body)
            return

        if path in ("/api/v1/policy/rules", "/api/policy/rules"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_add_policy_rule(body)
            return

        # V9 Advanced Observability span ingestion endpoint
        if path in ("/api/v1/observability/spans", "/api/observability/spans"):
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return
            self._handle_record_span(body)
            return

        # Resource action endpoints
        resource_id, sub_resource = self._extract_resource_params(path)
        if resource_id is not None:
            body = self._read_json_body() if self._has_body() else {}
            if body is None:
                return

            if sub_resource == "approve":
                self._handle_approve_task(resource_id, body)
            elif sub_resource == "cancel":
                self._handle_cancel_mission(resource_id, body)
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

    def _handle_readiness(self) -> None:
        resp = self.service.check_readiness()
        status_code = HTTPStatus.OK if resp.status == "ready" else HTTPStatus.SERVICE_UNAVAILABLE
        self._send_json(status_code, resp.to_dict())

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

    def _handle_list_benchmarks(self) -> None:
        suites = self.service.list_benchmark_suites()
        self._send_json(HTTPStatus.OK, suites)

    def _handle_run_benchmark(self, body: dict[str, Any]) -> None:
        suite_name = str(body.get("suite", "smoke"))
        try:
            report = self.service.run_benchmark_suite(suite_name=suite_name)
            self._send_json(HTTPStatus.OK, report.to_dict())
        except KeyError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc), code="SUITE_NOT_FOUND")
        except Exception as exc:
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Benchmark error: {exc}",
                code="BENCHMARK_ERROR",
            )

    def _handle_run_evaluation(self, body: dict[str, Any]) -> None:
        suite = str(body.get("suite") or body.get("suite_name") or "smoke")
        auto_repair = bool(body.get("auto_repair", True))
        config = body.get("configuration")
        try:
            exp = self.service.run_evaluation_experiment(
                suite_name=suite,
                configuration=config,
                auto_repair=auto_repair,
            )
            self._send_json(HTTPStatus.CREATED, exp.to_dict())
        except KeyError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc), code="SUITE_NOT_FOUND")
        except Exception as exc:
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"Evaluation experiment error: {exc}",
                code="EVALUATION_ERROR",
            )

    def _handle_list_evaluation_runs(self) -> None:
        runs = self.service.list_evaluation_experiments()
        self._send_json(HTTPStatus.OK, {"runs": runs, "total": len(runs)})

    def _handle_get_evaluation_run_detail(self, path: str) -> None:
        prefix = (
            "/api/v1/evaluation/runs/"
            if path.startswith("/api/v1/evaluation/runs/")
            else "/api/evaluation/runs/"
        )
        subpath = path[len(prefix) :].strip("/")
        parts = subpath.split("/")
        if not parts or not parts[0]:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Experiment ID is required.")
            return

        exp_id = parts[0]
        if len(parts) == 1:
            exp = self.service.get_evaluation_experiment(exp_id)
            if not exp:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Experiment '{exp_id}' not found.")
                return
            self._send_json(HTTPStatus.OK, exp)
        elif len(parts) == 2 and parts[1] == "metrics":
            metrics = self.service.get_evaluation_metrics(exp_id)
            if not metrics:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Experiment '{exp_id}' not found.")
                return
            self._send_json(HTTPStatus.OK, metrics)
        elif len(parts) == 2 and parts[1] == "failures":
            failures = self.service.get_evaluation_failures(exp_id)
            if not failures:
                self._send_error_json(HTTPStatus.NOT_FOUND, f"Experiment '{exp_id}' not found.")
                return
            self._send_json(HTTPStatus.OK, failures)
        else:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Subresource '{parts[1]}' not found.")

    def _handle_compare_evaluation_runs_get(self, query: dict[str, list[str]]) -> None:
        base_id = query.get("base_id", [None])[0]
        target_id = query.get("target_id", [None])[0]
        if not base_id or not target_id:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Query parameters 'base_id' and 'target_id' are required.",
            )
            return
        try:
            comparison = self.service.compare_evaluation_experiments(
                base_id=str(base_id),
                target_id=str(target_id),
            )
            self._send_json(HTTPStatus.OK, comparison)
        except KeyError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_compare_evaluation_runs_post(self, body: dict[str, Any]) -> None:
        base_id = body.get("base_id")
        target_id = body.get("target_id")
        if not base_id or not target_id:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Fields 'base_id' and 'target_id' are required in request body.",
            )
            return
        try:
            comparison = self.service.compare_evaluation_experiments(
                base_id=str(base_id),
                target_id=str(target_id),
            )
            self._send_json(HTTPStatus.OK, comparison)
        except KeyError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    # -------------------------------------------------------------
    # V7 Human-in-the-Loop Handlers
    # -------------------------------------------------------------
    def _handle_list_clarifications(self, query: dict[str, list[str]]) -> None:
        mid_raw = query.get("mission_id", [None])[0]
        status = query.get("status", [None])[0]
        mission_id = UUID(mid_raw) if mid_raw else None
        clarifications = self.service.list_clarifications(mission_id=mission_id, status=status)
        self._send_json(
            HTTPStatus.OK,
            {"clarifications": clarifications, "total": len(clarifications)},
        )

    def _handle_get_hitl_interventions(self, path: str) -> None:
        prefix = (
            "/api/v1/hitl/interventions/"
            if path.startswith("/api/v1/hitl/interventions/")
            else "/api/hitl/interventions/"
        )
        mid_str = path[len(prefix) :].strip("/")
        try:
            mid = UUID(mid_str)
            intervs = self.service.get_mission_interventions(mid)
            self._send_json(HTTPStatus.OK, {"interventions": intervs, "total": len(intervs)})
        except ValueError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"Invalid UUID '{mid_str}'.")

    def _handle_get_hitl_feedback(self, path: str) -> None:
        prefix = (
            "/api/v1/hitl/feedback/"
            if path.startswith("/api/v1/hitl/feedback/")
            else "/api/hitl/feedback/"
        )
        mid_str = path[len(prefix) :].strip("/")
        try:
            mid = UUID(mid_str)
            fb = self.service.get_mission_feedback(mid)
            self._send_json(HTTPStatus.OK, {"feedback": fb, "total": len(fb)})
        except ValueError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"Invalid UUID '{mid_str}'.")

    def _handle_hitl_intervene(self, body: dict[str, Any]) -> None:
        mid_raw = body.get("mission_id")
        action = body.get("action")
        operator = body.get("operator", "Operator")
        reason = body.get("reason", "")
        payload = body.get("payload")
        if not mid_raw or not action:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Fields 'mission_id' and 'action' are required.",
            )
            return
        try:
            res = self.service.intervene_mission(
                mission_id=UUID(str(mid_raw)),
                action=str(action),
                operator=str(operator),
                reason=str(reason),
                payload=dict(payload) if isinstance(payload, dict) else None,
            )
            self._send_json(HTTPStatus.OK, res)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_hitl_request_clarification(self, body: dict[str, Any]) -> None:
        mid_raw = body.get("mission_id")
        tid_raw = body.get("task_id")
        question = body.get("question")
        context = body.get("context", "")
        options = tuple(body.get("options", ()))
        default_choice = body.get("default_choice")
        if not mid_raw or not tid_raw or not question:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Fields 'mission_id', 'task_id', and 'question' are required.",
            )
            return
        try:
            req = self.service.request_clarification(
                mission_id=UUID(str(mid_raw)),
                task_id=UUID(str(tid_raw)),
                question=str(question),
                context=str(context),
                options=options,
                default_choice=str(default_choice) if default_choice else None,
            )
            self._send_json(HTTPStatus.CREATED, req)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_hitl_respond_clarification(self, path: str, body: dict[str, Any]) -> None:
        prefix = (
            "/api/v1/hitl/clarifications/"
            if path.startswith("/api/v1/hitl/clarifications/")
            else "/api/hitl/clarifications/"
        )
        req_id_str = path[len(prefix) : -len("/respond")].strip("/")
        resp_text = body.get("response") or body.get("answer")
        operator = body.get("operator", "Operator")
        if not resp_text:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Field 'response' (or 'answer') is required.",
            )
            return
        try:
            res = self.service.respond_clarification(
                request_id=UUID(req_id_str),
                response_text=str(resp_text),
                operator=str(operator),
            )
            self._send_json(HTTPStatus.OK, res)
        except KeyError as exc:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_hitl_feedback(self, body: dict[str, Any]) -> None:
        mid_raw = body.get("mission_id")
        operator = body.get("operator", "Operator")
        rating = body.get("rating")
        comments = body.get("comments", "")
        corrections = tuple(body.get("corrections", ()))
        if not mid_raw or rating is None:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Fields 'mission_id' and 'rating' are required.",
            )
            return
        try:
            fb = self.service.submit_operator_feedback(
                mission_id=UUID(str(mid_raw)),
                operator=str(operator),
                rating=int(rating),
                comments=str(comments),
                corrections=corrections,
            )
            self._send_json(HTTPStatus.CREATED, fb)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    # -------------------------------------------------------------
    # V8 Policy Engine Handlers
    # -------------------------------------------------------------
    def _handle_list_policy_rules(self) -> None:
        rules = self.service.list_policy_rules()
        self._send_json(HTTPStatus.OK, {"rules": rules, "total": len(rules)})

    def _handle_get_policy_decisions(self, query: dict[str, list[str]]) -> None:
        limit_str = query.get("limit", ["100"])[0]
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 100
        decisions = self.service.get_policy_decisions(limit=limit)
        self._send_json(HTTPStatus.OK, {"decisions": decisions, "total": len(decisions)})

    def _handle_evaluate_policy(self, body: dict[str, Any]) -> None:
        subject = body.get("subject")
        action = body.get("action")
        resource = body.get("resource")
        if not subject or not action or not resource:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Fields 'subject', 'action', and 'resource' are required.",
            )
            return

        try:
            decision = self.service.evaluate_policy(
                subject=str(subject),
                action=str(action),
                resource=str(resource),
                tenant_id=str(body.get("tenant_id", "default")),
                environment=str(body.get("environment", "sandbox")),
                risk_tier=str(body.get("risk_tier", "low")),
                parameters=body.get("parameters"),
                metadata=body.get("metadata"),
            )
            self._send_json(HTTPStatus.OK, decision)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_add_policy_rule(self, body: dict[str, Any]) -> None:
        if not body.get("rule_id") or not body.get("name") or not body.get("effect"):
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Fields 'rule_id', 'name', and 'effect' are required.",
            )
            return

        try:
            res = self.service.add_policy_rule(body)
            self._send_json(HTTPStatus.CREATED, res)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    # -------------------------------------------------------------
    # V9 Advanced Observability Handlers
    # -------------------------------------------------------------
    def _handle_get_observability_spans(self, path: str) -> None:
        prefix = (
            "/api/v1/observability/spans/"
            if path.startswith("/api/v1/observability/spans/")
            else "/api/observability/spans/"
        )
        mid_str = path[len(prefix) :].strip("/")
        try:
            mid = UUID(mid_str)
            spans = self.service.get_mission_spans(mid)
            self._send_json(HTTPStatus.OK, {"spans": spans, "total": len(spans)})
        except ValueError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, f"Invalid UUID '{mid_str}'.")

    def _handle_get_cost_metrics(self, query: dict[str, list[str]]) -> None:
        mid_raw = query.get("mission_id", [None])[0]
        mission_id = UUID(mid_raw) if mid_raw else None
        metrics = self.service.get_cost_metrics(mission_id=mission_id)
        self._send_json(HTTPStatus.OK, metrics)

    def _handle_get_system_bottlenecks(self, query: dict[str, list[str]]) -> None:
        mid_raw = query.get("mission_id", [None])[0]
        top_n_raw = query.get("top_n", ["5"])[0]
        mission_id = UUID(mid_raw) if mid_raw else None
        try:
            top_n = int(top_n_raw)
        except ValueError:
            top_n = 5
        bottlenecks = self.service.get_system_bottlenecks(mission_id=mission_id, top_n=top_n)
        self._send_json(HTTPStatus.OK, bottlenecks)

    def _handle_get_optimization_recommendations(self, query: dict[str, list[str]]) -> None:
        mid_raw = query.get("mission_id", [None])[0]
        mission_id = UUID(mid_raw) if mid_raw else None
        insights = self.service.generate_optimization_recommendations(mission_id=mission_id)
        self._send_json(HTTPStatus.OK, {"recommendations": insights, "total": len(insights)})

    def _handle_record_span(self, body: dict[str, Any]) -> None:
        name = body.get("name")
        if not name:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'name' is required.")
            return

        trace_id_raw = body.get("trace_id")
        parent_id_raw = body.get("parent_span_id")
        trace_id = UUID(str(trace_id_raw)) if trace_id_raw else None
        parent_id = UUID(str(parent_id_raw)) if parent_id_raw else None

        try:
            span = self.service.record_telemetry_span(
                name=str(name),
                trace_id=trace_id,
                parent_span_id=parent_id,
                kind=str(body.get("kind", "internal")),
                status=str(body.get("status", "ok")),
                duration_ms=float(body.get("duration_ms", 0.0)),
                attributes=body.get("attributes"),
            )
            self._send_json(HTTPStatus.CREATED, span)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_get_repo_index(self, query: dict[str, list[str]]) -> None:
        ws_list = query.get("workspace", [None])
        ws_path = ws_list[0] if ws_list else None
        try:
            data = self.service.get_repository_index(ws_path)
            self._send_json(HTTPStatus.OK, data)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_repo_impact(self, body: dict[str, Any]) -> None:
        target_file = body.get("target_file")
        if not target_file:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'target_file' is required.")
            return
        ws_path = body.get("workspace")
        try:
            report = self.service.analyze_repository_impact(
                target_file=str(target_file),
                workspace_path=str(ws_path) if ws_path else None,
            )
            self._send_json(HTTPStatus.OK, report)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_repo_context(self, body: dict[str, Any]) -> None:
        target_file = body.get("target_file")
        if not target_file:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'target_file' is required.")
            return
        ws_path = body.get("workspace")
        try:
            ctx = self.service.get_repository_context(
                target_file=str(target_file),
                workspace_path=str(ws_path) if ws_path else None,
            )
            self._send_json(HTTPStatus.OK, ctx)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_get_workforce_roster(self) -> None:
        roster = self.service.get_workforce_roster()
        self._send_json(HTTPStatus.OK, {"roster": roster, "total": len(roster)})

    def _handle_workforce_review(self, body: dict[str, Any]) -> None:
        try:
            verdict = self.service.review_agent_proposal(body)
            self._send_json(HTTPStatus.OK, verdict)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_workforce_resolve_conflict(self, body: dict[str, Any]) -> None:
        proposals = body.get("proposals", [])
        if not isinstance(proposals, list) or not proposals:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Field 'proposals' must be a non-empty list.",
            )
            return
        try:
            resolution = self.service.resolve_competing_proposals(proposals)
            self._send_json(HTTPStatus.OK, resolution)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_get_recovery_metrics(self) -> None:
        metrics = self.service.get_recovery_strategy_metrics()
        self._send_json(HTTPStatus.OK, {"metrics": metrics})

    def _handle_recovery_classify(self, body: dict[str, Any]) -> None:
        output_text = body.get("output_text") or body.get("error_text")
        if not output_text:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST, "Field 'output_text' (or 'error_text') is required."
            )
            return
        target_file = body.get("target_file")
        exit_code = body.get("exit_code")
        try:
            diag = self.service.classify_failure(
                output_text=str(output_text),
                target_file=str(target_file) if target_file else None,
                exit_code=int(exit_code) if exit_code is not None else None,
            )
            self._send_json(HTTPStatus.OK, diag)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_recovery_simulate(self, body: dict[str, Any]) -> None:
        action_type = body.get("action_type")
        if not action_type:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'action_type' is required.")
            return
        target_files = body.get("target_files", [])
        est_duration = float(body.get("estimated_duration_seconds", 5.0))
        budget = float(body.get("max_duration_budget", 60.0))
        try:
            result = self.service.simulate_recovery_action(
                action_type=str(action_type),
                target_files=list(target_files),
                estimated_duration_seconds=est_duration,
                max_duration_budget=budget,
            )
            self._send_json(HTTPStatus.OK, result)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_recovery_plan(self, body: dict[str, Any]) -> None:
        output_text = body.get("output_text") or body.get("error_text")
        if not output_text:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST, "Field 'output_text' (or 'error_text') is required."
            )
            return
        target_files = body.get("target_files")
        attempt_number = int(body.get("attempt_number", 1))
        try:
            plan = self.service.plan_adaptive_recovery(
                output_text=str(output_text),
                target_files=list(target_files) if target_files else None,
                attempt_number=attempt_number,
            )
            self._send_json(HTTPStatus.OK, plan)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

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

    def _handle_get_agents(self, mission_id: UUID) -> None:
        roster = self.service.get_mission_agents(mission_id)
        if roster is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
            return
        self._send_json(HTTPStatus.OK, roster.to_dict())

    def _handle_get_graph(self, mission_id: UUID) -> None:
        graph = self.service.get_execution_graph(mission_id)
        if graph is not None:
            self._send_json(HTTPStatus.OK, graph.to_dict())
            return
        v2_graph = self.service.get_mission_graph(mission_id)
        if v2_graph is not None:
            self._send_json(HTTPStatus.OK, v2_graph)
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")

    def _handle_get_mission_memory(self, mission_id: UUID) -> None:
        mem = self.service.get_mission_memory(mission_id)
        if mem is None:
            self._send_error_json(
                HTTPStatus.NOT_FOUND, f"Mission memory for '{mission_id}' not found."
            )
            return
        self._send_json(HTTPStatus.OK, mem)

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
        self._send_security_headers()
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
                    if ev_name in ("TASK_COMPLETED", "TASK_TERMINATED", "SYSTEM_SHUTDOWN"):
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

    def _handle_cancel_mission(self, mission_id: UUID, body: dict[str, Any]) -> None:
        reason = body.get("reason", "Operator requested cancellation")
        cancelled_by = body.get("cancelled_by", "Operator")
        try:
            req = TaskCancellationRequest(reason=str(reason), cancelled_by=str(cancelled_by))
            resp = self.service.cancel_mission(mission_id, req)
            self._send_json(HTTPStatus.OK, resp.to_dict())
        except KeyError:
            # Check if it's a V2 mission plan
            cancelled_v2 = self.service.cancel_mission_plan(mission_id, reason=str(reason))
            if cancelled_v2:
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "mission_id": str(mission_id),
                        "status": "cancelled",
                        "reason": str(reason),
                    },
                )
                return
            self._send_error_json(HTTPStatus.NOT_FOUND, f"Mission '{mission_id}' not found.")
        except Exception as exc:
            self._send_error_json(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))

    def _handle_plan_mission(self, body: dict[str, Any]) -> None:
        objective = body.get("objective") or body.get("task")
        if not objective or not str(objective).strip():
            self._send_error_json(HTTPStatus.BAD_REQUEST, "Field 'objective' is required.")
            return

        mid_raw = body.get("mission_id")
        mission_id = UUID(str(mid_raw)) if mid_raw else None
        max_duration = float(body.get("max_duration_seconds", 300.0))

        try:
            plan = self.service.plan_mission(
                objective=str(objective),
                mission_id=mission_id,
                max_duration_seconds=max_duration,
            )
            self._send_json(HTTPStatus.CREATED, plan)
        except Exception as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_run_task(self, mission_id: UUID, body: dict[str, Any]) -> None:
        auto_approve = bool(body.get("auto_approve", False))
        background = bool(body.get("background", True))

        try:
            self.service.run_pipeline(mission_id, auto_approve=auto_approve, background=background)
            self._send_json(
                HTTPStatus.ACCEPTED,
                {
                    "status": "executing",
                    "mission_id": str(mission_id),
                    "message": "Pipeline execution initiated.",
                },
            )
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
        """Parse incoming JSON payload with size boundary enforcement."""
        content_length_header = self.headers.get("Content-Length")
        if not content_length_header:
            return {}

        try:
            content_length = int(content_length_header)
        except ValueError:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Invalid Content-Length header.",
                code="INVALID_CONTENT_LENGTH",
            )
            return None

        if content_length < 0:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "Content-Length cannot be negative.",
                code="INVALID_CONTENT_LENGTH",
            )
            return None

        if content_length == 0:
            return {}

        # Enforce maximum body size cap
        max_bytes = self.service.config.max_request_body_bytes
        if content_length > max_bytes:
            try:
                self.rfile.read(min(content_length, 65536))
            except Exception:
                pass
            self._send_error_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"Request payload ({content_length} bytes) exceeds limit of {max_bytes} bytes.",
                code="PAYLOAD_TOO_LARGE",
            )
            return None

        # Strict Content-Type enforcement for non-empty JSON bodies
        content_type = self.headers.get("Content-Type", "")
        if content_type and not (
            content_type.lower().startswith("application/json") or "json" in content_type.lower()
        ):
            try:
                self.rfile.read(min(content_length, 65536))
            except Exception:
                pass
            self._send_error_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                f"Unsupported Content-Type '{content_type}'. Must be 'application/json'.",
                code="UNSUPPORTED_MEDIA_TYPE",
            )
            return None

        raw_data = self.rfile.read(content_length)
        try:
            parsed = json.loads(raw_data.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except json.JSONDecodeError as exc:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                f"Malformed JSON: {exc}",
                code="MALFORMED_JSON",
            )
            return None

    def _has_body(self) -> bool:
        return int(self.headers.get("Content-Length", 0)) > 0

    def _send_json(
        self,
        status: HTTPStatus,
        data: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Send a JSON HTTP response with security and cache headers."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self._send_cors_headers()
        self._send_security_headers()
        if extra_headers:
            for header_name, header_val in extra_headers.items():
                self.send_header(header_name, header_val)
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error_json(
        self,
        status: HTTPStatus,
        error: str,
        code: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """Send a standardized JSON error response."""
        self._send_json(
            status,
            {
                "error": error,
                "code": code or status.name,
                "status": status.value,
                "timestamp": self._current_time_iso(),
            },
            extra_headers=extra_headers,
        )

    def _send_cors_headers(self) -> None:
        """Include standard CORS headers matching configuration."""
        has_hdrs = hasattr(self, "headers") and self.headers is not None
        req_origin = self.headers.get("Origin", "") if has_hdrs else ""
        allowed_origins = getattr(self.service.config, "cors_allowed_origins", ("*",))

        if "*" in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", req_origin if req_origin else "*")
        elif req_origin and (
            req_origin in allowed_origins
            or any(
                o.startswith("*.") and req_origin.endswith(o[1:])
                for o in allowed_origins
                if "." in o
            )
        ):
            self.send_header("Access-Control-Allow-Origin", req_origin)
            self.send_header("Vary", "Origin")
        elif allowed_origins:
            self.send_header("Access-Control-Allow-Origin", allowed_origins[0])
            self.send_header("Vary", "Origin")

        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_security_headers(self) -> None:
        """Send production HTTP security headers."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        self.send_header("Content-Security-Policy", csp)

    def _serve_static_file(self, filename: str, content_type: str | None = None) -> None:
        """Serve static file from the static asset directory."""
        from urllib.parse import unquote

        decoded_name = unquote(filename).lstrip("/\\")
        file_path = (STATIC_DIR / decoded_name).resolve()

        # Prevent directory traversal
        try:
            file_path.relative_to(STATIC_DIR)
        except ValueError:
            self._send_error_json(HTTPStatus.FORBIDDEN, "Access forbidden.", code="FORBIDDEN_PATH")
            return

        if not file_path.exists() or file_path.is_dir():
            self._send_error_json(
                HTTPStatus.NOT_FOUND, f"File '{filename}' not found.", code="NOT_FOUND"
            )
            return

        if file_path.suffix.lower() == ".woff2":
            mime = "font/woff2"
        elif file_path.suffix.lower() == ".woff":
            mime = "font/woff"
        else:
            mime = (
                content_type
                or mimetypes.guess_type(str(file_path))[0]
                or "application/octet-stream"
            )

        content = file_path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self._send_cors_headers()
        self._send_security_headers()
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
    rate_limiter: TokenBucketRateLimiter | None = None,
) -> ThreadingHTTPServer:
    """Create and return an initialized multi-threaded HTTP server."""
    active_service = service or MissionAPIService()
    active_rate_limiter = rate_limiter or TokenBucketRateLimiter(
        default_limit_per_minute=active_service.config.rate_limit_per_minute
    )

    class CustomBoundHandler(OrionAPIHandler):
        service = active_service
        rate_limiter = active_rate_limiter

    return ThreadingHTTPServer((host, port), CustomBoundHandler)
