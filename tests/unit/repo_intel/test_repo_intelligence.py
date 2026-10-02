"""Unit and integration test suite for ORION V3 Deep Repository Intelligence."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from orion.api.server import create_server
from orion.api.service import MissionAPIService
from orion.core.repo_intel.detector import ArchitectureDetector
from orion.core.repo_intel.graph import RepoCodeGraph
from orion.core.repo_intel.impact import ChangeImpactAnalyzer
from orion.core.repo_intel.indexer import ASTSymbolIndexer
from orion.core.repo_intel.models import SymbolType
from orion.core.repo_intel.optimizer import ContextOptimizer


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Create a structured multi-module repository with source and test files."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Config
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n[tool.pytest.ini_options]\naddopts = "-q"\n',
        encoding="utf-8",
    )

    # Core module: utils.py
    (src_dir / "utils.py").write_text(
        '"""Utility helpers."""\n\n'
        "def sanitize_input(raw: str) -> str:\n"
        '    """Strip unwanted characters."""\n'
        "    return raw.strip()\n\n"
        "def format_output(val: str) -> str:\n"
        "    return f'out: {val}'\n",
        encoding="utf-8",
    )

    # Service module: auth.py (imports utils)
    (src_dir / "auth.py").write_text(
        '"""Authentication service."""\n\n'
        "from src.utils import sanitize_input\n\n"
        "class AuthService:\n"
        '    """Manages credentials and sessions."""\n'
        "    def __init__(self, realm: str = 'default'):\n"
        "        self.realm = realm\n\n"
        "    def login(self, username: str) -> bool:\n"
        '        """Authenticate user."""\n'
        "        clean = sanitize_input(username)\n"
        "        return bool(clean)\n",
        encoding="utf-8",
    )

    # API module: api.py (imports auth)
    (src_dir / "api.py").write_text(
        "from src.auth import AuthService\n\n"
        "def handle_login(req_user: str) -> dict:\n"
        "    svc = AuthService()\n"
        "    return {'ok': svc.login(req_user)}\n",
        encoding="utf-8",
    )

    # Test module: test_auth.py (imports auth)
    (tests_dir / "test_auth.py").write_text(
        "from src.auth import AuthService\n\n"
        "def test_auth_login():\n"
        "    svc = AuthService()\n"
        "    assert svc.login('  alice  ') is True\n",
        encoding="utf-8",
    )

    # Test module: test_utils.py (imports utils)
    (tests_dir / "test_utils.py").write_text(
        "from src.utils import sanitize_input\n\n"
        "def test_sanitize():\n"
        "    assert sanitize_input('  x ') == 'x'\n",
        encoding="utf-8",
    )

    return tmp_path


def test_ast_symbol_indexer(sample_workspace: Path):
    """Verify ASTSymbolIndexer extracts classes, methods, functions, and docstrings."""
    indexer = ASTSymbolIndexer(sample_workspace)
    modules = indexer.index_repository()

    assert "src/utils.py" in modules
    assert "src/auth.py" in modules
    assert "tests/test_auth.py" in modules

    auth_mod = modules["src/auth.py"]
    assert auth_mod.module_name == "src.auth"
    assert "AuthService" in auth_mod.symbols
    assert auth_mod.symbols["AuthService"].symbol_type == SymbolType.CLASS
    assert "AuthService.login" in auth_mod.symbols
    assert auth_mod.symbols["AuthService.login"].symbol_type == SymbolType.METHOD
    assert auth_mod.symbols["AuthService.login"].docstring == "Authenticate user."


def test_ast_indexer_syntax_error_resilience(tmp_path: Path):
    """Verify indexer gracefully records syntax errors without aborting."""
    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def broken_syntax(:\n   pass", encoding="utf-8")

    indexer = ASTSymbolIndexer(tmp_path)
    modules = indexer.index_repository()

    assert "broken.py" in modules
    assert "<SyntaxError>" in modules["broken.py"].symbols


def test_repo_code_graph_and_test_mapping(sample_workspace: Path):
    """Verify RepoCodeGraph resolves dependencies, dependents, and test mappings."""
    graph = RepoCodeGraph.build_from_workspace(sample_workspace)

    # Check dependencies: auth.py depends on utils.py
    deps = graph.get_dependencies("src/auth.py")
    assert "src/utils.py" in deps

    # Check dependents: utils.py is depended on by auth.py
    dependents = graph.get_dependents("src/utils.py", recursive=False)
    assert "src/auth.py" in dependents

    # Transitive dependents: utils.py -> auth.py -> api.py
    transitive = graph.get_dependents("src/utils.py", recursive=True)
    assert "src/auth.py" in transitive
    assert "src/api.py" in transitive

    # Test mapping
    auth_tests = graph.get_tests_for_file("src/auth.py")
    assert "tests/test_auth.py" in auth_tests

    # Symbol lookup
    defs = graph.find_symbol_definitions("sanitize_input")
    assert len(defs) == 1
    assert defs[0].file_path == "src/utils.py"


def test_change_impact_analyzer(sample_workspace: Path):
    """Verify ChangeImpactAnalyzer computes blast radius and risk scoring."""
    graph = RepoCodeGraph.build_from_workspace(sample_workspace)
    analyzer = ChangeImpactAnalyzer(graph)

    # Modifying utils.py impacts auth.py, api.py, test_auth.py, and test_utils.py
    report = analyzer.analyze_change("src/utils.py", modified_symbols=["sanitize_input"])
    assert report.target_file == "src/utils.py"
    assert "src/auth.py" in report.directly_affected_modules
    assert "src/api.py" in report.transitively_affected_modules
    assert "tests/test_utils.py" in report.impacted_tests
    assert "tests/test_auth.py" in report.impacted_tests
    assert report.regression_risk in ("medium", "high")


def test_architecture_detector(sample_workspace: Path):
    """Verify ArchitectureDetector detects pytest, pyproject.toml, and source roots."""
    detector = ArchitectureDetector(sample_workspace)
    profile = detector.detect_profile(total_files=5, total_symbols=10)

    assert profile.framework == "python-pyproject"
    assert profile.test_runner == "pytest"
    assert "pyproject.toml" in profile.config_files
    assert "src" in profile.source_roots


def test_context_optimizer(sample_workspace: Path):
    """Verify ContextOptimizer generates bounded, token-efficient context snippets."""
    graph = RepoCodeGraph.build_from_workspace(sample_workspace)
    optimizer = ContextOptimizer(graph)

    ctx = optimizer.build_context("src/auth.py")
    assert ctx.target_path == "src/auth.py"
    assert any(s.name == "AuthService" for s in ctx.symbols)
    assert "tests/test_auth.py" in ctx.relevant_tests
    assert ctx.token_estimate > 0
    assert "class AuthService" in ctx.context_snippet
    assert "def login" in ctx.context_snippet


@pytest.fixture
def repo_server(sample_workspace: Path):
    """Spin up server with sample workspace as default."""
    service = MissionAPIService(default_workspace_path=sample_workspace)
    server = create_server(host="127.0.0.1", port=0, service=service)
    server_port = server.server_address[1]

    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server_port}"
    yield base_url, service, sample_workspace
    server.shutdown()
    server.server_close()


def test_api_v3_repo_endpoints(repo_server):
    """Test GET /api/v1/repo/index, POST /api/v1/repo/impact, and POST /api/v1/repo/context."""
    base_url, _, _ = repo_server

    # 1. GET /api/v1/repo/index
    with urlopen(f"{base_url}/api/v1/repo/index") as resp:
        assert resp.status == HTTPStatus.OK
        index_data = json.loads(resp.read().decode("utf-8"))
        assert "total_modules" in index_data
        assert "profile" in index_data
        assert index_data["profile"]["framework"] == "python-pyproject"

    # 2. POST /api/v1/repo/impact
    impact_payload = json.dumps({"target_file": "src/utils.py"}).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/repo/impact",
        data=impact_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        impact_data = json.loads(resp.read().decode("utf-8"))
        assert impact_data["target_file"] == "src/utils.py"
        assert "src/auth.py" in impact_data["directly_affected_modules"]

    # 3. POST /api/v1/repo/context
    context_payload = json.dumps({"target_file": "src/auth.py"}).encode("utf-8")
    req = Request(
        f"{base_url}/api/v1/repo/context",
        data=context_payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as resp:
        assert resp.status == HTTPStatus.OK
        ctx_data = json.loads(resp.read().decode("utf-8"))
        assert ctx_data["target_path"] == "src/auth.py"
        assert ctx_data["token_estimate"] > 0
        assert "AuthService" in ctx_data["context_snippet"]
