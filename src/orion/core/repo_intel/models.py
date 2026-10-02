"""Data models and enums for V3 Deep Repository Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SymbolType(str, Enum):
    """Categorization of code symbols extracted by repository intelligence."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"


@dataclass(frozen=True)
class CodeSymbol:
    """An individual symbol extracted from AST parsing."""

    name: str
    symbol_type: SymbolType
    file_path: str
    line_number: int
    end_line: int = -1
    docstring: str | None = None
    signature: str | None = None
    parent_symbol: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert code symbol to dictionary."""
        return {
            "name": self.name,
            "symbol_type": self.symbol_type.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "end_line": self.end_line,
            "docstring": self.docstring,
            "signature": self.signature,
            "parent_symbol": self.parent_symbol,
        }


@dataclass
class ModuleNode:
    """A module node in the repository code graph."""

    file_path: str
    module_name: str
    is_test: bool = False
    symbols: dict[str, CodeSymbol] = field(default_factory=dict)
    imports: set[str] = field(default_factory=set)
    dependencies: set[str] = field(default_factory=set)  # file paths this module imports
    dependents: set[str] = field(default_factory=set)  # file paths that import this module
    test_targets: set[str] = field(default_factory=set)  # if test, files it targets

    def to_dict(self) -> dict[str, Any]:
        """Convert module node to dictionary."""
        return {
            "file_path": self.file_path,
            "module_name": self.module_name,
            "is_test": self.is_test,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
            "imports": sorted(self.imports),
            "dependencies": sorted(self.dependencies),
            "dependents": sorted(self.dependents),
            "test_targets": sorted(self.test_targets),
        }


@dataclass(frozen=True)
class ArchitectureProfile:
    """High-level architectural profile of a repository."""

    framework: str
    test_runner: str
    config_files: tuple[str, ...]
    source_roots: tuple[str, ...]
    total_files: int
    total_symbols: int

    def to_dict(self) -> dict[str, Any]:
        """Convert architecture profile to dictionary."""
        return {
            "framework": self.framework,
            "test_runner": self.test_runner,
            "config_files": list(self.config_files),
            "source_roots": list(self.source_roots),
            "total_files": self.total_files,
            "total_symbols": self.total_symbols,
        }


@dataclass(frozen=True)
class ImpactReport:
    """Pre-patch change impact analysis report."""

    target_file: str
    modified_symbols: tuple[str, ...]
    directly_affected_modules: tuple[str, ...]
    transitively_affected_modules: tuple[str, ...]
    impacted_tests: tuple[str, ...]
    regression_risk: str

    def to_dict(self) -> dict[str, Any]:
        """Convert impact report to dictionary."""
        return {
            "target_file": self.target_file,
            "modified_symbols": list(self.modified_symbols),
            "directly_affected_modules": list(self.directly_affected_modules),
            "transitively_affected_modules": list(self.transitively_affected_modules),
            "impacted_tests": list(self.impacted_tests),
            "regression_risk": self.regression_risk,
        }


@dataclass(frozen=True)
class OptimizedContext:
    """Bounded, token-efficient context neighborhood for a target change."""

    target_path: str
    symbols: tuple[CodeSymbol, ...]
    relevant_imports: tuple[str, ...]
    relevant_tests: tuple[str, ...]
    neighbor_files: tuple[str, ...]
    token_estimate: int
    context_snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Convert optimized context to dictionary."""
        return {
            "target_path": self.target_path,
            "symbols": [s.to_dict() for s in self.symbols],
            "relevant_imports": list(self.relevant_imports),
            "relevant_tests": list(self.relevant_tests),
            "neighbor_files": list(self.neighbor_files),
            "token_estimate": self.token_estimate,
            "context_snippet": self.context_snippet,
        }
