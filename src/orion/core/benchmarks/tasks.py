"""Standardized 10-task SWE benchmark suite covering formal failure taxonomies.

Each benchmark task contains a reproducible bug in standard Python code and a test suite
that fails unassisted and passes once repaired.
"""

from __future__ import annotations

from orion.core.evaluation.models import (
    BenchmarkCategory,
    BenchmarkDifficulty,
    BenchmarkTask,
)

# 1. Off-by-one arithmetic / indexing
TASK_OFF_BY_ONE = BenchmarkTask(
    task_id="BM-OFF-BY-ONE",
    name="Pagination Offset Off-By-One",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement=(
        "paginate() in pagination.py uses 0-based page multiplier for 1-based page numbers."
    ),
    workspace_files={
        "src/pagination.py": (
            "def paginate(items: list[int], page: int, page_size: int) -> list[int]:\n"
            "    start = page * page_size\n"
            "    return items[start:start + page_size]\n"
        )
    },
    test_files={
        "tests/test_pagination.py": (
            "from src.pagination import paginate\n\n"
            "def test_first_page():\n"
            "    items = list(range(10))\n"
            "    assert paginate(items, page=1, page_size=3) == [0, 1, 2]\n\n"
            "def test_second_page():\n"
            "    items = list(range(10))\n"
            "    assert paginate(items, page=2, page_size=3) == [3, 4, 5]\n"
        )
    },
    target_files=("src/pagination.py",),
    timeout_seconds=30.0,
    failure_category="off_by_one",
)

# 2. Type error
TASK_TYPE_ERROR = BenchmarkTask(
    task_id="BM-TYPE-ERROR",
    name="Port String Concatenation Type Error",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement=(
        "format_address() in network.py concatenates string host and integer port without casting."
    ),
    workspace_files={
        "src/network.py": (
            "def format_address(host: str, port: int) -> str:\n    return host + ':' + port\n"
        )
    },
    test_files={
        "tests/test_network.py": (
            "from src.network import format_address\n\n"
            "def test_format_address():\n"
            "    assert format_address('127.0.0.1', 8080) == '127.0.0.1:8080'\n"
            "    assert format_address('localhost', 443) == 'localhost:443'\n"
        )
    },
    target_files=("src/network.py",),
    timeout_seconds=30.0,
    failure_category="type_error",
)

# 3. Missing None check
TASK_MISSING_NONE = BenchmarkTask(
    task_id="BM-MISSING-NONE",
    name="Header Sanitizer Missing None Check",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement=(
        "clean_header() in headers.py fails with AttributeError when header value is None."
    ),
    workspace_files={
        "src/headers.py": (
            "def clean_header(val: str | None) -> str:\n    return val.strip().lower()\n"
        )
    },
    test_files={
        "tests/test_headers.py": (
            "from src.headers import clean_header\n\n"
            "def test_clean_header_normal():\n"
            "    assert clean_header(' Bearer XYZ ') == 'bearer xyz'\n\n"
            "def test_clean_header_none():\n"
            "    assert clean_header(None) == ''\n"
        )
    },
    target_files=("src/headers.py",),
    timeout_seconds=30.0,
    failure_category="missing_none_check",
)

# 4. Wrong exception caught
TASK_WRONG_EXCEPTION = BenchmarkTask(
    task_id="BM-WRONG-EXCEPTION",
    name="JSON Lookup Wrong Exception Caught",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.MEDIUM,
    problem_statement=(
        "safe_lookup() in storage.py catches ValueError instead of KeyError for missing keys."
    ),
    workspace_files={
        "src/storage.py": (
            "def safe_lookup(data: dict[str, str], key: str, default: str = '') -> str:\n"
            "    try:\n"
            "        return data[key]\n"
            "    except ValueError:\n"
            "        return default\n"
        )
    },
    test_files={
        "tests/test_storage.py": (
            "from src.storage import safe_lookup\n\n"
            "def test_key_present():\n"
            "    assert safe_lookup({'a': 'b'}, 'a') == 'b'\n\n"
            "def test_key_missing():\n"
            "    assert safe_lookup({'a': 'b'}, 'missing', 'def') == 'def'\n"
        )
    },
    target_files=("src/storage.py",),
    timeout_seconds=30.0,
    failure_category="wrong_exception",
)

# 5. Bad regex
TASK_BAD_REGEX = BenchmarkTask(
    task_id="BM-BAD-REGEX",
    name="Semantic Version Regex Escaping",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.MEDIUM,
    problem_statement=(
        "is_semver() in semver.py has unescaped dot in regex, permitting arbitrary characters."
    ),
    workspace_files={
        "src/semver.py": (
            "import re\n\n"
            "def is_semver(version: str) -> bool:\n"
            "    pattern = r'^\\d+.\\d+.\\d+$'\n"
            "    return bool(re.match(pattern, version))\n"
        )
    },
    test_files={
        "tests/test_semver.py": (
            "from src.semver import is_semver\n\n"
            "def test_valid_semver():\n"
            "    assert is_semver('1.2.3') is True\n"
            "    assert is_semver('10.20.30') is True\n\n"
            "def test_invalid_semver():\n"
            "    assert is_semver('1a2b3') is False\n"
            "    assert is_semver('1-2-3') is False\n"
        )
    },
    target_files=("src/semver.py",),
    timeout_seconds=30.0,
    failure_category="bad_regex",
)

# 6. Concurrency race
TASK_CONCURRENCY_RACE = BenchmarkTask(
    task_id="BM-CONCURRENCY-RACE",
    name="Shared Metrics Counter Concurrency Race",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.HARD,
    problem_statement=(
        "MetricsCounter in metrics.py does not synchronize increment across concurrent threads."
    ),
    workspace_files={
        "src/metrics.py": (
            "import threading\n"
            "import time\n\n"
            "class MetricsCounter:\n"
            "    def __init__(self) -> None:\n"
            "        self.count = 0\n"
            "        self.lock = threading.Lock()\n\n"
            "    def increment(self) -> None:\n"
            "        curr = self.count\n"
            "        time.sleep(0.0001)\n"
            "        self.count = curr + 1\n"
        )
    },
    test_files={
        "tests/test_metrics.py": (
            "import threading\n"
            "from src.metrics import MetricsCounter\n\n"
            "def test_concurrent_increments():\n"
            "    counter = MetricsCounter()\n"
            "    threads = [\n"
            "        threading.Thread(target=lambda: [counter.increment() for _ in range(10)])\n"
            "        for _ in range(5)\n"
            "    ]\n"
            "    for t in threads: t.start()\n"
            "    for t in threads: t.join()\n"
            "    assert counter.count == 50\n"
        )
    },
    target_files=("src/metrics.py",),
    timeout_seconds=30.0,
    failure_category="concurrency_race",
)

# 7. Resource leak
TASK_RESOURCE_LEAK = BenchmarkTask(
    task_id="BM-RESOURCE-LEAK",
    name="Audit Log Reader Resource Leak",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.MEDIUM,
    problem_statement=(
        "read_log() in logger.py leaves open file handle without context management."
    ),
    workspace_files={
        "src/logger.py": (
            "OPEN_HANDLES = []\n\n"
            "def read_log(path: str) -> str:\n"
            "    f = open(path, 'r', encoding='utf-8')\n"
            "    OPEN_HANDLES.append(f)\n"
            "    return f.read()\n"
        )
    },
    test_files={
        "tests/test_logger.py": (
            "from src.logger import read_log, OPEN_HANDLES\n\n"
            "def test_read_log_closes_file(tmp_path):\n"
            "    log_file = tmp_path / 'app.log'\n"
            "    log_file.write_text('system_healthy', encoding='utf-8')\n"
            "    content = read_log(str(log_file))\n"
            "    assert content == 'system_healthy'\n"
            "    assert len(OPEN_HANDLES) > 0 and all(h.closed for h in OPEN_HANDLES)\n"
        )
    },
    target_files=("src/logger.py",),
    timeout_seconds=30.0,
    failure_category="resource_leak",
)

# 8. Wrong operator
TASK_WRONG_OPERATOR = BenchmarkTask(
    task_id="BM-WRONG-OPERATOR",
    name="Rate Limit Check Inverted Comparison Operator",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement=(
        "is_rate_limited() in limiter.py uses < instead of >=, inverting limit logic."
    ),
    workspace_files={
        "src/limiter.py": (
            "def is_rate_limited(request_count: int, threshold: int) -> bool:\n"
            "    return request_count < threshold\n"
        )
    },
    test_files={
        "tests/test_limiter.py": (
            "from src.limiter import is_rate_limited\n\n"
            "def test_within_limit():\n"
            "    assert is_rate_limited(5, 10) is False\n\n"
            "def test_at_limit():\n"
            "    assert is_rate_limited(10, 10) is True\n\n"
            "def test_exceeded_limit():\n"
            "    assert is_rate_limited(15, 10) is True\n"
        )
    },
    target_files=("src/limiter.py",),
    timeout_seconds=30.0,
    failure_category="wrong_operator",
)

# 9. Bad default argument
TASK_BAD_DEFAULT_ARG = BenchmarkTask(
    task_id="BM-BAD-DEFAULT-ARG",
    name="Mutable List Default Argument Mutation",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.EASY,
    problem_statement=(
        "record_event() in tracer.py uses mutable list [] as default parameter value."
    ),
    workspace_files={
        "src/tracer.py": (
            "def record_event(name: str, history: list[str] = []) -> list[str]:\n"
            "    history.append(name)\n"
            "    return history\n"
        )
    },
    test_files={
        "tests/test_tracer.py": (
            "from src.tracer import record_event\n\n"
            "def test_fresh_calls():\n"
            "    res1 = record_event('event1')\n"
            "    res2 = record_event('event2')\n"
            "    assert res1 == ['event1']\n"
            "    assert res2 == ['event2']\n"
        )
    },
    target_files=("src/tracer.py",),
    timeout_seconds=30.0,
    failure_category="bad_default_argument",
)

# 10. Floating-point rounding error
TASK_FLOAT_ROUNDING = BenchmarkTask(
    task_id="BM-FLOAT-ROUNDING",
    name="Currency Ledger Rounding Precision Bug",
    category=BenchmarkCategory.BUG_FIX,
    difficulty=BenchmarkDifficulty.MEDIUM,
    problem_statement=(
        "calculate_total() in ledger.py sums floats without rounding, accumulating binary error."
    ),
    workspace_files={
        "src/ledger.py": (
            "def calculate_total(amounts: list[float]) -> float:\n    return sum(amounts)\n"
        )
    },
    test_files={
        "tests/test_ledger.py": (
            "from src.ledger import calculate_total\n\n"
            "def test_cents_sum():\n"
            "    # 0.1 + 0.2 equals 0.30000000000000004 in raw IEEE-754\n"
            "    total = calculate_total([0.1, 0.2])\n"
            "    assert total == 0.3\n"
        )
    },
    target_files=("src/ledger.py",),
    timeout_seconds=30.0,
    failure_category="floating_point_rounding",
)

BENCHMARK_TASKS: tuple[BenchmarkTask, ...] = (
    TASK_OFF_BY_ONE,
    TASK_TYPE_ERROR,
    TASK_MISSING_NONE,
    TASK_WRONG_EXCEPTION,
    TASK_BAD_REGEX,
    TASK_CONCURRENCY_RACE,
    TASK_RESOURCE_LEAK,
    TASK_WRONG_OPERATOR,
    TASK_BAD_DEFAULT_ARG,
    TASK_FLOAT_ROUNDING,
)

BENCHMARK_REPAIRS: dict[str, dict[str, str]] = {
    "BM-OFF-BY-ONE": {
        "src/pagination.py": (
            "def paginate(items: list[int], page: int, page_size: int) -> list[int]:\n"
            "    start = (page - 1) * page_size\n"
            "    return items[start:start + page_size]\n"
        )
    },
    "BM-TYPE-ERROR": {
        "src/network.py": (
            "def format_address(host: str, port: int) -> str:\n    return f'{host}:{port}'\n"
        )
    },
    "BM-MISSING-NONE": {
        "src/headers.py": (
            "def clean_header(val: str | None) -> str:\n"
            "    if val is None:\n"
            "        return ''\n"
            "    return val.strip().lower()\n"
        )
    },
    "BM-WRONG-EXCEPTION": {
        "src/storage.py": (
            "def safe_lookup(data: dict[str, str], key: str, default: str = '') -> str:\n"
            "    try:\n"
            "        return data[key]\n"
            "    except KeyError:\n"
            "        return default\n"
        )
    },
    "BM-BAD-REGEX": {
        "src/semver.py": (
            "import re\n\n"
            "def is_semver(version: str) -> bool:\n"
            "    pattern = r'^\\d+\\.\\d+\\.\\d+$'\n"
            "    return bool(re.match(pattern, version))\n"
        )
    },
    "BM-CONCURRENCY-RACE": {
        "src/metrics.py": (
            "import threading\n"
            "import time\n\n"
            "class MetricsCounter:\n"
            "    def __init__(self) -> None:\n"
            "        self.count = 0\n"
            "        self.lock = threading.Lock()\n\n"
            "    def increment(self) -> None:\n"
            "        with self.lock:\n"
            "            curr = self.count\n"
            "            time.sleep(0.0001)\n"
            "            self.count = curr + 1\n"
        )
    },
    "BM-RESOURCE-LEAK": {
        "src/logger.py": (
            "OPEN_HANDLES = []\n\n"
            "def read_log(path: str) -> str:\n"
            "    with open(path, 'r', encoding='utf-8') as f:\n"
            "        OPEN_HANDLES.append(f)\n"
            "        return f.read()\n"
        )
    },
    "BM-WRONG-OPERATOR": {
        "src/limiter.py": (
            "def is_rate_limited(request_count: int, threshold: int) -> bool:\n"
            "    return request_count >= threshold\n"
        )
    },
    "BM-BAD-DEFAULT-ARG": {
        "src/tracer.py": (
            "def record_event(name: str, history: list[str] | None = None) -> list[str]:\n"
            "    if history is None:\n"
            "        history = []\n"
            "    history.append(name)\n"
            "    return history\n"
        )
    },
    "BM-FLOAT-ROUNDING": {
        "src/ledger.py": (
            "def calculate_total(amounts: list[float]) -> float:\n"
            "    return round(sum(amounts), 2)\n"
        )
    },
}
