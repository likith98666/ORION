"""Directed code graph tracking module imports, symbol definitions, and test mappings."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from orion.core.repo_intel.indexer import ASTSymbolIndexer
from orion.core.repo_intel.models import CodeSymbol, ModuleNode


class RepoCodeGraph:
    """Directed graph representing inter-module dependencies and symbol definitions."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()
        self._indexer = ASTSymbolIndexer(self.root_dir)
        self.modules: dict[str, ModuleNode] = {}
        self._module_lookup: dict[str, str] = {}  # module_name -> file_path
        self._symbol_index: dict[str, list[CodeSymbol]] = {}  # symbol_name -> list of CodeSymbol

    @classmethod
    def build_from_workspace(cls, root_dir: Path | str) -> RepoCodeGraph:
        """Construct and populate a RepoCodeGraph from a repository root."""
        graph = cls(root_dir)
        graph.build()
        return graph

    def build(self) -> None:
        """Execute indexing and resolve inter-module dependencies."""
        self.modules = self._indexer.index_repository()
        self._module_lookup.clear()
        self._symbol_index.clear()

        # Build module name to file path lookup
        for path, node in self.modules.items():
            self._module_lookup[node.module_name] = path
            # Also register suffix aliases (e.g. 'calc' for 'src.calc')
            simple_name = Path(path).stem
            if simple_name != "__init__" and simple_name not in self._module_lookup:
                self._module_lookup[simple_name] = path

            for sym in node.symbols.values():
                self._symbol_index.setdefault(sym.name, []).append(sym)

        # Resolve dependencies and dependents
        for path, node in self.modules.items():
            for imported in node.imports:
                target_path = self._resolve_import_to_path(imported)
                if target_path and target_path != path:
                    node.dependencies.add(target_path)
                    if target_path in self.modules:
                        self.modules[target_path].dependents.add(path)
                        # If this module is a test file, mark it as testing target_path
                        if node.is_test:
                            node.test_targets.add(target_path)

    def _resolve_import_to_path(self, import_str: str) -> str | None:
        """Resolve an import string (e.g. 'src.calc' or 'calc') to a known relative file path."""
        if import_str in self._module_lookup:
            return self._module_lookup[import_str]

        # Check prefix matches
        parts = import_str.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in self._module_lookup:
                return self._module_lookup[candidate]
            parts.pop()

        return None

    def find_symbol_definitions(self, symbol_name: str) -> list[CodeSymbol]:
        """Find where a function, class, or method is defined across the repository."""
        return list(self._symbol_index.get(symbol_name, []))

    def get_tests_for_file(self, file_path: str) -> list[str]:
        """Return all test file paths that import or target the given file."""
        norm_path = file_path.replace("\\", "/")
        target = self.modules.get(norm_path)
        if not target:
            # Try fuzzy match on basename
            base = Path(norm_path).stem
            for p, mod in self.modules.items():
                if Path(p).stem == base:
                    target = mod
                    norm_path = p
                    break

        if not target:
            return []

        tests: set[str] = set()
        # Direct test dependents
        for dep_path in target.dependents:
            dep_node = self.modules.get(dep_path)
            if dep_node and dep_node.is_test:
                tests.add(dep_path)

        # Explicit test targets
        for p, mod in self.modules.items():
            if mod.is_test and norm_path in mod.test_targets:
                tests.add(p)

        return sorted(tests)

    def get_dependencies(self, file_path: str, recursive: bool = False) -> list[str]:
        """Retrieve files that this file imports."""
        norm_path = file_path.replace("\\", "/")
        node = self.modules.get(norm_path)
        if not node:
            return []

        if not recursive:
            return sorted(node.dependencies)

        visited: set[str] = set()
        queue: deque[str] = deque(node.dependencies)
        while queue:
            curr = queue.popleft()
            if curr in visited or curr == norm_path:
                continue
            visited.add(curr)
            curr_node = self.modules.get(curr)
            if curr_node:
                for nxt in curr_node.dependencies:
                    queue.append(nxt)

        return sorted(visited)

    def get_dependents(self, file_path: str, recursive: bool = False) -> list[str]:
        """Retrieve files that import this file."""
        norm_path = file_path.replace("\\", "/")
        node = self.modules.get(norm_path)
        if not node:
            return []

        if not recursive:
            return sorted(node.dependents)

        visited: set[str] = set()
        queue: deque[str] = deque(node.dependents)
        while queue:
            curr = queue.popleft()
            if curr in visited or curr == norm_path:
                continue
            visited.add(curr)
            curr_node = self.modules.get(curr)
            if curr_node:
                for nxt in curr_node.dependents:
                    queue.append(nxt)

        return sorted(visited)

    def to_dict(self) -> dict[str, Any]:
        """Export serialized summary of the code graph."""
        return {
            "root_dir": str(self.root_dir),
            "total_modules": len(self.modules),
            "total_symbols": sum(len(m.symbols) for m in self.modules.values()),
            "modules": {k: v.to_dict() for k, v in self.modules.items()},
        }
