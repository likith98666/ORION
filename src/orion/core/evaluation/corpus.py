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


def get_benchmark_suite(suite_name: str = "standard") -> tuple[BenchmarkTask, ...]:
    """Retrieve benchmark tasks by suite name."""
    normalized = suite_name.lower().strip()
    if normalized in ("smoke", "quick"):
        return SMOKE_CORPUS
    if normalized in ("standard", "full", "default"):
        return STANDARD_CORPUS
    raise KeyError(f"Unknown benchmark suite '{suite_name}'. Available: 'standard', 'smoke'.")
