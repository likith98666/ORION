"""ORION Production CLI and Server Entrypoint.

Starts the ORION Mission Command Center and REST API server.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

from orion import __version__
from orion.api.server import create_server
from orion.api.service import MissionAPIService

BANNER = f"""
======================================================================
  ORION — Autonomous AI Execution Platform v{__version__}
  Flagship: Autonomous Software Engineering
======================================================================
  [Core Subsystems Online]
  * Workspace Isolation Engine (Canonical paths & boundary enforcement)
  * Controlled Repository Tool Registry (Read/Write/Test/Diff)
  * 7-Stage Deterministic SWE Graph (No uncontrolled loops)
  * VerificationEngine & RecoveryCoordinator
  * EvidenceLedger & Deterministic SWEEvaluator
  * Mission Command Center & Product REST API
======================================================================
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="orion",
        description="ORION Autonomous AI Execution Platform — Mission Command Center",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("ORION_HOST", "127.0.0.1"),
        help="Host address to bind HTTP server (default: 127.0.0.1, use 0.0.0.0 for Docker)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ORION_PORT", "8000")),
        help="Port number to listen on (default: 8000)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.environ.get("ORION_WORKSPACE", ".")).resolve(),
        help="Initial default workspace root path",
    )
    return parser.parse_args(argv)


def run_server(host: str, port: int, workspace: Path) -> int:
    """Run the HTTP server until interrupted."""
    service = MissionAPIService(default_workspace_path=workspace)
    server = create_server(host=host, port=port, service=service)

    # Print startup telemetry banner
    print(BANNER)
    print(f"  HTTP Server : http://{host}:{port}")
    print(f"  Workspace   : {workspace.resolve()}")
    print(f"  Health Check: http://{host}:{port}/api/v1/health")
    print(f"  UI Console  : http://{host}:{port}/")
    print("======================================================================")
    print("  Press Ctrl+C to terminate cleanly.\n")

    def _shutdown_handler(signum, frame):
        print("\n[ORION] Received termination signal. Shutting down gracefully...")
        server.shutdown()
        server.server_close()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _shutdown_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _shutdown_handler)
    except (ValueError, AttributeError):
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = args.workspace.resolve()
    if not workspace.exists():
        print(f"[ORION] Error: Workspace path does not exist: {workspace}", file=sys.stderr)
        return 1
    return run_server(host=args.host, port=args.port, workspace=workspace)


if __name__ == "__main__":
    sys.exit(main())
