"""AST-based Python source code symbol indexer for V3 Deep Repository Intelligence."""

from __future__ import annotations

import ast
from pathlib import Path

from orion.core.repo_intel.models import CodeSymbol, ModuleNode, SymbolType

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "egg-info",
    }
)


class ASTSymbolIndexer:
    """Extracts symbols, definitions, signatures, and imports across a repository workspace."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()
        if not self.root_dir.exists():
            raise ValueError(f"Repository root does not exist: '{root_dir}'")
        if not self.root_dir.is_dir():
            raise ValueError(f"Repository root is not a directory: '{root_dir}'")

    def index_repository(self) -> dict[str, ModuleNode]:
        """Index all Python files in the repository."""
        modules: dict[str, ModuleNode] = {}

        for py_path in self._discover_python_files():
            rel_path = str(py_path.relative_to(self.root_dir)).replace("\\", "/")
            module_node = self.index_file(py_path, rel_path)
            modules[rel_path] = module_node

        return modules

    def index_file(self, full_path: Path, rel_path: str) -> ModuleNode:
        """Parse a single Python file into a ModuleNode with extracted symbols and imports."""
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = full_path.read_text(encoding="latin-1", errors="replace")

        module_name = self._path_to_module_name(rel_path)
        is_test = "test" in rel_path.lower() or Path(rel_path).name.startswith("test_")
        node = ModuleNode(
            file_path=rel_path,
            module_name=module_name,
            is_test=is_test,
        )

        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError as exc:
            # Record broken file without failing entire repository indexing
            err_sym = CodeSymbol(
                name="<SyntaxError>",
                symbol_type=SymbolType.VARIABLE,
                file_path=rel_path,
                line_number=exc.lineno or 1,
                docstring=f"SyntaxError: {exc.msg}",
            )
            node.symbols["<SyntaxError>"] = err_sym
            return node

        # Extract module docstring
        mod_doc = ast.get_docstring(tree)
        if mod_doc:
            mod_sym = CodeSymbol(
                name=module_name,
                symbol_type=SymbolType.MODULE,
                file_path=rel_path,
                line_number=1,
                docstring=mod_doc,
            )
            node.symbols[module_name] = mod_sym

        # Extract imports and top-level definitions
        for item in tree.body:
            if isinstance(item, (ast.Import, ast.ImportFrom)):
                self._extract_imports(item, node)
            elif isinstance(item, ast.ClassDef):
                self._extract_class(item, node, rel_path)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(item, node, rel_path)

        return node

    def _discover_python_files(self) -> list[Path]:
        """Discover Python files while skipping excluded folders."""
        found: list[Path] = []
        for path in self.root_dir.rglob("*.py"):
            parts = set(path.relative_to(self.root_dir).parts)
            if not parts.intersection(EXCLUDED_DIRS):
                found.append(path)
        return sorted(found)

    def _path_to_module_name(self, rel_path: str) -> str:
        """Convert relative file path to Python dot-separated module name."""
        p = Path(rel_path)
        parts = list(p.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def _extract_imports(self, node: ast.Import | ast.ImportFrom, module_node: ModuleNode) -> None:
        """Extract imported module names and symbols."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_node.imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base_mod = node.module or ""
            module_node.imports.add(base_mod)
            for alias in node.names:
                full_sym = f"{base_mod}.{alias.name}" if base_mod else alias.name
                module_node.imports.add(full_sym)

    def _extract_class(self, node: ast.ClassDef, module_node: ModuleNode, rel_path: str) -> None:
        """Extract a class and its member methods."""
        class_name = node.name
        doc = ast.get_docstring(node)
        bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else []
        sig = f"class {class_name}({', '.join(bases)})" if bases else f"class {class_name}"

        end_lineno = getattr(node, "end_lineno", node.lineno)
        sym = CodeSymbol(
            name=class_name,
            symbol_type=SymbolType.CLASS,
            file_path=rel_path,
            line_number=node.lineno,
            end_line=end_lineno,
            docstring=doc,
            signature=sig,
        )
        module_node.symbols[class_name] = sym

        # Methods within the class
        for sub in node.body:
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_name = sub.name
                full_method_name = f"{class_name}.{method_name}"
                method_doc = ast.get_docstring(sub)
                args = [a.arg for a in sub.args.args]
                method_sig = f"def {method_name}({', '.join(args)})"

                m_end_lineno = getattr(sub, "end_lineno", sub.lineno)
                m_sym = CodeSymbol(
                    name=full_method_name,
                    symbol_type=SymbolType.METHOD,
                    file_path=rel_path,
                    line_number=sub.lineno,
                    end_line=m_end_lineno,
                    docstring=method_doc,
                    signature=method_sig,
                    parent_symbol=class_name,
                )
                module_node.symbols[full_method_name] = m_sym

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        module_node: ModuleNode,
        rel_path: str,
    ) -> None:
        """Extract a top-level function."""
        func_name = node.name
        doc = ast.get_docstring(node)
        args = [a.arg for a in node.args.args]
        sig = f"def {func_name}({', '.join(args)})"

        end_lineno = getattr(node, "end_lineno", node.lineno)
        sym = CodeSymbol(
            name=func_name,
            symbol_type=SymbolType.FUNCTION,
            file_path=rel_path,
            line_number=node.lineno,
            end_line=end_lineno,
            docstring=doc,
            signature=sig,
        )
        module_node.symbols[func_name] = sym
