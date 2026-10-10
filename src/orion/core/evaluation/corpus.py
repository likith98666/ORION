"""Standardized, curated SWE benchmark task corpus for ORION evaluation."""

from __future__ import annotations

from orion.core.evaluation.models import (
    BenchmarkCategory,
    BenchmarkDifficulty,
    BenchmarkTask,
)

# ---------------------------------------------------------------------------
# Task 1: Bug Fix — Off-by-one arithmetic calculation
# ---------------------------------------------------------------------------
TASK_BUG_FIX_CALCULATOR = BenchmarkTask(
    task_id="SWE-BUG-001",
    name="Fix Calculator Addition Offset",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement=(
        "The add function in calc.py subtracts instead of adding. "
        "Fix it so that add(a, b) == a + b."
    ),
    workspace_files={
        "src/calc.py": (
            "def add(a: int, b: int) -> int:\n"
            "    return a - b\n\n"
            "def multiply(a: int, b: int) -> int:\n"
            "    return a * b\n"
        ),
    },
    test_files={
        "tests/test_calc.py": (
            "from src.calc import add, multiply\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
            "    assert add(-1, 1) == 0\n\n"
            "def test_multiply():\n"
            "    assert multiply(3, 4) == 12\n"
        ),
    },
    target_files=("src/calc.py",),
    timeout_seconds=30.0,
    failure_category="assertion_failure",
)

# ---------------------------------------------------------------------------
# Task 2: Bug Fix — Key-value configuration parser
# ---------------------------------------------------------------------------
TASK_BUG_FIX_CONFIG_PARSER = BenchmarkTask(
    task_id="SWE-BUG-002",
    name="Fix Config Parser Key Stripping",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.MEDIUM,
    problem_statement="parse_config in parser.py fails to strip whitespace from keys and values.",
    workspace_files={
        "src/parser.py": (
            "def parse_config(raw: str) -> dict[str, str]:\n"
            "    result = {}\n"
            "    for line in raw.strip().splitlines():\n"
            "        if '=' in line:\n"
            "            k, v = line.split('=', 1)\n"
            "            result[k] = v\n"
            "    return result\n"
        ),
    },
    test_files={
        "tests/test_parser.py": (
            "from src.parser import parse_config\n\n"
            "def test_parse_clean():\n"
            "    cfg = parse_config('host = 127.0.0.1\\nport = 8000')\n"
            "    assert cfg == {'host': '127.0.0.1', 'port': '8000'}\n"
        ),
    },
    target_files=("src/parser.py",),
    timeout_seconds=30.0,
    failure_category="assertion_failure",
)

# ---------------------------------------------------------------------------
# Task 3: Regression Fix — Cache TTL Invalidation
# ---------------------------------------------------------------------------
TASK_REGRESSION_CACHE = BenchmarkTask(
    task_id="SWE-REG-001",
    name="Repair Cache Expiration Check",
    category=BenchmarkCategory.REGRESSION_FIX,
    difficulty=BenchmarkDifficulty.MEDIUM,
    problem_statement=(
        "SimpleCache in cache.py incorrectly invalidates items immediately upon creation."
    ),
    workspace_files={
        "src/cache.py": (
            "import time\n\n"
            "class SimpleCache:\n"
            "    def __init__(self, ttl: float = 60.0):\n"
            "        self.ttl = ttl\n"
            "        self._store = {}\n\n"
            "    def set(self, k: str, v: str) -> None:\n"
            "        self._store[k] = (v, time.time() - self.ttl - 1)\n\n"
            "    def get(self, k: str) -> str | None:\n"
            "        if k not in self._store:\n"
            "            return None\n"
            "        val, ts = self._store[k]\n"
            "        if time.time() - ts > self.ttl:\n"
            "            return None\n"
            "        return val\n"
        ),
    },
    test_files={
        "tests/test_cache.py": (
            "from src.cache import SimpleCache\n\n"
            "def test_cache_retrieval():\n"
            "    c = SimpleCache(ttl=10.0)\n"
            "    c.set('session', 'xyz123')\n"
            "    assert c.get('session') == 'xyz123'\n"
        ),
    },
    target_files=("src/cache.py",),
    timeout_seconds=30.0,
    failure_category="test_regression",
)

# ---------------------------------------------------------------------------
# Task 4: Syntax / AST Validation — Data Model Validation
# ---------------------------------------------------------------------------
TASK_SYNTAX_VALIDATOR = BenchmarkTask(
    task_id="SWE-SYN-001",
    name="Resolve Validator Syntax AST Error",
    category=BenchmarkCategory.SYNTAX_VALIDATION,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement="validator.py has a syntax error in validate_email regex definition.",
    workspace_files={
        "src/validator.py": (
            "def validate_email(email: str) -> bool:\n"
            "    if not email or '@' not in email\n"
            "        return False\n"
            "    return True\n"
        ),
    },
    test_files={
        "tests/test_validator.py": (
            "from src.validator import validate_email\n\n"
            "def test_email():\n"
            "    assert validate_email('user@orion.ai') is True\n"
            "    assert validate_email('invalid') is False\n"
        ),
    },
    target_files=("src/validator.py",),
    timeout_seconds=30.0,
    failure_category="syntax_failure",
)

# ---------------------------------------------------------------------------
# Task 5: Type Failure — Formatting Incompatible Types
# ---------------------------------------------------------------------------
TASK_TYPE_FORMATTER = BenchmarkTask(
    task_id="SWE-TYP-001",
    name="Fix Formatter Type Incompatibility",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement="format_badge in formatter.py raises TypeError by concatenating int to str.",
    workspace_files={
        "src/formatter.py": (
            "def format_badge(label: str, count: int) -> str:\n    return label + ': ' + count\n"
        ),
    },
    test_files={
        "tests/test_formatter.py": (
            "from src.formatter import format_badge\n\n"
            "def test_badge():\n"
            "    assert format_badge('Issues', 5) == 'Issues: 5'\n"
        ),
    },
    target_files=("src/formatter.py",),
    timeout_seconds=30.0,
    failure_category="type_failure",
)

# ---------------------------------------------------------------------------
# Task 6: Import Failure — Unresolved Module Import
# ---------------------------------------------------------------------------
TASK_IMPORT_RESOLVER = BenchmarkTask(
    task_id="SWE-IMP-001",
    name="Fix Unresolved Module Import",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement="app.py imports non-existent 'math_utils' instead of 'utils'.",
    workspace_files={
        "src/utils.py": ("def square(x: int) -> int:\n    return x * x\n"),
        "src/app.py": (
            "from src.math_utils import square\n\n"
            "def run_square(n: int) -> int:\n"
            "    return square(n)\n"
        ),
    },
    test_files={
        "tests/test_app.py": (
            "from src.app import run_square\n\ndef test_square():\n    assert run_square(4) == 16\n"
        ),
    },
    target_files=("src/app.py",),
    timeout_seconds=30.0,
    failure_category="import_failure",
)

# ---------------------------------------------------------------------------
# Task 7: Security Boundary — Path Traversal Guard
# ---------------------------------------------------------------------------
TASK_SECURITY_TRAVERSAL_GUARD = BenchmarkTask(
    task_id="SWE-SEC-001",
    name="Enforce Path Traversal Boundary",
    category=BenchmarkCategory.RECOVERY_CHALLENGE,
    difficulty=BenchmarkDifficulty.HARD,
    problem_statement=(
        "sanitize_path in storage.py allows directory traversal via '../'. "
        "Block traversal attempts and raise ValueError."
    ),
    workspace_files={
        "src/storage.py": (
            "from pathlib import Path\n\n"
            "def sanitize_path(base_dir: str, rel_path: str) -> Path:\n"
            "    return Path(base_dir) / rel_path\n"
        ),
    },
    test_files={
        "tests/test_storage.py": (
            "import pytest\n"
            "from src.storage import sanitize_path\n\n"
            "def test_valid_path():\n"
            "    p = sanitize_path('/app/data', 'user.txt')\n"
            "    assert str(p).replace('\\\\', '/').endswith('/app/data/user.txt')\n\n"
            "def test_traversal_blocked():\n"
            "    with pytest.raises(ValueError):\n"
            "        sanitize_path('/app/data', '../../etc/passwd')\n"
        ),
    },
    target_files=("src/storage.py",),
    timeout_seconds=30.0,
    risk_classification="high",
    failure_category="security_failure",
)

# ---------------------------------------------------------------------------
# Standard Benchmark Suites
# ---------------------------------------------------------------------------

STANDARD_CORPUS: tuple[BenchmarkTask, ...] = (
    TASK_BUG_FIX_CALCULATOR,
    TASK_BUG_FIX_CONFIG_PARSER,
    TASK_REGRESSION_CACHE,
    TASK_SYNTAX_VALIDATOR,
)

SMOKE_CORPUS: tuple[BenchmarkTask, ...] = (
    TASK_BUG_FIX_CALCULATOR,
    TASK_BUG_FIX_CONFIG_PARSER,
)

FAILURE_TAXONOMY_CORPUS: tuple[BenchmarkTask, ...] = (
    TASK_SYNTAX_VALIDATOR,
    TASK_BUG_FIX_CALCULATOR,
    TASK_TYPE_FORMATTER,
    TASK_IMPORT_RESOLVER,
    TASK_REGRESSION_CACHE,
    TASK_SECURITY_TRAVERSAL_GUARD,
)


def get_benchmark_suite(suite_name: str = "standard") -> tuple[BenchmarkTask, ...]:
    """Retrieve benchmark tasks by suite name."""
    normalized = suite_name.lower().strip()
    if normalized in ("smoke", "quick"):
        return SMOKE_CORPUS
    if normalized in ("standard", "full", "default"):
        return STANDARD_CORPUS
    if normalized in ("taxonomy", "failures", "v6", "comprehensive"):
        return FAILURE_TAXONOMY_CORPUS
    raise KeyError(
        f"Unknown benchmark suite '{suite_name}'. Available: 'standard', 'smoke', 'taxonomy'."
    )
