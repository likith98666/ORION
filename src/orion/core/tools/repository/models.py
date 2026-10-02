from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ListFilesResult:
    """Structured result of list_files operation."""

    path: str
    entries: tuple[dict[str, Any], ...]
    total_count: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadFileResult:
    """Structured result of read_file operation."""

    path: str
    content: str
    size: int
    total_lines: int
    lines_read: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchMatch:
    """A single search match within a repository file."""

    file: str
    line_number: int
    line_content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchFilesResult:
    """Structured result of search_files operation."""

    query: str
    matches: tuple[dict[str, Any], ...]
    total_matches: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WriteFileResult:
    """Structured result of write_file operation."""

    path: str
    bytes_written: int
    created: bool
    checksum: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApplyChangeResult:
    """Structured result of apply_change operation."""

    path: str
    previous_hash: str
    new_hash: str
    change_applied: bool
    lines_added: int
    lines_removed: int
    diff_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiffResult:
    """Structured result of diff operation."""

    path: str
    diff: str
    identical: bool
    lines_added: int
    lines_removed: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    """Structured result of validation tool execution."""

    operation: str
    status: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool
    workspace_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
